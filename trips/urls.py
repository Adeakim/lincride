"""
URL configuration for the trips app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import TripViewSet, TripMatchView

router = DefaultRouter()
router.register(r'trips', TripViewSet, basename='trip')

urlpatterns = [
    path('trips/matches/', TripMatchView.as_view(), name='trip-matches'),
    path('', include(router.urls)),
]

