from django.apps import AppConfig


class ServicesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'services'
    verbose_name = 'Услуги и цены'

    def ready(self):
        from . import signals  # noqa: F401
