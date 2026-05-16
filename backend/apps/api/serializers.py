"""DRF serializers для API."""
from rest_framework import serializers

from apps.toponyms.models import (
    FeatureType,
    HistoricalMap,
    MediaItem,
    Region,
    Toponym,
    ToponymOnMap,
)


class RegionSerializer(serializers.ModelSerializer):
    bbox = serializers.SerializerMethodField()

    class Meta:
        model = Region
        fields = ["id", "name", "slug", "description", "bbox"]

    def get_bbox(self, obj):
        if all([obj.bbox_west, obj.bbox_south, obj.bbox_east, obj.bbox_north]):
            return [float(obj.bbox_west), float(obj.bbox_south),
                    float(obj.bbox_east), float(obj.bbox_north)]
        return None


class FeatureTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeatureType
        fields = ["id", "code", "name", "icon", "default_color", "sort_order"]


class MediaItemSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = MediaItem
        fields = ["id", "type", "file_url", "caption", "credit", "license", "created_at"]

    def get_file_url(self, obj):
        request = self.context.get("request")
        url = obj.file.url
        return request.build_absolute_uri(url) if request else url


class HistoricalMapListSerializer(serializers.ModelSerializer):
    """Лёгкий serializer для списка."""

    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = HistoricalMap
        fields = [
            "id", "title", "slug", "creator", "date_drawn",
            "region", "language", "georeference_status", "thumbnail_url",
        ]

    def get_thumbnail_url(self, obj):
        img = obj.thumbnail or obj.scanned_image
        if not img:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(img.url) if request else img.url


class HistoricalMapDetailSerializer(HistoricalMapListSerializer):
    """Полный serializer для детальной страницы."""

    scanned_image_url = serializers.SerializerMethodField()
    related_media = MediaItemSerializer(many=True, read_only=True)

    class Meta(HistoricalMapListSerializer.Meta):
        fields = HistoricalMapListSerializer.Meta.fields + [
            "description",
            "date_collected",
            "scanned_image_url",
            "georeference_data",
            "related_media",
        ]

    def get_scanned_image_url(self, obj):
        if not obj.scanned_image:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.scanned_image.url) if request else obj.scanned_image.url


class ToponymOnMapInlineSerializer(serializers.ModelSerializer):
    historical_map = HistoricalMapListSerializer(read_only=True)

    class Meta:
        model = ToponymOnMap
        fields = ["historical_map", "pixel_x", "pixel_y", "label_as_written", "note"]


class ToponymListSerializer(serializers.ModelSerializer):
    """Минимальный serializer — список + карта."""

    class Meta:
        model = Toponym
        fields = [
            "id",
            "name_ru",
            "name_evn_cyrillic",
            "name_evn_latin",
            "name_en",
            "feature_type",
            "region",
            "latitude",
            "longitude",
            "confidence",
        ]


class ToponymDetailSerializer(serializers.ModelSerializer):
    """Полный serializer для детальной страницы."""

    feature_type = FeatureTypeSerializer(read_only=True)
    region = RegionSerializer(read_only=True)
    map_positions = ToponymOnMapInlineSerializer(many=True, read_only=True)
    related_media = MediaItemSerializer(many=True, read_only=True)

    class Meta:
        model = Toponym
        fields = [
            "id",
            "name_ru",
            "name_ru_variants",
            "name_evn_cyrillic",
            "name_evn_latin",
            "name_evn_ipa",
            "name_evn_variants",
            "name_en",
            "feature_type",
            "region",
            "latitude",
            "longitude",
            "confidence",
            "etymology",
            "narrative",
            "map_positions",
            "related_media",
            "created_at",
            "updated_at",
        ]


class ToponymGeoJSONSerializer(serializers.ModelSerializer):
    """GeoJSON-формат для отображения на карте.

    Не использует DRF-gis (его нет в зависимостях), формируем GeoJSON вручную.
    """

    type = serializers.SerializerMethodField()
    geometry = serializers.SerializerMethodField()
    properties = serializers.SerializerMethodField()

    class Meta:
        model = Toponym
        fields = ["type", "geometry", "properties"]

    def get_type(self, obj):
        return "Feature"

    def get_geometry(self, obj):
        return {
            "type": "Point",
            "coordinates": [float(obj.longitude), float(obj.latitude)],
        }

    def get_properties(self, obj):
        return {
            "id": obj.id,
            "name_ru": obj.name_ru,
            "name_evn_cyrillic": obj.name_evn_cyrillic,
            "name_evn_latin": obj.name_evn_latin,
            "feature_type_id": obj.feature_type_id,
            "region_id": obj.region_id,
            "confidence": obj.confidence,
        }
