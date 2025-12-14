"""
Serializers for the trips API.
"""

from rest_framework import serializers
from .models import Trip


class TripSerializer(serializers.ModelSerializer):
    """Serializer for Trip model - used for list and retrieve operations."""
    
    class Meta:
        model = Trip
        fields = [
            'id',
            'starting_latitude',
            'starting_longitude',
            'destination_latitude',
            'destination_longitude',
            'route_geometry',
            'available_seats',
            'is_ride_requests_allowed',
            'date_added',
            'date_last_updated',
        ]
        read_only_fields = ['id', 'route_geometry', 'date_added', 'date_last_updated']


class TripCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a new trip."""
    
    class Meta:
        model = Trip
        fields = [
            'starting_latitude',
            'starting_longitude',
            'destination_latitude',
            'destination_longitude',
            'available_seats',
            'is_ride_requests_allowed',
        ]
    
    def validate_starting_latitude(self, value):
        if not -90 <= value <= 90:
            raise serializers.ValidationError("Latitude must be between -90 and 90")
        return value
    
    def validate_starting_longitude(self, value):
        if not -180 <= value <= 180:
            raise serializers.ValidationError("Longitude must be between -180 and 180")
        return value
    
    def validate_destination_latitude(self, value):
        if not -90 <= value <= 90:
            raise serializers.ValidationError("Latitude must be between -90 and 90")
        return value
    
    def validate_destination_longitude(self, value):
        if not -180 <= value <= 180:
            raise serializers.ValidationError("Longitude must be between -180 and 180")
        return value


class TripUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating a trip."""
    
    class Meta:
        model = Trip
        fields = [
            'starting_latitude',
            'starting_longitude',
            'destination_latitude',
            'destination_longitude',
            'available_seats',
            'is_ride_requests_allowed',
        ]
        extra_kwargs = {
            'starting_latitude': {'required': False},
            'starting_longitude': {'required': False},
            'destination_latitude': {'required': False},
            'destination_longitude': {'required': False},
            'available_seats': {'required': False},
            'is_ride_requests_allowed': {'required': False},
        }


class MatchQuerySerializer(serializers.Serializer):
    """Serializer for route matching query parameters."""
    
    starting_latitude = serializers.FloatField(required=True)
    starting_longitude = serializers.FloatField(required=True)
    destination_latitude = serializers.FloatField(required=True)
    destination_longitude = serializers.FloatField(required=True)
    no_of_seats_required = serializers.IntegerField(default=1, min_value=1)
    intersection_radius_meters = serializers.FloatField(default=500, min_value=0)
    
    def validate_starting_latitude(self, value):
        if not -90 <= value <= 90:
            raise serializers.ValidationError("Latitude must be between -90 and 90")
        return value
    
    def validate_starting_longitude(self, value):
        if not -180 <= value <= 180:
            raise serializers.ValidationError("Longitude must be between -180 and 180")
        return value
    
    def validate_destination_latitude(self, value):
        if not -90 <= value <= 90:
            raise serializers.ValidationError("Latitude must be between -90 and 90")
        return value
    
    def validate_destination_longitude(self, value):
        if not -180 <= value <= 180:
            raise serializers.ValidationError("Longitude must be between -180 and 180")
        return value


class MatchedTripSerializer(serializers.Serializer):
    """Serializer for matched trip results."""
    
    trip_id = serializers.IntegerField()
    pickup_latitude = serializers.FloatField()
    pickup_longitude = serializers.FloatField()
    dropoff_latitude = serializers.FloatField()
    dropoff_longitude = serializers.FloatField()
    pickup_distance_meters = serializers.FloatField()
    dropoff_distance_meters = serializers.FloatField()
    rider_trip_distance_meters = serializers.FloatField()
    available_seats = serializers.IntegerField()
    estimated_arrival_minutes = serializers.FloatField()


class MatchResponseSerializer(serializers.Serializer):
    """Serializer for the complete match response."""
    
    total_matches = serializers.IntegerField()
    matches = MatchedTripSerializer(many=True)

