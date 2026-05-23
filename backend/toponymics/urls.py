"""URL configuration for toponymics project.

Без префиксов языка:
- /django-admin/  — Django admin (для superuser)
- /cms/           — Wagtail-админка для редакторов
- /documents/     — Wagtail-документы
- /api/           — DRF API для топонимов
- /pmtiles/<file> — pmtiles-тайлы карты (большие файлы, мимо staticfiles)
- /map-style/<file>.json — JSON стиля MapLibre (с подменой PMTILES_URL)

С префиксами /ru/ или /en/:
- /ru/            — главная (русская)
- /en/            — главная (английская)
- /ru/o-proekte/  — раздел/статья (рендер через Wagtail)
- /ru/o-proekte/kontakty/ — подстраница

Без префикса URL автоматически редиректит на язык, определённый по Accept-Language.
"""
from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls

from apps.content.views import serve_pmtiles, serve_map_style


# URL без языковых префиксов
urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("cms/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    path("api/", include("apps.api.urls")),
    # Ассеты карты — раздаются мимо staticfiles
    re_path(r"^pmtiles/(?P<path>.+)$", serve_pmtiles),
    path("map-style/<str:filename>", serve_map_style),
]

# Wagtail-страницы — с префиксами языка
urlpatterns += i18n_patterns(
    path("", include(wagtail_urls)),
    prefix_default_language=True,  # /ru/ всегда виден, не "по умолчанию"
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
