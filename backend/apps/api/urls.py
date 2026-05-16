"""API URL routing."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    FeatureTypeViewSet,
    HistoricalMapViewSet,
    MediaItemViewSet,
    RegionViewSet,
    ToponymViewSet,
)

router = DefaultRouter()
router.register(r"regions", RegionViewSet, basename="region")
router.register(r"feature-types", FeatureTypeViewSet, basename="feature-type")
router.register(r"media", MediaItemViewSet, basename="media")
router.register(r"historical-maps", HistoricalMapViewSet, basename="historical-map")
router.register(r"toponyms", ToponymViewSet, basename="toponym")

urlpatterns = [
    path("", include(router.urls)),
]
