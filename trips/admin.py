"""
Admin configuration for the trips app.
"""

from django.contrib import admin
from .models import Trip


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'starting_latitude',
        'starting_longitude',
        'destination_latitude',
        'destination_longitude',
        'available_seats',
        'is_ride_requests_allowed',
        'date_added',
    ]
    list_filter = ['is_ride_requests_allowed', 'date_added']
    search_fields = ['id']
    readonly_fields = ['date_added', 'date_last_updated', 'route_geometry']
    ordering = ['-date_added']
