"""DRF views для API."""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.toponyms.models import FeatureType, HistoricalMap, MediaItem, Region, Toponym

from .serializers import (
    FeatureTypeSerializer,
    HistoricalMapDetailSerializer,
    HistoricalMapListSerializer,
    MediaItemSerializer,
    RegionSerializer,
    ToponymDetailSerializer,
    ToponymGeoJSONSerializer,
    ToponymListSerializer,
)


class RegionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Region.objects.all()
    serializer_class = RegionSerializer
    lookup_field = "slug"


class FeatureTypeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = FeatureType.objects.all().order_by("sort_order", "name")
    serializer_class = FeatureTypeSerializer


class MediaItemViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MediaItem.objects.all()
    serializer_class = MediaItemSerializer
    filterset_fields = ["type"]


class HistoricalMapViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = HistoricalMap.objects.select_related("region")
    lookup_field = "slug"
    filterset_fields = ["region", "language", "georeference_status"]
    search_fields = ["title", "creator"]

    def get_serializer_class(self):
        if self.action == "list":
            return HistoricalMapListSerializer
        return HistoricalMapDetailSerializer


class ToponymViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Toponym.objects.select_related("feature_type", "region")
    filterset_fields = ["feature_type", "region", "confidence"]
    search_fields = [
        "name_ru",
        "name_evn_cyrillic",
        "name_evn_latin",
        "name_en",
    ]

    def get_serializer_class(self):
        if self.action == "list":
            return ToponymListSerializer
        return ToponymDetailSerializer

    @action(detail=False, methods=["get"], url_path="geojson")
    def geojson(self, request):
        """Отдаёт ВСЕ топонимы как FeatureCollection в GeoJSON.

        До 1000 точек — это легко в один HTTP ответ.
        Поддерживает те же фильтры query-параметрами: ?region=1&feature_type=2
        """
        qs = self.filter_queryset(self.get_queryset())
        features = ToponymGeoJSONSerializer(qs, many=True).data
        return Response({
            "type": "FeatureCollection",
            "features": features,
        })
