"""
WebSocket URL routing for the trips app.
"""

from django.urls import re_path
from .consumers import TripLocationConsumer

websocket_urlpatterns = [
    re_path(r'ws/trip-location/$', TripLocationConsumer.as_asgi()),
]

