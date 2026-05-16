"""Wagtail snippets и viewsets для топонимов.

Snippets — это то, как Wagtail-админка покажет наши не-Page модели:
Toponym, HistoricalMap, Region, FeatureType, MediaItem.
"""
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from .models import FeatureType, HistoricalMap, MediaItem, Region, Toponym


@register_snippet
class RegionViewSet(SnippetViewSet):
    model = Region
    icon = "globe"
    menu_label = "Регионы"
    menu_order = 100
    list_display = ["name", "slug"]
    search_fields = ["name"]


@register_snippet
class FeatureTypeViewSet(SnippetViewSet):
    model = FeatureType
    icon = "tag"
    menu_label = "Типы объектов"
    menu_order = 110
    list_display = ["name", "code", "sort_order"]
    search_fields = ["name", "code"]


@register_snippet
class MediaItemViewSet(SnippetViewSet):
    model = MediaItem
    icon = "image"
    menu_label = "Медиа"
    menu_order = 120
    list_display = ["caption", "type", "credit", "created_at"]
    list_filter = ["type"]
    search_fields = ["caption", "credit"]


@register_snippet
class HistoricalMapViewSet(SnippetViewSet):
    model = HistoricalMap
    icon = "site"
    menu_label = "Рукописные карты"
    menu_order = 200
    list_display = ["title", "creator", "date_drawn", "region", "georeference_status"]
    list_filter = ["region", "georeference_status", "language"]
    search_fields = ["title", "creator"]


@register_snippet
class ToponymViewSet(SnippetViewSet):
    model = Toponym
    icon = "pin"
    menu_label = "Топонимы"
    menu_order = 210
    list_display = [
        "name_ru",
        "name_evn_cyrillic",
        "feature_type",
        "region",
        "confidence",
    ]
    list_filter = ["feature_type", "region", "confidence"]
    search_fields = [
        "name_ru",
        "name_evn_cyrillic",
        "name_evn_latin",
        "name_en",
    ]
