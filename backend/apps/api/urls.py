"""API URL routing."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    FeatureTypeViewSet,
    HistoricalMapViewSet,
    LanguageViewSet,
    MotivationTypeViewSet,
    PersonViewSet,
    ToponymViewSet,
)

router = DefaultRouter()
router.register(r"languages", LanguageViewSet, basename="language")
router.register(r"feature-types", FeatureTypeViewSet, basename="feature-type")
router.register(r"motivations", MotivationTypeViewSet, basename="motivation")
router.register(r"persons", PersonViewSet, basename="person")
router.register(r"historical-maps", HistoricalMapViewSet, basename="historical-map")
router.register(r"toponyms", ToponymViewSet, basename="toponym")

urlpatterns = [
    path("", include(router.urls)),
]
