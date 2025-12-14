"""
Route matching service for finding suitable trips for riders.
"""

import polyline
from typing import List, Optional
from dataclasses import dataclass
from django.conf import settings

from .distance import DistanceService


@dataclass
class MatchedTrip:
    """Represents a matched trip with all required details."""
    trip_id: int
    pickup_latitude: float
    pickup_longitude: float
    dropoff_latitude: float
    dropoff_longitude: float
    pickup_distance_meters: float
    dropoff_distance_meters: float
    rider_trip_distance_meters: float
    available_seats: int
    estimated_arrival_minutes: float


class RouteMatchingService:
    """
    Service for matching riders with suitable trips.
    
    A trip qualifies as a match if:
    1. Pickup proximity: Rider's start point is within radius of any point on trip's route
    2. Dropoff proximity: Rider's destination is within radius AND after pickup along route
    3. Seat availability: Trip has at least the requested number of seats
    4. Trip eligibility: is_ride_requests_allowed is True
    """
    
    def __init__(
        self,
        radius_meters: Optional[float] = None,
        average_speed_kmh: Optional[float] = None
    ):
        self.radius_meters = radius_meters or settings.DEFAULT_MATCHING_RADIUS_METERS
        self.average_speed_kmh = average_speed_kmh or settings.DEFAULT_AVERAGE_SPEED_KMH
        self.distance_service = DistanceService()
    
    def find_matches(
        self,
        trips,  # QuerySet of Trip objects
        rider_start_lat: float,
        rider_start_lon: float,
        rider_dest_lat: float,
        rider_dest_lon: float,
        seats_required: int = 1,
    ) -> List[MatchedTrip]:
        """
        Find all trips that match the rider's journey.
        
        Args:
            trips: QuerySet of Trip objects to search
            rider_start_lat, rider_start_lon: Rider's pickup coordinates
            rider_dest_lat, rider_dest_lon: Rider's destination coordinates
            seats_required: Number of seats needed
            
        Returns:
            List of MatchedTrip objects
        """
        matches = []
        
        for trip in trips:
            match = self._evaluate_trip(
                trip,
                rider_start_lat,
                rider_start_lon,
                rider_dest_lat,
                rider_dest_lon,
                seats_required
            )
            if match:
                matches.append(match)
        
        return matches
    
    def _evaluate_trip(
        self,
        trip,
        rider_start_lat: float,
        rider_start_lon: float,
        rider_dest_lat: float,
        rider_dest_lon: float,
        seats_required: int
    ) -> Optional[MatchedTrip]:
        """
        Evaluate if a single trip matches the rider's requirements.
        
        Returns MatchedTrip if the trip is a match, None otherwise.
        """
        # Check eligibility
        if not trip.is_ride_requests_allowed:
            return None
        
        # Check seat availability
        if trip.available_seats < seats_required:
            return None
        
        # Decode route geometry
        if not trip.route_geometry:
            return None
        
        try:
            route_points = polyline.decode(trip.route_geometry)
        except Exception:
            return None
        
        if not route_points:
            return None
        
        # Find nearest point to pickup
        pickup_result = self.distance_service.find_nearest_point_on_route(
            rider_start_lat, rider_start_lon, route_points
        )
        
        if not pickup_result or pickup_result.distance_to_point > self.radius_meters:
            return None
        
        # Find nearest point to dropoff
        dropoff_result = self.distance_service.find_nearest_point_on_route(
            rider_dest_lat, rider_dest_lon, route_points
        )
        
        if not dropoff_result or dropoff_result.distance_to_point > self.radius_meters:
            return None
        
        # Ensure dropoff is after pickup along the route
        if dropoff_result.route_index <= pickup_result.route_index:
            return None
        
        # Calculate rider's trip distance along the route
        rider_trip_distance = self.distance_service.calculate_route_distance_between_points(
            route_points,
            pickup_result.route_index,
            dropoff_result.route_index
        )
        
        # Calculate ETA (distance from trip start to pickup point)
        eta_minutes = self.distance_service.calculate_eta_minutes(
            pickup_result.point.distance_from_start,
            self.average_speed_kmh
        )
        
        return MatchedTrip(
            trip_id=trip.id,
            pickup_latitude=pickup_result.point.latitude,
            pickup_longitude=pickup_result.point.longitude,
            dropoff_latitude=dropoff_result.point.latitude,
            dropoff_longitude=dropoff_result.point.longitude,
            pickup_distance_meters=pickup_result.distance_to_point,
            dropoff_distance_meters=dropoff_result.distance_to_point,
            rider_trip_distance_meters=rider_trip_distance,
            available_seats=trip.available_seats,
            estimated_arrival_minutes=round(eta_minutes, 2)
        )

