"""
Google Directions API service for fetching route geometry.
"""

import requests
from django.conf import settings
from typing import Optional


class DirectionsAPIError(Exception):
    """Exception raised for Google Directions API errors."""
    pass


class GoogleDirectionsService:
    """
    Service for interacting with Google Directions API.
    
    Responsibilities:
    - Fetch route polyline between two coordinates
    - Handle API errors gracefully
    """
    
    BASE_URL = "https://maps.googleapis.com/maps/api/directions/json"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key if api_key is not None else settings.GOOGLE_MAPS_API_KEY
    
    def get_route_geometry(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float
    ) -> str:
        """
        Fetch the encoded polyline for a route between two points.
        
        Args:
            origin_lat: Origin latitude
            origin_lng: Origin longitude
            dest_lat: Destination latitude
            dest_lng: Destination longitude
            
        Returns:
            Encoded polyline string
            
        Raises:
            DirectionsAPIError: If the API request fails or no route is found
        """
        if not self.api_key:
            raise DirectionsAPIError("Google Maps API key is not configured")
        
        params = {
            'origin': f"{origin_lat},{origin_lng}",
            'destination': f"{dest_lat},{dest_lng}",
            'key': self.api_key,
            'mode': 'driving',
        }
        
        try:
            response = requests.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            raise DirectionsAPIError(f"API request failed: {str(e)}")
        
        data = response.json()
        
        if data.get('status') != 'OK':
            error_message = data.get('error_message', data.get('status', 'Unknown error'))
            raise DirectionsAPIError(f"Directions API error: {error_message}")
        
        routes = data.get('routes', [])
        if not routes:
            raise DirectionsAPIError("No route found between the specified coordinates")
        
        polyline = routes[0].get('overview_polyline', {}).get('points', '')
        if not polyline:
            raise DirectionsAPIError("No polyline data in the response")
        
        return polyline
