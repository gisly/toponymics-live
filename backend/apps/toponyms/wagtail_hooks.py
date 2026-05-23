"""Регистрация моделей topyms как Wagtail Snippets.

Snippet'ы — это объекты, доступные в Wagtail-админке через раздел "Snippets".
Это удобный способ показать справочники и контентные модели редакторам.
"""
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup

from .models import (
    FeatureType,
    GeoSystem,
    HistoricalMap,
    Language,
    MotivationType,
    Narration,
    NarrationTranslation,
    Person,
    Place,
    SourceReference,
    Toponym,
)


# ─── Группировка в админке ───────────────────────────────────────────


class LanguageViewSet(SnippetViewSet):
    model = Language
    icon = "globe"
    list_display = ["iso", "name_ru", "name_en", "name_native"]
    search_fields = ["iso", "name_ru", "name_en"]


class FeatureTypeViewSet(SnippetViewSet):
    model = FeatureType
    icon = "tag"
    list_display = ["code", "name_ru", "name_en", "language", "sort_order"]
    list_filter = ["language"]
    search_fields = ["code", "name_ru", "name_en"]


class MotivationTypeViewSet(SnippetViewSet):
    model = MotivationType
    icon = "openquote"
    list_display = ["short_name_ru", "short_name_en"]
    search_fields = ["short_name_ru", "short_name_en"]


class SourceReferenceViewSet(SnippetViewSet):
    model = SourceReference
    icon = "doc-full"
    list_display = ["__str__"]
    search_fields = ["description"]


class PersonViewSet(SnippetViewSet):
    model = Person
    icon = "user"
    list_display = ["last_name", "first_name", "patronymic"]
    search_fields = ["last_name", "first_name", "patronymic"]


class GeoSystemViewSet(SnippetViewSet):
    model = GeoSystem
    icon = "site"
    list_display = ["name_ru", "name_en"]
    search_fields = ["name_ru", "name_en"]


class HistoricalMapViewSet(SnippetViewSet):
    model = HistoricalMap
    icon = "image"
    list_display = ["area_name_ru", "author", "collector", "is_archive"]
    list_filter = ["is_archive", "geo_systems"]
    search_fields = ["area_name_ru", "area_name_en", "place_collected"]


class PlaceViewSet(SnippetViewSet):
    model = Place
    icon = "site"
    list_display = ["__str__", "feature_type", "is_coordinates_approximate", "date_added"]
    list_filter = ["feature_type", "is_coordinates_approximate", "historical_map"]
    search_fields = ["location_comment", "osm_id"]


class ToponymViewSet(SnippetViewSet):
    model = Toponym
    icon = "tag"
    list_display = ["name", "language", "translation_ru", "motivation", "historical_map"]
    list_filter = ["language", "motivation", "historical_map"]
    search_fields = ["name", "name_latin", "translation_ru", "translation_en"]


class NarrationViewSet(SnippetViewSet):
    model = Narration
    icon = "openquote"
    list_display = ["__str__", "narrator", "place", "language_original"]
    list_filter = ["language_original"]
    search_fields = ["text_original"]


class NarrationTranslationViewSet(SnippetViewSet):
    model = NarrationTranslation
    icon = "openquote"
    list_display = ["narration", "language"]
    list_filter = ["language"]


class ToponymyViewSetGroup(SnippetViewSetGroup):
    """Группа «Топонимика» — собирает все модели в одно меню."""

    menu_label = "Топонимика"
    menu_icon = "site"
    menu_order = 200
    items = (
        # Основные сущности — сверху
        ToponymViewSet,
        PlaceViewSet,
        HistoricalMapViewSet,
        # Нарративы
        NarrationViewSet,
        NarrationTranslationViewSet,
        # Справочники — внизу
        LanguageViewSet,
        FeatureTypeViewSet,
        MotivationTypeViewSet,
        SourceReferenceViewSet,
        PersonViewSet,
        GeoSystemViewSet,
    )


register_snippet(ToponymyViewSetGroup)
