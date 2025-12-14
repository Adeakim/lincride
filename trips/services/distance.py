"""
Distance calculation utilities using the Haversine formula.
"""

import math
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class RoutePoint:
    """Represents a point on a route with its position along the route."""
    latitude: float
    longitude: float
    distance_from_start: float  # meters from the start of the route


@dataclass
class NearestPointResult:
    """Result of finding the nearest point on a route."""
    point: RoutePoint
    distance_to_point: float  # meters from the query point to this route point
    route_index: int  # index in the decoded route


class DistanceService:
    """
    Service for distance and ETA calculations.
    
    Uses the Haversine formula for calculating distances between coordinates.
    """
    
    EARTH_RADIUS_METERS = 6371000  # Earth's radius in meters
    
    @staticmethod
    def haversine_distance(
        lat1: float, lon1: float,
        lat2: float, lon2: float
    ) -> float:
        """
        Calculate the distance between two points on Earth using Haversine formula.
        
        Args:
            lat1, lon1: First point coordinates
            lat2, lon2: Second point coordinates
            
        Returns:
            Distance in meters
        """
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return DistanceService.EARTH_RADIUS_METERS * c
    
    @classmethod
    def find_nearest_point_on_route(
        cls,
        query_lat: float,
        query_lon: float,
        route_points: List[Tuple[float, float]]
    ) -> Optional[NearestPointResult]:
        """
        Find the nearest point on a route to a given query point.
        
        Args:
            query_lat, query_lon: The query point coordinates
            route_points: List of (lat, lon) tuples representing the route
            
        Returns:
            NearestPointResult or None if route is empty
        """
        if not route_points:
            return None
        
        min_distance = float('inf')
        nearest_index = 0
        cumulative_distance = 0.0
        distances_from_start = [0.0]
        
        # Calculate cumulative distances along the route
        for i in range(1, len(route_points)):
            prev_lat, prev_lon = route_points[i - 1]
            curr_lat, curr_lon = route_points[i]
            segment_distance = cls.haversine_distance(prev_lat, prev_lon, curr_lat, curr_lon)
            cumulative_distance += segment_distance
            distances_from_start.append(cumulative_distance)
        
        # Find the nearest point
        for i, (lat, lon) in enumerate(route_points):
            distance = cls.haversine_distance(query_lat, query_lon, lat, lon)
            if distance < min_distance:
                min_distance = distance
                nearest_index = i
        
        nearest_lat, nearest_lon = route_points[nearest_index]
        
        return NearestPointResult(
            point=RoutePoint(
                latitude=nearest_lat,
                longitude=nearest_lon,
                distance_from_start=distances_from_start[nearest_index]
            ),
            distance_to_point=min_distance,
            route_index=nearest_index
        )
    
    @classmethod
    def calculate_route_distance_between_points(
        cls,
        route_points: List[Tuple[float, float]],
        start_index: int,
        end_index: int
    ) -> float:
        """
        Calculate the distance along a route between two indices.
        
        Args:
            route_points: List of (lat, lon) tuples
            start_index: Starting index
            end_index: Ending index
            
        Returns:
            Distance in meters along the route
        """
        if start_index >= end_index:
            return 0.0
        
        total_distance = 0.0
        for i in range(start_index, end_index):
            lat1, lon1 = route_points[i]
            lat2, lon2 = route_points[i + 1]
            total_distance += cls.haversine_distance(lat1, lon1, lat2, lon2)
        
        return total_distance
    
    @staticmethod
    def calculate_eta_minutes(distance_meters: float, speed_kmh: float = 30.0) -> float:
        """
        Calculate estimated time of arrival.
        
        Args:
            distance_meters: Distance in meters
            speed_kmh: Average speed in km/h (default 30)
            
        Returns:
            ETA in minutes
        """
        if speed_kmh <= 0:
            return 0.0
        
        speed_mpm = (speed_kmh * 1000) / 60  # meters per minute
        return distance_meters / speed_mpm

