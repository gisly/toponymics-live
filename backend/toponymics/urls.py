"""URL configuration for toponymics project."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls


urlpatterns = [
    # Django admin (для тебя как superuser)
    path("django-admin/", admin.site.urls),
    # Wagtail-админка (для контент-редакторов)
    path("cms/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    # API
    path("api/", include("apps.api.urls")),
    # Корень — пока редирект на Wagtail-админку; позже SPA будет тут
    path("", RedirectView.as_view(url="/cms/", permanent=False)),
    # Wagtail-сайт (страницы из CMS) — самый низкий приоритет
    path("pages/", include(wagtail_urls)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
