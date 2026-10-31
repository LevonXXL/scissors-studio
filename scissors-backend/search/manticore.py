"""One real-time Manticore table for public Scissors Studio content."""

import json
import time

import requests
from django.conf import settings

from .documents import as_document, document_id, public_sources


INDEX = 'scissors_index'
PROJECT = 'scissors'
BATCH_SIZE = 400
CREATE_TABLE = (
    f'CREATE TABLE IF NOT EXISTS {INDEX} '
    '(title text, content text, search_text text, type string, url string, '
    "project string, generation bigint) morphology='stem_enru'"
)
EXPECTED_COLUMNS = {
    'id': 'bigint', 'title': 'text', 'content': 'text',
    'search_text': 'text', 'type': 'string', 'url': 'string',
    'project': 'string', 'generation': 'bigint',
}


class ManticoreError(Exception):
    pass


class ManticoreClient:
    def _post(self, path, *, timeout=30, **kwargs):
        try:
            response = requests.post(
                settings.MANTICORE_HOST.rstrip('/') + path,
                timeout=timeout, **kwargs,
            )
        except requests.RequestException as exc:
            raise ManticoreError('Нет соединения с поисковым сервером.') from exc
        if not 200 <= response.status_code < 300:
            raise ManticoreError(f'Manticore HTTP {response.status_code}: {response.text[:500]}')
        return response

    def _sql(self, statement):
        response = self._post('/sql?mode=raw', data=statement.encode('utf-8'))
        try:
            results = response.json()
            if not isinstance(results, list) or len(results) != 1 or not isinstance(results[0], dict):
                raise ValueError('unexpected SQL response')
            result = results[0]
        except (ValueError, TypeError, KeyError) as exc:
            raise ManticoreError('Некорректный ответ SQL-интерфейса Manticore.') from exc
        if result.get('error'):
            raise ManticoreError(str(result['error'])[:500])
        return result

    def ensure_table(self):
        # IF NOT EXISTS is not enough: an existing scissors_index may have
        # a different schema. Stop before writing or cleaning it.
        self._sql(CREATE_TABLE)
        description = self._sql(f'DESC {INDEX}')
        try:
            columns = {row['Field']: row for row in description['data']}
            correct_types = all(columns[name]['Type'] == kind
                                for name, kind in EXPECTED_COLUMNS.items())
            text_properties = all(
                {'indexed', 'stored'} <= set(columns[name]['Properties'].split())
                for name in ('title', 'content', 'search_text')
            )
        except (KeyError, TypeError, AttributeError):
            correct_types = text_properties = False
        if not correct_types or not text_properties:
            raise ManticoreError(f'Схема {INDEX} не соответствует Scissors Studio; индексация остановлена.')

    def replace(self, documents):
        if not documents:
            return
        payload = ''.join(json.dumps({
            'replace': {
                'table': INDEX, 'id': item['id'],
                'doc': {key: value for key, value in item.items() if key != 'id'},
            },
        }, ensure_ascii=False) + '\n' for item in documents)
        response = self._post('/bulk', data=payload.encode('utf-8'),
                              headers={'Content-Type': 'application/x-ndjson'}, timeout=60)
        try:
            result = response.json()
            if (result['errors'] is not False or result.get('error') or
                    result.get('skipped_lines', 0) != 0 or
                    result.get('current_line', len(documents)) < len(documents)):
                raise ValueError('Manticore сообщил об ошибке в пакетной записи')

            items = result['items']
            if len(items) == 1 and 'bulk' in items[0]:
                # Native /bulk groups operations for one RT table into a
                # transaction and returns one summary, not one item per row.
                summary = items[0]['bulk']
                confirmed = (
                    summary['table'] == INDEX and
                    200 <= summary['status'] < 300 and
                    summary['created'] + summary['updated'] == len(documents)
                )
            else:
                # Older versions can return one replace result per document.
                confirmed = len(items) == len(documents) and all(
                    item['replace']['table'] == INDEX and
                    int(item['replace'].get('id', item['replace'].get('_id'))) == document['id'] and
                    200 <= item['replace']['status'] < 300 and
                    item['replace']['result'] in ('created', 'updated')
                    for item, document in zip(items, documents)
                )
            if not confirmed:
                raise ValueError('Manticore не подтвердил все документы пакета')
        except (ValueError, TypeError, KeyError, IndexError) as exc:
            raise ManticoreError(f'Пакетная запись не подтверждена: {response.text[:500]}') from exc

    def delete(self, kind, pk):
        item_id = document_id(kind, pk)
        response = self._post('/delete', json={'table': INDEX, 'id': item_id})
        try:
            result = response.json()
            if (result['table'] != INDEX or int(result['id']) != item_id or
                    result.get('result') not in ('deleted', 'not found', 'not_found') and
                    result.get('found') is not False):
                raise ValueError('unexpected delete result')
        except (ValueError, TypeError, KeyError) as exc:
            raise ManticoreError('Manticore не подтвердил удаление документа.') from exc

    def delete_stale(self, generation):
        # Executed only after every source batch has been confirmed.
        self._sql(f"DELETE FROM {INDEX} WHERE project = '{PROJECT}' AND generation <> {generation}")

    def count(self):
        result = self._sql(f"SELECT COUNT(*) AS total_count FROM {INDEX} WHERE project = '{PROJECT}'")
        try:
            return int(result['data'][0]['total_count'])
        except (ValueError, TypeError, KeyError, IndexError) as exc:
            raise ManticoreError('Некорректный ответ Manticore при проверке числа документов.') from exc

    def search(self, query, page, page_size):
        response = self._post('/search', json={
            'table': INDEX,
            'query': {'bool': {'must': [
                {'match': {'search_text': query}},
                {'equals': {'project': PROJECT}},
            ]}},
            'limit': page_size,
            'offset': (page - 1) * page_size,
            'options': {'max_matches': 10000},
        })
        try:
            hits = response.json()['hits']
            total = int(hits['total'])
            results = []
            for hit in hits['hits']:
                source = hit['_source']
                url = source['url']
                if not isinstance(url, str) or not url.startswith('/') or url.startswith('//'):
                    raise ValueError('Некорректный URL поискового документа')
                results.append({
                    'id': str(hit['_id']), 'type': source['type'],
                    'title': source['title'], 'content': source['content'],
                    'url': url,
                })
            return results, total
        except (ValueError, TypeError, KeyError) as exc:
            raise ManticoreError('Некорректный ответ поискового сервера.') from exc


def index_all(output, *, client=None, generation=None):
    client = client or ManticoreClient()
    client.ensure_table()
    generation = generation or time.time_ns()
    counts = {}
    for kind, queryset in public_sources().items():
        batch = []
        count = 0
        for obj in queryset.iterator(chunk_size=BATCH_SIZE):
            batch.append(as_document(kind, obj, generation))
            if len(batch) == BATCH_SIZE:
                client.replace(batch)
                count += len(batch)
                batch = []
        if batch:
            client.replace(batch)
            count += len(batch)
        counts[kind] = count
        output(f'{kind}: {count}')

    client.delete_stale(generation)
    actual = client.count()
    expected = sum(counts.values())
    if actual != expected:
        raise ManticoreError(f'Проверка индекса: ожидалось {expected}, найдено {actual}.')
    return counts


def index_one(kind, pk, *, client=None):
    sources = public_sources()
    if kind not in sources:
        raise ValueError(f'Неизвестный тип документа: {kind}')
    client = client or ManticoreClient()
    client.ensure_table()
    obj = sources[kind].filter(pk=pk).first()
    if obj is None:
        client.delete(kind, pk)
        return 'deleted'
    client.replace([as_document(kind, obj, time.time_ns())])
    return 'updated'
