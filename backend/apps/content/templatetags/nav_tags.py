"""
Шаблонные теги для построения навигации:
- main_menu — главное меню (дети HomePage верхнего уровня, кроме футерных)
- footer_links — ссылки в футер (страницы с NOTES=Footer-ссылка)
- language_switcher — переключатель языков
- site_root — корневая HomePage текущего языка
"""
from django import template
from django.urls import translate_url
from django.utils.translation import get_language
from wagtail.models import Locale, Page, Site

from apps.content.models import ArticlePage, HomePage, ProjectPage

register = template.Library()


@register.simple_tag(takes_context=True)
def site_root(context):
    """Возвращает корневую HomePage текущего языка."""
    request = context.get("request")
    if request:
        site = Site.find_for_request(request)
        if site:
            root = site.root_page
            # Если root указывает на дефолтную локаль, ищем перевод на текущий язык
            current_locale = _get_current_locale()
            if root.locale != current_locale:
                try:
                    return root.get_translation(current_locale).specific
                except Page.DoesNotExist:
                    pass
            return root.specific
    return HomePage.objects.live().first()


@register.inclusion_tag("includes/main_menu.html", takes_context=True)
def main_menu(context, current_page=None):
    """Главное меню: дети HomePage, в текущем языке."""
    root = site_root(context)
    if not root:
        return {"items": [], "current_page": current_page}

    # Берём опубликованные дочки HomePage, отсортированные по path (== sort_order в дереве)
    children = (
        root.get_children()
        .live()
        .in_menu()  # это поле Wagtail "show in menu" в admin
        .specific()
    )

    # Если страница помечена в NOTES как footer-ссылка — в главное меню не идёт
    items = []
    for child in children:
        # Простая эвристика — статья "Политика обработки..." (id=33) идёт в футер.
        # При желании можно сделать кастомное поле в моделях. Пока: по title/slug.
        if _is_footer_only(child):
            continue
        items.append(child)

    return {"items": items, "current_page": current_page}


@register.inclusion_tag("includes/footer_links.html", takes_context=True)
def footer_links(context):
    """Ссылки в футер — страницы, помеченные как footer-only."""
    root = site_root(context)
    if not root:
        return {"items": []}

    items = [
        child for child in root.get_children().live().specific()
        if _is_footer_only(child)
    ]
    return {"items": items}


@register.inclusion_tag("includes/language_switcher.html", takes_context=True)
def language_switcher(context):
    """Переключатель языков: на той же странице, но в другой локали."""
    request = context.get("request")
    page = context.get("page")
    current_lang = get_language() or "ru"

    languages = []
    for locale in Locale.objects.all():
        url = None
        if page and hasattr(page, "get_translation"):
            try:
                translated = page.get_translation(locale)
                if translated.live:
                    url = translated.url
            except Page.DoesNotExist:
                pass
        # Если страницы в этом языке нет — ссылку на корень того языка
        if not url:
            # Корень в нужной локали
            try:
                root_translation = (
                    Site.find_for_request(request).root_page.get_translation(locale)
                    if request else None
                )
                url = root_translation.url if root_translation else f"/{locale.language_code}/"
            except (Page.DoesNotExist, AttributeError):
                url = f"/{locale.language_code}/"

        languages.append({
            "code": locale.language_code,
            "label": locale.language_code.upper(),
            "name": _LANGUAGE_NAMES.get(locale.language_code, locale.language_code),
            "url": url,
            "is_current": locale.language_code == current_lang,
        })

    return {"languages": languages}


# ─── Утилиты ──────────────────────────────────────────────────────────


_LANGUAGE_NAMES = {
    "ru": "Русский",
    "en": "English",
    "evn": "Эвэды̄ турэ̄н",
}

_FOOTER_SLUG_HINTS = {
    "politika-v-otnoshenii-obrabotki-perso",
    "politika",
    "policy",
    "pravila-ispolzovaniya-sayta",
    "terms",
}


def _is_footer_only(page) -> bool:
    """Грубая эвристика. Можно потом заменить на поле модели."""
    return page.slug in _FOOTER_SLUG_HINTS


def _get_current_locale():
    code = get_language() or "ru"
    # Wagtail-localize может хотеть основу 'ru', а Django настройка — 'ru-ru'
    try:
        return Locale.objects.get(language_code=code)
    except Locale.DoesNotExist:
        base = code.split("-")[0]
        return Locale.objects.filter(language_code=base).first() or Locale.objects.first()
