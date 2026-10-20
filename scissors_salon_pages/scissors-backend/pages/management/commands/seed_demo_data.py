from django.core.management.base import BaseCommand

from masters.models import Master
from pages.models import Page
from salons.models import Salon


class Command(BaseCommand):
    help = 'Создаёт демо-данные (2 салона, пара мастеров, дерево страниц) для локальной проверки.'

    def handle(self, *args, **options):
        if Salon.objects.exists() or Page.objects.exists():
            self.stdout.write(self.style.WARNING(
                'В базе уже есть данные — команда рассчитана на пустую БД. Ничего не делаю.'
            ))
            return

        moscow = Salon.objects.create(
            name='Москва, Красные ворота',
            address='Москва, Большой Козловский переулок, 11/4',
            latitude='55.769600', longitude='37.652200',
            phone='+7 (926) 071-71-63',
            working_hours='Ежедневно 10:00 — 22:00',
        )
        zelenograd = Salon.objects.create(
            name='Зеленоград, 17 район',
            address='Зеленоград, корпус 1712',
            latitude='55.987200', longitude='37.181300',
            phone='+7 (926) 729-79-89',
            working_hours='Ежедневно 10:00 — 22:00',
            position=1,
        )

        Master.objects.create(
            salon=moscow, name='Анна Иванова', specialization='Стрижки, окрашивание',
            category=Master.CATEGORY_STYLIST, status=Master.STATUS_SELF_EMPLOYED,
            bio='Топ-стилист, специализация — сложное окрашивание.',
        )
        Master.objects.create(
            salon=zelenograd, name='Мария Петрова', specialization='Ногтевой сервис',
            category=Master.CATEGORY_UNIVERSAL, status=Master.STATUS_IP,
        )

        about = Page.objects.create(
            title='О пространстве',
            meta_description='Scissors Studio — пространство независимых мастеров-партнёров.',
            content='<p>Scissors Studio — пространство, где собрана команда партнёров-профессионалов.</p>',
        )
        Page.objects.create(title='Команда', parent=about)
        Page.objects.create(title='Вакансии', parent=about, position=1)
        Page.objects.create(title='Политика конфиденциальности')

        self.stdout.write(self.style.WARNING(
            'Демо-записей (Booking) не создаю — для них нужны реальные '
            'yclients_company_id/yclients_staff_id, тестовые данные тут не помогут.'
        ))

        self.stdout.write(self.style.SUCCESS(
            f'Готово: {Salon.objects.count()} салона, {Master.objects.count()} мастера, '
            f'{Page.objects.count()} страницы.'
        ))
