from django.apps import AppConfig


class OrganizationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.organizations'

    def ready(self):
        from apps.organizations import signals  # noqa: F401
