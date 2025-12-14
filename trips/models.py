"""
Trip model for the ride-hailing application.
"""

from django.db import models
from django.core.validators import MinValueValidator


class Trip(models.Model):
    """
    Represents a trip with route information.
    
    The route_geometry field stores an encoded polyline string
    from the Google Directions API.
    """
    
    starting_latitude = models.FloatField(
        help_text="Starting point latitude"
    )
    starting_longitude = models.FloatField(
        help_text="Starting point longitude"
    )
    destination_latitude = models.FloatField(
        help_text="Destination latitude"
    )
    destination_longitude = models.FloatField(
        help_text="Destination longitude"
    )
    route_geometry = models.TextField(
        blank=True,
        default='',
        help_text="Encoded polyline string from Google Directions API"
    )
    available_seats = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(0)],
        help_text="Number of available seats"
    )
    is_ride_requests_allowed = models.BooleanField(
        default=True,
        help_text="Whether new ride requests are allowed"
    )
    date_added = models.DateTimeField(auto_now_add=True)
    date_last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_added']
        verbose_name = 'Trip'
        verbose_name_plural = 'Trips'

    def __str__(self):
        return f"Trip {self.id}: ({self.starting_latitude}, {self.starting_longitude}) -> ({self.destination_latitude}, {self.destination_longitude})"

    @property
    def origin_coords(self) -> tuple:
        """Return origin coordinates as tuple."""
        return (self.starting_latitude, self.starting_longitude)

    @property
    def destination_coords(self) -> tuple:
        """Return destination coordinates as tuple."""
        return (self.destination_latitude, self.destination_longitude)
