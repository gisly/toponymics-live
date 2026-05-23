"""DRF views для API топонимов."""
from django.db.models import Q
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.toponyms.models import (
    FeatureType, HistoricalMap, Language, MotivationType, Person, Place, Toponym,
)
from .serializers import (
    FeatureTypeSerializer,
    HistoricalMapDetailSerializer,
    HistoricalMapListSerializer,
    LanguageSerializer,
    MotivationTypeSerializer,
    PersonSerializer,
    ToponymDetailSerializer,
    ToponymListSerializer,
)


class LanguageViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Language.objects.all().order_by("iso")
    serializer_class = LanguageSerializer
    lookup_field = "iso"


class FeatureTypeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = FeatureType.objects.all().order_by("sort_order", "name_ru")
    serializer_class = FeatureTypeSerializer
    lookup_field = "code"


class MotivationTypeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MotivationType.objects.all().order_by("short_name_ru")
    serializer_class = MotivationTypeSerializer


class PersonViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Person.objects.all().order_by("last_name")
    serializer_class = PersonSerializer


class HistoricalMapViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = HistoricalMap.objects.select_related("author", "collector")

    def get_serializer_class(self):
        if self.action == "list":
            return HistoricalMapListSerializer
        return HistoricalMapDetailSerializer


def filter_toponyms(qs, request):
    """Применяет query-параметры фильтрации к queryset топонимов."""
    p = request.query_params

    if language := p.get("language"):
        # Поддержка multiple через запятую: ?language=evn,sah
        qs = qs.filter(language__iso__in=language.split(","))

    if feature_type := p.get("feature_type"):
        qs = qs.filter(place__feature_type__code__in=feature_type.split(","))

    if hm := p.get("historical_map"):
        qs = qs.filter(historical_map_id__in=hm.split(","))

    if motivation := p.get("motivation"):
        qs = qs.filter(motivation_id__in=motivation.split(","))

    if search := p.get("search"):
        qs = qs.filter(
            Q(name__icontains=search) |
            Q(name_latin__icontains=search) |
            Q(translation_ru__icontains=search) |
            Q(translation_en__icontains=search)
        )

    if bbox := p.get("bbox"):
        # bbox=west,south,east,north (lng/lat)
        try:
            west, south, east, north = map(float, bbox.split(","))
            qs = qs.filter(
                place__longitude__gte=west, place__longitude__lte=east,
                place__latitude__gte=south, place__latitude__lte=north,
            )
        except (ValueError, TypeError):
            pass

    if p.get("has_coords") in ("1", "true"):
        qs = qs.filter(place__latitude__isnull=False, place__longitude__isnull=False)

    return qs


class ToponymViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Toponym.objects.select_related(
        "place", "place__feature_type", "language", "motivation",
        "historical_map", "informant",
    )

    def get_serializer_class(self):
        if self.action == "list":
            return ToponymListSerializer
        return ToponymDetailSerializer

    def get_queryset(self):
        return filter_toponyms(super().get_queryset(), self.request)

    @action(detail=False, methods=["get"], url_path="geojson")
    def geojson(self, request):
        """Отдаёт топонимы как GeoJSON FeatureCollection.

        Поддерживает все те же фильтры, что list endpoint, плюс bbox.
        Возвращает только точки с координатами.
        """
        qs = self.get_queryset().filter(
            place__latitude__isnull=False,
            place__longitude__isnull=False,
        )

        features = []
        for t in qs:
            features.append({
                "type": "Feature",
                "id": t.id,
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(t.place.longitude), float(t.place.latitude)],
                },
                "properties": {
                    "id": t.id,
                    "place_id": t.place_id,
                    "name": t.name,
                    "name_latin": t.name_latin,
                    "language": t.language.iso,
                    "feature_type": t.place.feature_type.code if t.place.feature_type else None,
                    "feature_color": t.place.feature_type.default_color if t.place.feature_type else None,
                    "translation_ru": t.translation_ru,
                    "is_approximate": t.place.is_coordinates_approximate,
                    "historical_map_id": t.historical_map_id,
                },
            })
        return Response({"type": "FeatureCollection", "features": features})

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        """Сводная статистика для UI (число записей в каждой категории)."""
        qs = self.get_queryset()
        return Response({
            "total": qs.count(),
            "with_coords": qs.filter(place__latitude__isnull=False).count(),
            "by_language": {
                lang.iso: qs.filter(language=lang).count()
                for lang in Language.objects.all()
            },
        })
