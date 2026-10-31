import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase, override_settings

from masters.models import Master, MasterSalon
from pages.models import Page
from salons.models import Salon
from services.models import Service, ServiceCategory, ServiceSalon

from .documents import as_document, document_id, plain_text, public_sources
from .manticore import EXPECTED_COLUMNS, ManticoreClient, ManticoreError, index_all, index_one
from .tasks import refresh_manticore_index


class DocumentTests(SimpleTestCase):
    def test_ids_are_stable_and_distinct_across_types(self):
        self.assertEqual(document_id('service', 10), document_id('service', 10))
        self.assertNotEqual(document_id('service', 10), document_id('category', 10))
        self.assertLess(document_id('service', 10), 2**63)

    def test_html_and_entities_are_plain_text(self):
        self.assertEqual(plain_text('<p>Мастер&nbsp;<b>стрижки</b></p>'), 'Мастер стрижки')
        self.assertEqual(plain_text('<p>&lt;SPA&gt; &amp; уход</p>'), '<SPA> & уход')
        self.assertEqual(plain_text('<p>Красный</p><p>цвет</p><script>hidden()</script>'), 'Красный цвет')

    def test_service_document_uses_cms_url_and_group_terms(self):
        page = SimpleNamespace(url_path='uslugi/hair/zhenskaya-strizhka',
                               content='<h2>Для волос</h2><p>Новый образ</p>', meta_description='')
        service = SimpleNamespace(pk=7, page=page, title='Женская стрижка',
                                  description='Подбор формы', conditions='',
                                  category=SimpleNamespace(title='Для волос'),
                                  group_title='Стрижки', subgroup_title='')
        doc = as_document('service', service, 123)
        self.assertEqual(doc['url'], '/uslugi/hair/zhenskaya-strizhka')
        self.assertIn('Стрижки', doc['search_text'])
        self.assertEqual(doc['project'], 'scissors')
        self.assertEqual(doc['generation'], 123)

    def test_other_document_types_have_public_frontend_urls(self):
        page = SimpleNamespace(pk=1, title='О нас', content='', meta_title='',
                               meta_description='', url_path='about')
        master_page = SimpleNamespace(url_path='team/anna', content='', meta_description='')
        master = SimpleNamespace(pk=2, page=master_page, name='Анна', bio='',
                                 get_price_level_display=lambda: '')
        salon = SimpleNamespace(pk=3, name='Зеленоград', slug='scissors-zelenograd-17mkr',
                                address='', description='', working_hours='', page=None)
        category_page = SimpleNamespace(url_path='uslugi/hair', content='', meta_description='')
        category = SimpleNamespace(pk=4, title='Парикмахерский зал', page=category_page)
        self.assertEqual(as_document('page', page, 1)['url'], '/about')
        self.assertEqual(as_document('master', master, 1)['url'], '/team/anna')
        self.assertEqual(as_document('salon', salon, 1)['url'], '/salons/scissors-zelenograd-17mkr')
        self.assertEqual(as_document('category', category, 1)['url'], '/uslugi/hair')


@override_settings(MANTICORE_HOST='http://127.0.0.1:9570')
class ManticoreContractTests(SimpleTestCase):
    def test_existing_table_with_other_schema_is_rejected(self):
        description = {'data': [
            {'Field': 'id', 'Type': 'bigint', 'Properties': ''},
            {'Field': 'title', 'Type': 'text', 'Properties': 'indexed stored'},
            {'Field': 'content', 'Type': 'text', 'Properties': 'indexed stored'},
            {'Field': 'search_text', 'Type': 'text', 'Properties': 'indexed stored'},
            {'Field': 'type', 'Type': 'string', 'Properties': ''},
            {'Field': 'url', 'Type': 'string', 'Properties': ''},
        ]}
        client = ManticoreClient()
        with patch.object(client, '_sql', side_effect=[{}, description]):
            with self.assertRaisesMessage(ManticoreError, 'Схема scissors_index'):
                client.ensure_table()

    def test_sql_raw_response_and_existing_table_schema(self):
        description = {'data': [
            {'Field': name, 'Type': kind,
             'Properties': 'indexed stored' if kind == 'text' else ''}
            for name, kind in EXPECTED_COLUMNS.items()
        ], 'error': ''}
        responses = []
        for result in ({'error': ''}, description):
            response = Mock(status_code=200)
            response.json.return_value = [result]
            responses.append(response)
        with patch('search.manticore.requests.post', side_effect=responses) as post:
            ManticoreClient().ensure_table()
        self.assertIn(b'CREATE TABLE IF NOT EXISTS scissors_index', post.call_args_list[0].kwargs['data'])
        self.assertEqual(post.call_args.kwargs['data'], b'DESC scissors_index')

    def test_sql_error_is_not_ignored(self):
        response = Mock(status_code=200)
        response.json.return_value = [{'error': 'table unavailable'}]
        with patch('search.manticore.requests.post', return_value=response):
            with self.assertRaisesMessage(ManticoreError, 'table unavailable'):
                ManticoreClient()._sql('DESC scissors_index')

    def test_cleanup_is_limited_to_scissors_documents(self):
        client = ManticoreClient()
        with patch.object(client, '_sql') as sql:
            client.delete_stale(42)
        sql.assert_called_once_with(
            "DELETE FROM scissors_index WHERE project = 'scissors' AND generation <> 42"
        )

    def test_count_uses_exact_sql_aggregate(self):
        client = ManticoreClient()
        with patch.object(client, '_sql', return_value={'data': [{'total_count': '1234'}]}) as sql:
            self.assertEqual(client.count(), 1234)
        sql.assert_called_once_with(
            "SELECT COUNT(*) AS total_count FROM scissors_index WHERE project = 'scissors'"
        )

    def test_delete_accepts_native_id_response(self):
        item_id = document_id('service', 7)
        response = Mock(status_code=200)
        response.json.return_value = {
            'table': 'scissors_index', 'id': item_id, 'found': True,
            'result': 'deleted',
        }
        with patch('search.manticore.requests.post', return_value=response) as post:
            ManticoreClient().delete('service', 7)
        self.assertEqual(post.call_args.kwargs['json'], {'table': 'scissors_index', 'id': item_id})

    def test_bulk_replaces_documents_in_one_table(self):
        response = Mock(status_code=200)
        document = {'id': document_id('page', 1), 'type': 'page', 'title': 'О нас',
                    'content': 'Текст', 'search_text': 'О нас Текст', 'url': '/about',
                    'project': 'scissors', 'generation': 42}
        response.json.return_value = {'errors': False, 'items': [
            {'replace': {'table': 'scissors_index', 'id': document['id'],
                         'status': 201, 'result': 'created'}},
        ]}
        with patch('search.manticore.requests.post', return_value=response) as post:
            ManticoreClient().replace([document])
        args, kwargs = post.call_args
        self.assertEqual(args[0], 'http://127.0.0.1:9570/bulk')
        self.assertEqual(kwargs['headers']['Content-Type'], 'application/x-ndjson')
        line = json.loads(kwargs['data'].decode().strip())
        self.assertEqual(line['replace']['table'], 'scissors_index')
        self.assertEqual(line['replace']['id'], document['id'])
        self.assertEqual(line['replace']['doc']['url'], '/about')

    def test_bulk_accepts_transaction_summary_returned_by_server(self):
        documents = [
            {'id': document_id('page', pk), 'type': 'page', 'title': f'Страница {pk}',
             'content': '', 'search_text': f'Страница {pk}', 'url': f'/page-{pk}',
             'project': 'scissors', 'generation': 42}
            for pk in range(1, 7)
        ]
        response = Mock(status_code=200)
        response.json.return_value = {
            'items': [{'bulk': {'table': 'scissors_index', '_id': documents[0]['id'],
                                'created': 6, 'deleted': 0, 'updated': 0,
                                'result': 'created', 'status': 201}}],
            'current_line': 7, 'skipped_lines': 0, 'errors': False, 'error': '',
        }
        with patch('search.manticore.requests.post', return_value=response) as post:
            ManticoreClient().replace(documents)
        self.assertEqual(post.call_args.kwargs['data'].count(b'\n'), 6)

        response.json.return_value['items'][0]['bulk'].update(created=0, updated=6, status=200)
        with patch('search.manticore.requests.post', return_value=response):
            ManticoreClient().replace(documents)

    def test_bulk_rejects_incomplete_transaction_summary(self):
        documents = [
            {'id': document_id('page', pk), 'title': f'Страница {pk}'}
            for pk in range(1, 7)
        ]
        response = Mock(status_code=200, text='incomplete bulk response')
        response.json.return_value = {
            'items': [{'bulk': {'table': 'scissors_index', 'created': 5,
                                'updated': 0, 'status': 201}}],
            'current_line': 7, 'skipped_lines': 0, 'errors': False,
        }
        with patch('search.manticore.requests.post', return_value=response):
            with self.assertRaisesMessage(ManticoreError, 'Пакетная запись не подтверждена'):
                ManticoreClient().replace(documents)

        response.json.return_value['items'][0]['bulk']['created'] = 6
        response.json.return_value['skipped_lines'] = 1
        with patch('search.manticore.requests.post', return_value=response):
            with self.assertRaises(ManticoreError):
                ManticoreClient().replace(documents)

    def test_failed_batch_prevents_stale_cleanup(self):
        class Queryset:
            def iterator(self, **_kwargs):
                yield SimpleNamespace(pk=1, title='О нас', url_path='about',
                                      content='', meta_title='', meta_description='')

        client = Mock()
        client.replace.side_effect = ManticoreError('batch failed')
        with patch('search.manticore.public_sources', return_value={'page': Queryset()}):
            with self.assertRaises(ManticoreError):
                index_all(lambda _: None, client=client, generation=42)
        client.delete_stale.assert_not_called()

    def test_full_run_removes_stale_documents_and_checks_count(self):
        class Queryset:
            def iterator(self, **_kwargs):
                yield SimpleNamespace(pk=1, title='О нас', url_path='about',
                                      content='', meta_title='', meta_description='')

        client = Mock()
        client.count.return_value = 1
        with patch('search.manticore.public_sources', return_value={'page': Queryset()}):
            counts = index_all(lambda _: None, client=client, generation=42)
        self.assertEqual(counts, {'page': 1})
        client.delete_stale.assert_called_once_with(42)
        client.count.assert_called_once()

    def test_search_retains_manticore_ranking_and_internal_urls(self):
        response = Mock(status_code=200)
        response.json.return_value = {'hits': {'total': 2, 'hits': [
            {'_id': 9, '_source': {'type': 'service', 'title': 'Стрижка',
                                   'content': 'Текст', 'url': '/uslugi/hair/strizhka'}},
            {'_id': 8, '_source': {'type': 'category', 'title': 'Для волос',
                                   'content': '', 'url': '/uslugi/hair'}},
        ]}}
        with patch('search.manticore.requests.post', return_value=response) as post:
            results, total = ManticoreClient().search('стрижка', 2, 30)
        self.assertEqual(total, 2)
        self.assertEqual([result['id'] for result in results], ['9', '8'])
        self.assertEqual(post.call_args.kwargs['json']['offset'], 30)
        self.assertEqual(post.call_args.kwargs['json']['table'], 'scissors_index')


class SearchApiTests(SimpleTestCase):
    def test_validation_and_pagination(self):
        self.assertEqual(self.client.get('/api/v1/search', {'query': 'ст'}).status_code, 400)
        self.assertEqual(self.client.get('/api/v1/search', {
            'query': 'стрижка', 'pagination.page': 'bad',
        }).status_code, 400)
        with patch('search.views.ManticoreClient.search', return_value=([{
            'id': '1', 'type': 'service', 'title': 'Стрижка',
            'content': '', 'url': '/uslugi/hair/strizhka',
        }], 1)) as search:
            response = self.client.get('/api/v1/search', {
                'query': ' стрижка ', 'pagination.page': '2', 'pagination.pageSize': '20',
            })
        self.assertEqual(response.status_code, 200)
        search.assert_called_once_with('стрижка', 2, 20)
        self.assertEqual(response.json()['pagination'], {
            'page': 2, 'pageSize': 20, 'totalCount': 1,
        })

    def test_manticore_failure_is_unavailable_without_internal_details(self):
        with patch('search.views.ManticoreClient.search', side_effect=ManticoreError('private host')):
            response = self.client.get('/api/v1/search', {'query': 'стрижка'})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private host', response.content.decode())


class ScheduledRefreshTests(SimpleTestCase):
    def test_task_uses_same_full_indexing_path(self):
        with patch('search.tasks.index_all', return_value={'service': 3}) as index:
            self.assertEqual(refresh_manticore_index(), {'service': 3})
        self.assertEqual(index.call_count, 1)


class PublicSourceTests(TestCase):
    def test_only_public_and_reachable_catalogue_records_are_selected(self):
        root = Page.objects.filter(url_path='uslugi').first() or Page.objects.create(title='Услуги', url='uslugi')
        category_page = Page.objects.create(title='Для волос', url='hair', parent=root)
        service_page = Page.objects.create(title='Стрижка', url='strizhka', parent=category_page)
        hidden_page = Page.objects.create(title='Скрытая услуга', url='hidden', parent=category_page,
                                          is_published=False)
        category = ServiceCategory.objects.create(title='Для волос', code='hair', page=category_page)
        salon = Salon.objects.create(name='Салон', slug='salon', address='Адрес', latitude=55,
                                     longitude=37)
        service = Service.objects.create(category=category, page=service_page, title='Стрижка')
        hidden = Service.objects.create(category=category, page=hidden_page, title='Скрытая услуга')
        ServiceSalon.objects.create(service=service, salon=salon)
        ServiceSalon.objects.create(service=hidden, salon=salon)
        hidden_category_page = Page.objects.create(title='Скрытая категория', url='hidden-category', parent=root)
        hidden_category = ServiceCategory.objects.create(
            title='Скрытая категория', code='hidden-category', page=hidden_category_page,
        )
        hidden_only_page = Page.objects.create(
            title='Ещё скрытая услуга', url='hidden-only', parent=hidden_category_page,
            is_published=False,
        )
        hidden_only = Service.objects.create(
            category=hidden_category, page=hidden_only_page, title='Скрытая услуга 2',
        )
        ServiceSalon.objects.create(service=hidden_only, salon=salon)
        sources = public_sources()
        self.assertEqual(list(sources['service'].values_list('pk', flat=True)), [service.pk])
        self.assertEqual(list(sources['category'].values_list('pk', flat=True)), [category.pk])
        self.assertEqual(list(sources['salon'].values_list('pk', flat=True)), [salon.pk])
        self.assertFalse(sources['page'].filter(pk=hidden_page.pk).exists())

        master_page = Page.objects.create(title='Мастер', url='master')
        master = Master.objects.create(name='Мастер', page=master_page,
                                       yclients_user_id='person-1')
        MasterSalon.objects.create(master=master, salon=salon)
        system_page = Page.objects.create(title='Техническая запись', url='placeholder')
        system = Master.objects.create(name='Бровист', page=system_page,
                                       is_system=True, is_booking_placeholder=True)
        MasterSalon.objects.create(master=system, salon=salon)
        self.assertEqual(list(public_sources()['master'].values_list('pk', flat=True)), [master.pk])

    def test_single_record_becomes_delete_when_no_longer_public(self):
        client = Mock()
        with patch('search.manticore.public_sources') as sources:
            sources.return_value = {'service': Mock()}
            sources.return_value['service'].filter.return_value.first.return_value = None
            result = index_one('service', 7, client=client)
        self.assertEqual(result, 'deleted')
        client.delete.assert_called_once_with('service', 7)
