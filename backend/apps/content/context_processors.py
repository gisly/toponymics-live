"""Контекстные процессоры для шаблонов."""
from django.conf import settings


def site_meta(request):
    """Делает WAGTAIL_SITE_NAME и т.п. доступными во всех шаблонах."""
    return {
        "WAGTAIL_SITE_NAME": getattr(settings, "WAGTAIL_SITE_NAME", "Топонимика"),
    }
