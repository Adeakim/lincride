"""
API views for the trips application.
"""

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from .models import Trip
from .serializers import (
    TripSerializer,
    TripCreateSerializer,
    TripUpdateSerializer,
    MatchQuerySerializer,
    MatchedTripSerializer,
    MatchResponseSerializer,
)
from .services import GoogleDirectionsService, RouteMatchingService
from .services.directions import DirectionsAPIError


@extend_schema_view(
    list=extend_schema(
        summary="List all trips",
        description="Retrieve a paginated list of all trips.",
        tags=['Trips']
    ),
    retrieve=extend_schema(
        summary="Get a trip",
        description="Retrieve details of a specific trip by ID.",
        tags=['Trips']
    ),
    create=extend_schema(
        summary="Create a trip",
        description="Create a new trip. The route geometry is automatically computed using the Google Directions API.",
        tags=['Trips']
    ),
    update=extend_schema(
        summary="Update a trip",
        description="Update all fields of a trip. If coordinates change, route geometry is recomputed.",
        tags=['Trips']
    ),
    partial_update=extend_schema(
        summary="Partially update a trip",
        description="Update specific fields of a trip. If coordinates change, route geometry is recomputed.",
        tags=['Trips']
    ),
    destroy=extend_schema(
        summary="Delete a trip",
        description="Delete a trip by ID.",
        tags=['Trips']
    ),
)
class TripViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Trip CRUD operations.
    
    Endpoints:
    - POST /api/trips/ - Create a trip
    - GET /api/trips/ - List all trips
    - GET /api/trips/{id}/ - Retrieve a trip
    - PUT /api/trips/{id}/ - Update a trip (full)
    - PATCH /api/trips/{id}/ - Update a trip (partial)
    - DELETE /api/trips/{id}/ - Delete a trip
    """
    
    queryset = Trip.objects.all()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return TripCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return TripUpdateSerializer
        return TripSerializer
    
    def create(self, request, *args, **kwargs):
        """Create a new trip with route geometry from Google Directions API."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        
        # Fetch route geometry
        directions_service = GoogleDirectionsService()
        try:
            route_geometry = directions_service.get_route_geometry(
                data['starting_latitude'],
                data['starting_longitude'],
                data['destination_latitude'],
                data['destination_longitude']
            )
        except DirectionsAPIError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create trip with route geometry
        trip = Trip.objects.create(
            **data,
            route_geometry=route_geometry
        )
        
        response_serializer = TripSerializer(trip)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    def update(self, request, *args, **kwargs):
        """Update a trip, recomputing route geometry if coordinates change."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        
        # Check if coordinates are being updated
        coords_changed = any([
            'starting_latitude' in data and data['starting_latitude'] != instance.starting_latitude,
            'starting_longitude' in data and data['starting_longitude'] != instance.starting_longitude,
            'destination_latitude' in data and data['destination_latitude'] != instance.destination_latitude,
            'destination_longitude' in data and data['destination_longitude'] != instance.destination_longitude,
        ])
        
        if coords_changed:
            # Get the final coordinates
            start_lat = data.get('starting_latitude', instance.starting_latitude)
            start_lon = data.get('starting_longitude', instance.starting_longitude)
            dest_lat = data.get('destination_latitude', instance.destination_latitude)
            dest_lon = data.get('destination_longitude', instance.destination_longitude)
            
            # Recompute route geometry
            directions_service = GoogleDirectionsService()
            try:
                route_geometry = directions_service.get_route_geometry(
                    start_lat, start_lon, dest_lat, dest_lon
                )
                data['route_geometry'] = route_geometry
            except DirectionsAPIError as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Update the instance
        for attr, value in data.items():
            setattr(instance, attr, value)
        instance.save()
        
        response_serializer = TripSerializer(instance)
        return Response(response_serializer.data)
    
    def destroy(self, request, *args, **kwargs):
        """Delete a trip."""
        instance = self.get_object()
        trip_id = instance.id
        instance.delete()
        return Response(
            {'message': f'Trip {trip_id} deleted successfully'},
            status=status.HTTP_200_OK
        )


class TripMatchView(APIView):
    """
    API view for finding matching trips.
    """
    
    @extend_schema(
        summary="Find matching trips",
        description="""
        Find trips whose routes can accommodate a rider's requested journey.
        
        A trip qualifies as a match if:
        1. **Pickup proximity**: Rider's start point is within the configured radius of any point on the trip's route
        2. **Dropoff proximity**: Rider's destination is within the radius AND after the pickup point along the route
        3. **Seat availability**: Trip has at least the requested number of seats
        4. **Trip eligibility**: `is_ride_requests_allowed` is True
        """,
        tags=['Matching'],
        parameters=[
            OpenApiParameter(
                name='starting_latitude',
                type=OpenApiTypes.FLOAT,
                location=OpenApiParameter.QUERY,
                required=True,
                description='Rider pickup latitude'
            ),
            OpenApiParameter(
                name='starting_longitude',
                type=OpenApiTypes.FLOAT,
                location=OpenApiParameter.QUERY,
                required=True,
                description='Rider pickup longitude'
            ),
            OpenApiParameter(
                name='destination_latitude',
                type=OpenApiTypes.FLOAT,
                location=OpenApiParameter.QUERY,
                required=True,
                description='Rider destination latitude'
            ),
            OpenApiParameter(
                name='destination_longitude',
                type=OpenApiTypes.FLOAT,
                location=OpenApiParameter.QUERY,
                required=True,
                description='Rider destination longitude'
            ),
            OpenApiParameter(
                name='no_of_seats_required',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                default=1,
                description='Number of seats required (default: 1)'
            ),
            OpenApiParameter(
                name='intersection_radius_meters',
                type=OpenApiTypes.FLOAT,
                location=OpenApiParameter.QUERY,
                required=False,
                default=500,
                description='Matching radius in meters (default: 500)'
            ),
        ],
        responses={200: MatchResponseSerializer},
    )
    def get(self, request):
        """Find trips matching the rider's journey."""
        serializer = MatchQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        
        # Get eligible trips
        trips = Trip.objects.filter(
            is_ride_requests_allowed=True,
            available_seats__gte=data['no_of_seats_required']
        ).exclude(route_geometry='')
        
        # Find matches
        matching_service = RouteMatchingService(
            radius_meters=data['intersection_radius_meters']
        )
        
        matches = matching_service.find_matches(
            trips=trips,
            rider_start_lat=data['starting_latitude'],
            rider_start_lon=data['starting_longitude'],
            rider_dest_lat=data['destination_latitude'],
            rider_dest_lon=data['destination_longitude'],
            seats_required=data['no_of_seats_required']
        )
        
        # Serialize response
        response_data = {
            'total_matches': len(matches),
            'matches': MatchedTripSerializer([
                {
                    'trip_id': m.trip_id,
                    'pickup_latitude': m.pickup_latitude,
                    'pickup_longitude': m.pickup_longitude,
                    'dropoff_latitude': m.dropoff_latitude,
                    'dropoff_longitude': m.dropoff_longitude,
                    'pickup_distance_meters': m.pickup_distance_meters,
                    'dropoff_distance_meters': m.dropoff_distance_meters,
                    'rider_trip_distance_meters': m.rider_trip_distance_meters,
                    'available_seats': m.available_seats,
                    'estimated_arrival_minutes': m.estimated_arrival_minutes,
                }
                for m in matches
            ], many=True).data
        }
        
        return Response(response_data)
