# LincRide - Trip Management & Real-time Location System

A backend system for a ride-hailing application built with Django REST Framework, featuring trip management, route matching, and real-time location tracking using WebSockets and Kafka.

## Features

- **Trip Management**: CRUD operations for trips with automatic route geometry computation
- **Route Matching**: Find suitable trips for riders based on spatial intersections
- **Real-time Location Tracking**: WebSocket-based live location updates via Kafka

## Tech Stack

- **Framework**: Django 4.2, Django REST Framework
- **Database**: PostgreSQL
- **WebSocket**: Django Channels with Redis
- **Message Broker**: Apache Kafka
- **Containerization**: Docker & Docker Compose
- **Route API**: Google Directions API

## Project Structure

```
lincride/
├── lincride/                # Project configuration
│   ├── settings.py          # Django settings
│   ├── urls.py              # Root URL configuration
│   ├── asgi.py              # ASGI config for WebSockets
│   └── wsgi.py              # WSGI config
├── trips/                   # Main application
│   ├── models.py            # Trip model
│   ├── views.py             # API views
│   ├── serializers.py       # DRF serializers
│   ├── urls.py              # App URL routing
│   ├── consumers.py         # WebSocket consumer
│   ├── kafka_client.py      # Kafka producer/consumer
│   ├── routing.py           # WebSocket routing
│   ├── tests.py             # Test suite
│   └── services/            # Business logic layer
│       ├── directions.py    # Google Directions API service
│       ├── distance.py      # Distance calculations (Haversine)
│       └── matching.py      # Route matching algorithm
├── docker-compose.yml       # Docker services configuration
├── Dockerfile               # Application container
├── requirements.txt         # Python dependencies
└── README.md
```

## Architecture

### Clean Architecture Principles

The application follows SOLID principles with clear separation of concerns:

1. **Models Layer** (`models.py`): Data representation
2. **Services Layer** (`services/`): Business logic
3. **Views Layer** (`views.py`): HTTP request handling
4. **Serializers** (`serializers.py`): Data validation and transformation

### Trip Model

| Field | Type | Description |
|-------|------|-------------|
| id | Primary Key | Auto-generated |
| starting_latitude | Float | Origin latitude |
| starting_longitude | Float | Origin longitude |
| destination_latitude | Float | Destination latitude |
| destination_longitude | Float | Destination longitude |
| route_geometry | Text | Encoded polyline from Google Directions API |
| available_seats | Integer | Number of available seats |
| is_ride_requests_allowed | Boolean | Whether new ride requests are allowed |
| date_added | DateTime | Auto-populated on creation |
| date_last_updated | DateTime | Auto-updated on modification |

### Route Matching Algorithm

A trip matches a rider's request when:

1. **Pickup Proximity**: Rider's starting point is within the configured radius (default: 500m) of any point along the trip's route
2. **Dropoff Proximity**: Rider's destination is within the radius AND appears after the pickup point along the route
3. **Seat Availability**: Trip has at least the required number of seats
4. **Trip Eligibility**: `is_ride_requests_allowed` is True

### WebSocket Event Flow

```
1. Client connects to ws://localhost:8000/ws/trip-location/
2. Client sends SUBSCRIBE_TO_TRIP_LOCATION with trip_id
3. Driver sends PUBLISH_LOCATION with coordinates
4. Server publishes to Kafka topic
5. Kafka consumer processes and broadcasts TRIP_LOCATION_UPDATE
6. All subscribed clients receive the update
```

## Setup Instructions

### Prerequisites

- Docker and Docker Compose
- Google Maps API Key (for route geometry)

### Environment Configuration

Create a `.env` file in the project root:

```env
# Django Settings
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# PostgreSQL Database
POSTGRES_DB=lincride
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Redis (for Django Channels)
REDIS_HOST=localhost
REDIS_PORT=6379

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# Google Maps API
GOOGLE_MAPS_API_KEY=your-google-maps-api-key-here
```

### Running with Docker

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f web

# Stop services
docker-compose down
```

The application will be available at:
- REST API: http://localhost:8000/api/
- WebSocket: ws://localhost:8000/ws/trip-location/

### Running Locally (Development)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env  # Edit with your values

# Run migrations
python manage.py migrate

# Start the server
python manage.py runserver

# Start Kafka consumer (in separate terminal)
python manage.py run_kafka_consumer
```

## API Endpoints

### Trip Management

#### Create Trip
```http
POST /api/trips/
Content-Type: application/json

{
    "starting_latitude": 6.5244,
    "starting_longitude": 3.3792,
    "destination_latitude": 7.3775,
    "destination_longitude": 3.9470,
    "available_seats": 3,
    "is_ride_requests_allowed": true
}
```

#### List Trips
```http
GET /api/trips/
```

#### Get Trip
```http
GET /api/trips/{id}/
```

#### Update Trip
```http
PATCH /api/trips/{id}/
Content-Type: application/json

{
    "available_seats": 2
}
```

#### Delete Trip
```http
DELETE /api/trips/{id}/
```

### Route Matching

```http
GET /api/trips/matches/?starting_latitude=6.5244&starting_longitude=3.3792&destination_latitude=7.3775&destination_longitude=3.9470&no_of_seats_required=1&intersection_radius_meters=500
```

**Response:**
```json
{
    "total_matches": 1,
    "matches": [
        {
            "trip_id": 1,
            "pickup_latitude": 6.524,
            "pickup_longitude": 3.379,
            "dropoff_latitude": 7.377,
            "dropoff_longitude": 3.947,
            "pickup_distance_meters": 45.2,
            "dropoff_distance_meters": 52.8,
            "rider_trip_distance_meters": 128000,
            "available_seats": 3,
            "estimated_arrival_minutes": 15.5
        }
    ]
}
```

### WebSocket Events

#### Connect
```
ws://localhost:8000/ws/trip-location/
```

#### Publish Location
```json
{
    "type": "PUBLISH_LOCATION",
    "data": {
        "trip_id": 1,
        "latitude": 6.5244,
        "longitude": 3.3792,
        "timestamp": "2024-01-15T10:30:00Z"
    }
}
```

#### Subscribe to Trip
```json
{
    "type": "SUBSCRIBE_TO_TRIP_LOCATION",
    "data": {
        "trip_id": 1
    }
}
```

#### Unsubscribe from Trip
```json
{
    "type": "UNSUBSCRIBE_FROM_TRIP_LOCATION",
    "data": {
        "trip_id": 1
    }
}
```

#### Location Update (Broadcast)
```json
{
    "type": "TRIP_LOCATION_UPDATE",
    "data": {
        "trip_id": 1,
        "latitude": 6.5244,
        "longitude": 3.3792,
        "timestamp": "2024-01-15T10:30:00Z"
    }
}
```

## Running Tests

```bash
# Run all tests
python manage.py test trips

# Run with verbosity
python manage.py test trips -v 2

# Run specific test class
python manage.py test trips.tests.TripAPITests
```

## Configuring Google Maps API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the "Directions API"
4. Create credentials (API Key)
5. Add the key to your `.env` file as `GOOGLE_MAPS_API_KEY`

## Kafka Setup

Kafka is automatically set up via Docker Compose. The configuration includes:

- **Zookeeper**: Port 2181
- **Kafka Broker**: Port 9092 (external), 29092 (internal)
- **Topic**: `trip-location-updates` (auto-created)

For production, consider:
- Multiple broker instances
- Topic replication
- Consumer groups for scaling

## License

MIT License

