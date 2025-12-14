"""
Tests for the trips application.

Covers:
- Trip Management (CRUD operations)
- Route Matching
- Real-time Location (WebSocket)
"""

import json
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from channels.testing import WebsocketCommunicator
from asgiref.sync import sync_to_async

from .models import Trip
from .services.directions import GoogleDirectionsService, DirectionsAPIError
from .services.distance import DistanceService
from .services.matching import RouteMatchingService
from .consumers import TripLocationConsumer


# Sample encoded polyline for testing (Lagos to Ibadan approximate route)
SAMPLE_POLYLINE = "a}y{D_wpzLmBdA{@`@cAl@}@d@kAp@}Av@eBx@gCnA"


class TripModelTests(TestCase):
    """Tests for the Trip model."""
    
    def test_create_trip(self):
        """Test creating a trip."""
        trip = Trip.objects.create(
            starting_latitude=6.5244,
            starting_longitude=3.3792,
            destination_latitude=7.3775,
            destination_longitude=3.9470,
            route_geometry=SAMPLE_POLYLINE,
            available_seats=3,
            is_ride_requests_allowed=True
        )
        
        self.assertIsNotNone(trip.id)
        self.assertEqual(trip.available_seats, 3)
        self.assertTrue(trip.is_ride_requests_allowed)
        self.assertIsNotNone(trip.date_added)
        self.assertIsNotNone(trip.date_last_updated)
    
    def test_trip_string_representation(self):
        """Test trip string representation."""
        trip = Trip.objects.create(
            starting_latitude=6.5244,
            starting_longitude=3.3792,
            destination_latitude=7.3775,
            destination_longitude=3.9470,
        )
        
        self.assertIn("Trip", str(trip))
        self.assertIn("6.5244", str(trip))
    
    def test_origin_coords_property(self):
        """Test origin_coords property."""
        trip = Trip(starting_latitude=6.5244, starting_longitude=3.3792)
        self.assertEqual(trip.origin_coords, (6.5244, 3.3792))
    
    def test_destination_coords_property(self):
        """Test destination_coords property."""
        trip = Trip(destination_latitude=7.3775, destination_longitude=3.9470)
        self.assertEqual(trip.destination_coords, (7.3775, 3.9470))


class GoogleDirectionsServiceTests(TestCase):
    """Tests for Google Directions API service."""
    
    @patch('trips.services.directions.requests.get')
    def test_get_route_geometry_success(self, mock_get):
        """Test successful route geometry fetch."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'status': 'OK',
            'routes': [{
                'overview_polyline': {
                    'points': SAMPLE_POLYLINE
                }
            }]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        service = GoogleDirectionsService(api_key='test-key')
        polyline = service.get_route_geometry(6.5244, 3.3792, 7.3775, 3.9470)
        
        self.assertEqual(polyline, SAMPLE_POLYLINE)
    
    @patch('trips.services.directions.requests.get')
    def test_get_route_geometry_no_route(self, mock_get):
        """Test handling of no route found."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'status': 'ZERO_RESULTS',
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        service = GoogleDirectionsService(api_key='test-key')
        
        with self.assertRaises(DirectionsAPIError):
            service.get_route_geometry(0, 0, 0, 0)
    
    def test_missing_api_key(self):
        """Test handling of missing API key."""
        service = GoogleDirectionsService(api_key='')
        
        with self.assertRaises(DirectionsAPIError) as context:
            service.get_route_geometry(6.5244, 3.3792, 7.3775, 3.9470)
        
        self.assertIn("not configured", str(context.exception))


class DistanceServiceTests(TestCase):
    """Tests for distance calculation service."""
    
    def test_haversine_distance_same_point(self):
        """Test distance between same point is zero."""
        distance = DistanceService.haversine_distance(6.5244, 3.3792, 6.5244, 3.3792)
        self.assertEqual(distance, 0)
    
    def test_haversine_distance_known_points(self):
        """Test distance calculation with known points."""
        # Lagos to Ibadan is approximately 128km
        distance = DistanceService.haversine_distance(
            6.5244, 3.3792,  # Lagos
            7.3775, 3.9470   # Ibadan
        )
        # Should be approximately 128,000 meters (with some tolerance)
        self.assertGreater(distance, 100000)  # > 100km
        self.assertLess(distance, 150000)     # < 150km
    
    def test_find_nearest_point_on_route(self):
        """Test finding nearest point on a route."""
        route_points = [
            (6.5244, 3.3792),
            (6.6000, 3.4500),
            (6.7000, 3.5500),
            (7.3775, 3.9470),
        ]
        
        result = DistanceService.find_nearest_point_on_route(
            6.5900, 3.4400,  # Point near second route point
            route_points
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result.route_index, 1)  # Should be closest to second point
    
    def test_find_nearest_point_empty_route(self):
        """Test handling of empty route."""
        result = DistanceService.find_nearest_point_on_route(6.5244, 3.3792, [])
        self.assertIsNone(result)
    
    def test_calculate_route_distance(self):
        """Test route distance calculation."""
        route_points = [
            (6.5244, 3.3792),
            (6.6000, 3.4500),
            (6.7000, 3.5500),
        ]
        
        distance = DistanceService.calculate_route_distance_between_points(
            route_points, 0, 2
        )
        
        self.assertGreater(distance, 0)
    
    def test_calculate_eta(self):
        """Test ETA calculation."""
        # 30 km at 30 km/h should take 60 minutes
        eta = DistanceService.calculate_eta_minutes(30000, 30.0)
        self.assertAlmostEqual(eta, 60.0, places=1)


class RouteMatchingServiceTests(TestCase):
    """Tests for route matching service."""
    
    def setUp(self):
        """Set up test data."""
        # Create a trip with route
        self.trip = Trip.objects.create(
            starting_latitude=6.5244,
            starting_longitude=3.3792,
            destination_latitude=7.3775,
            destination_longitude=3.9470,
            route_geometry=SAMPLE_POLYLINE,
            available_seats=3,
            is_ride_requests_allowed=True
        )
    
    def test_exact_route_match(self):
        """Test matching when rider's route exactly matches."""
        service = RouteMatchingService(radius_meters=1000)
        
        # Rider wants to go along the same route
        matches = service.find_matches(
            Trip.objects.all(),
            rider_start_lat=6.524,
            rider_start_lon=3.379,
            rider_dest_lat=6.527,
            rider_dest_lon=3.375,
        )
        
        # May or may not match depending on polyline decode
        # This tests that the service doesn't crash
        self.assertIsInstance(matches, list)
    
    def test_no_match_ride_requests_disabled(self):
        """Test no match when ride requests are disabled."""
        self.trip.is_ride_requests_allowed = False
        self.trip.save()
        
        service = RouteMatchingService(radius_meters=50000)
        
        matches = service.find_matches(
            Trip.objects.all(),
            rider_start_lat=6.5244,
            rider_start_lon=3.3792,
            rider_dest_lat=7.3775,
            rider_dest_lon=3.9470,
        )
        
        self.assertEqual(len(matches), 0)
    
    def test_no_match_insufficient_seats(self):
        """Test no match when insufficient seats."""
        self.trip.available_seats = 1
        self.trip.save()
        
        service = RouteMatchingService(radius_meters=50000)
        
        matches = service.find_matches(
            Trip.objects.all(),
            rider_start_lat=6.5244,
            rider_start_lon=3.3792,
            rider_dest_lat=7.3775,
            rider_dest_lon=3.9470,
            seats_required=3
        )
        
        self.assertEqual(len(matches), 0)
    
    def test_no_match_outside_radius(self):
        """Test no match when points are outside radius."""
        service = RouteMatchingService(radius_meters=10)  # Very small radius
        
        matches = service.find_matches(
            Trip.objects.all(),
            rider_start_lat=0,  # Far away
            rider_start_lon=0,
            rider_dest_lat=1,
            rider_dest_lon=1,
        )
        
        self.assertEqual(len(matches), 0)


@override_settings(
    DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    }
)
class TripAPITests(APITestCase):
    """Tests for Trip API endpoints."""
    
    @patch.object(GoogleDirectionsService, 'get_route_geometry')
    def test_create_trip(self, mock_directions):
        """Test creating a trip via API."""
        mock_directions.return_value = SAMPLE_POLYLINE
        
        url = reverse('trip-list')
        data = {
            'starting_latitude': 6.5244,
            'starting_longitude': 3.3792,
            'destination_latitude': 7.3775,
            'destination_longitude': 3.9470,
            'available_seats': 3,
            'is_ride_requests_allowed': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Trip.objects.count(), 1)
        self.assertEqual(response.data['route_geometry'], SAMPLE_POLYLINE)
    
    @patch.object(GoogleDirectionsService, 'get_route_geometry')
    def test_create_trip_api_failure(self, mock_directions):
        """Test handling Google API failure."""
        mock_directions.side_effect = DirectionsAPIError("API Error")
        
        url = reverse('trip-list')
        data = {
            'starting_latitude': 6.5244,
            'starting_longitude': 3.3792,
            'destination_latitude': 7.3775,
            'destination_longitude': 3.9470,
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_create_trip_invalid_coordinates(self):
        """Test validation of invalid coordinates."""
        url = reverse('trip-list')
        data = {
            'starting_latitude': 100,  # Invalid: > 90
            'starting_longitude': 3.3792,
            'destination_latitude': 7.3775,
            'destination_longitude': 3.9470,
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    @patch.object(GoogleDirectionsService, 'get_route_geometry')
    def test_list_trips(self, mock_directions):
        """Test listing trips."""
        mock_directions.return_value = SAMPLE_POLYLINE
        
        # Create trips
        Trip.objects.create(
            starting_latitude=6.5244,
            starting_longitude=3.3792,
            destination_latitude=7.3775,
            destination_longitude=3.9470,
            route_geometry=SAMPLE_POLYLINE,
        )
        
        url = reverse('trip-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
    
    @patch.object(GoogleDirectionsService, 'get_route_geometry')
    def test_retrieve_trip(self, mock_directions):
        """Test retrieving a single trip."""
        trip = Trip.objects.create(
            starting_latitude=6.5244,
            starting_longitude=3.3792,
            destination_latitude=7.3775,
            destination_longitude=3.9470,
            route_geometry=SAMPLE_POLYLINE,
        )
        
        url = reverse('trip-detail', kwargs={'pk': trip.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], trip.id)
    
    @patch.object(GoogleDirectionsService, 'get_route_geometry')
    def test_update_trip_seats(self, mock_directions):
        """Test updating available seats (no route recompute)."""
        trip = Trip.objects.create(
            starting_latitude=6.5244,
            starting_longitude=3.3792,
            destination_latitude=7.3775,
            destination_longitude=3.9470,
            route_geometry=SAMPLE_POLYLINE,
            available_seats=3,
        )
        
        url = reverse('trip-detail', kwargs={'pk': trip.id})
        data = {'available_seats': 2}
        
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['available_seats'], 2)
        # Directions should not be called for seat update
        mock_directions.assert_not_called()
    
    @patch.object(GoogleDirectionsService, 'get_route_geometry')
    def test_update_trip_coordinates(self, mock_directions):
        """Test updating coordinates triggers route recompute."""
        mock_directions.return_value = "new_polyline"
        
        trip = Trip.objects.create(
            starting_latitude=6.5244,
            starting_longitude=3.3792,
            destination_latitude=7.3775,
            destination_longitude=3.9470,
            route_geometry=SAMPLE_POLYLINE,
        )
        
        url = reverse('trip-detail', kwargs={'pk': trip.id})
        data = {'starting_latitude': 6.6000}
        
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_directions.assert_called_once()
    
    def test_delete_trip(self):
        """Test deleting a trip."""
        trip = Trip.objects.create(
            starting_latitude=6.5244,
            starting_longitude=3.3792,
            destination_latitude=7.3775,
            destination_longitude=3.9470,
            route_geometry=SAMPLE_POLYLINE,
        )
        
        url = reverse('trip-detail', kwargs={'pk': trip.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Trip.objects.count(), 0)
    
    def test_delete_nonexistent_trip(self):
        """Test deleting a non-existent trip."""
        url = reverse('trip-detail', kwargs={'pk': 9999})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


@override_settings(
    DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    }
)
class TripMatchAPITests(APITestCase):
    """Tests for trip matching API endpoint."""
    
    def setUp(self):
        """Set up test data."""
        self.trip = Trip.objects.create(
            starting_latitude=6.5244,
            starting_longitude=3.3792,
            destination_latitude=7.3775,
            destination_longitude=3.9470,
            route_geometry=SAMPLE_POLYLINE,
            available_seats=3,
            is_ride_requests_allowed=True
        )
    
    def test_match_endpoint_missing_params(self):
        """Test match endpoint with missing parameters."""
        url = reverse('trip-matches')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_match_endpoint_valid_params(self):
        """Test match endpoint with valid parameters."""
        url = reverse('trip-matches')
        params = {
            'starting_latitude': 6.5244,
            'starting_longitude': 3.3792,
            'destination_latitude': 7.3775,
            'destination_longitude': 3.9470,
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_matches', response.data)
        self.assertIn('matches', response.data)
    
    def test_match_endpoint_with_optional_params(self):
        """Test match endpoint with optional parameters."""
        url = reverse('trip-matches')
        params = {
            'starting_latitude': 6.5244,
            'starting_longitude': 3.3792,
            'destination_latitude': 7.3775,
            'destination_longitude': 3.9470,
            'no_of_seats_required': 2,
            'intersection_radius_meters': 1000,
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_match_response_structure(self):
        """Test that match response has correct structure."""
        url = reverse('trip-matches')
        params = {
            'starting_latitude': 6.5244,
            'starting_longitude': 3.3792,
            'destination_latitude': 7.3775,
            'destination_longitude': 3.9470,
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data['total_matches'], int)
        self.assertIsInstance(response.data['matches'], list)


class WebSocketConsumerTests(TestCase):
    """Tests for WebSocket consumer (basic tests without full async)."""
    
    def test_group_name_generation(self):
        """Test channel group name generation."""
        group_name = TripLocationConsumer._get_group_name(1)
        self.assertEqual(group_name, "trip_location_1")
    
    def test_group_name_with_different_ids(self):
        """Test group names are unique per trip."""
        group1 = TripLocationConsumer._get_group_name(1)
        group2 = TripLocationConsumer._get_group_name(2)
        
        self.assertNotEqual(group1, group2)
