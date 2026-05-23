"""DRF сериализаторы для API топонимов."""
from rest_framework import serializers

from apps.toponyms.models import (
    FeatureType,
    HistoricalMap,
    Language,
    MotivationType,
    Person,
    Place,
    Toponym,
)


class LanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Language
        fields = ["iso", "name_ru", "name_en", "name_native"]


class FeatureTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeatureType
        fields = ["code", "name_ru", "name_en", "icon", "default_color", "sort_order"]


class MotivationTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MotivationType
        fields = ["id", "short_name_ru", "short_name_en", "comment_ru", "comment_en"]


class PersonSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()
    class Meta:
        model = Person
        fields = ["id", "full_name", "comment"]


class HistoricalMapListSerializer(serializers.ModelSerializer):
    author = PersonSerializer(read_only=True)
    collector = PersonSerializer(read_only=True)
    toponym_count = serializers.SerializerMethodField()

    class Meta:
        model = HistoricalMap
        fields = ["id", "area_name_ru", "area_name_en", "author", "collector",
                  "is_archive", "scanned_image", "image_link", "toponym_count"]

    def get_toponym_count(self, obj):
        return obj.toponyms.count()


class HistoricalMapDetailSerializer(HistoricalMapListSerializer):
    class Meta(HistoricalMapListSerializer.Meta):
        fields = HistoricalMapListSerializer.Meta.fields + [
            "place_collected", "comment_collected_ru", "comment_collected_en",
            "date_collected", "map_latitude", "map_longitude",
        ]


class ToponymListSerializer(serializers.ModelSerializer):
    """Короткий формат для списков."""
    language = serializers.CharField(source="language.iso", read_only=True)
    feature_type = serializers.CharField(source="place.feature_type.code", read_only=True)
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()

    class Meta:
        model = Toponym
        fields = ["id", "name", "name_latin", "language", "translation_ru",
                  "translation_en", "feature_type", "latitude", "longitude"]

    def get_latitude(self, obj):
        return float(obj.place.latitude) if obj.place.latitude else None

    def get_longitude(self, obj):
        return float(obj.place.longitude) if obj.place.longitude else None


class ToponymDetailSerializer(serializers.ModelSerializer):
    """Полный формат для попапа карты и детальной страницы."""
    language = LanguageSerializer(read_only=True)
    feature_type = FeatureTypeSerializer(source="place.feature_type", read_only=True)
    motivation = MotivationTypeSerializer(read_only=True)
    informant = PersonSerializer(read_only=True)
    historical_map = HistoricalMapListSerializer(read_only=True)
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    is_coordinates_approximate = serializers.BooleanField(
        source="place.is_coordinates_approximate", read_only=True,
    )
    location_comment = serializers.CharField(source="place.location_comment", read_only=True)
    # Все имена этого же места
    other_names = serializers.SerializerMethodField()

    class Meta:
        model = Toponym
        fields = [
            "id", "name", "name_latin", "name_ipa",
            "language", "feature_type",
            "translation_ru", "translation_en",
            "motivation", "motivation_comment", "linguistic_means",
            "informant", "historical_map", "number_on_map",
            "alternative_forms",
            "latitude", "longitude", "is_coordinates_approximate",
            "location_comment", "other_names",
        ]

    def get_latitude(self, obj):
        return float(obj.place.latitude) if obj.place.latitude else None

    def get_longitude(self, obj):
        return float(obj.place.longitude) if obj.place.longitude else None

    def get_other_names(self, obj):
        others = obj.place.toponyms.exclude(id=obj.id)
        return [
            {"id": t.id, "name": t.name, "language": t.language.iso,
             "translation_ru": t.translation_ru}
            for t in others
        ]
