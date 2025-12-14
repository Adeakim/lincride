"""
WebSocket consumer for real-time trip location updates.
"""

import json
import logging
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.exceptions import ObjectDoesNotExist

from .models import Trip
from .kafka_client import KafkaProducerClient

logger = logging.getLogger(__name__)


class TripLocationConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for handling real-time trip location updates.
    
    Message Types:
    - PUBLISH_LOCATION: Publish a location update
    - SUBSCRIBE_TO_TRIP_LOCATION: Subscribe to a trip's location updates
    - UNSUBSCRIBE_FROM_TRIP_LOCATION: Unsubscribe from a trip's updates
    
    Broadcast Message:
    - TRIP_LOCATION_UPDATE: Sent to all subscribers when location is updated
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.subscribed_trips = set()
        self.kafka_producer = None
    
    async def connect(self):
        """Handle WebSocket connection."""
        await self.accept()
        self.kafka_producer = KafkaProducerClient()
        await self.kafka_producer.start()
        logger.info(f"WebSocket connected: {self.channel_name}")
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Unsubscribe from all trips
        for trip_id in list(self.subscribed_trips):
            await self._unsubscribe_from_trip(trip_id)
        
        if self.kafka_producer:
            await self.kafka_producer.stop()
        
        logger.info(f"WebSocket disconnected: {self.channel_name}, code: {close_code}")
    
    async def receive_json(self, content):
        """Handle incoming JSON messages."""
        message_type = content.get('type')
        data = content.get('data', {})
        
        handlers = {
            'PUBLISH_LOCATION': self._handle_publish_location,
            'SUBSCRIBE_TO_TRIP_LOCATION': self._handle_subscribe,
            'UNSUBSCRIBE_FROM_TRIP_LOCATION': self._handle_unsubscribe,
        }
        
        handler = handlers.get(message_type)
        if handler:
            await handler(data)
        else:
            await self.send_json({
                'type': 'ERROR',
                'data': {'message': f'Unknown message type: {message_type}'}
            })
    
    async def _handle_publish_location(self, data):
        """Handle PUBLISH_LOCATION message."""
        trip_id = data.get('trip_id')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        timestamp = data.get('timestamp')
        
        # Validate required fields
        if not all([trip_id, latitude is not None, longitude is not None]):
            await self.send_json({
                'type': 'ERROR',
                'data': {'message': 'Missing required fields: trip_id, latitude, longitude'}
            })
            return
        
        # Validate trip exists
        if not await self._trip_exists(trip_id):
            await self.send_json({
                'type': 'ERROR',
                'data': {'message': f'Trip {trip_id} not found'}
            })
            return
        
        # Publish to Kafka
        location_update = {
            'trip_id': trip_id,
            'latitude': latitude,
            'longitude': longitude,
            'timestamp': timestamp,
        }
        
        try:
            await self.kafka_producer.publish_location(location_update)
            
            # Send acknowledgment
            await self.send_json({
                'type': 'LOCATION_PUBLISHED',
                'data': {'trip_id': trip_id, 'status': 'success'}
            })
        except Exception as e:
            logger.error(f"Failed to publish location: {e}")
            await self.send_json({
                'type': 'ERROR',
                'data': {'message': 'Failed to publish location update'}
            })
    
    async def _handle_subscribe(self, data):
        """Handle SUBSCRIBE_TO_TRIP_LOCATION message."""
        trip_id = data.get('trip_id')
        
        if not trip_id:
            await self.send_json({
                'type': 'ERROR',
                'data': {'message': 'Missing trip_id'}
            })
            return
        
        # Validate trip exists
        if not await self._trip_exists(trip_id):
            await self.send_json({
                'type': 'ERROR',
                'data': {'message': f'Trip {trip_id} not found'}
            })
            return
        
        # Subscribe to trip's channel group
        group_name = self._get_group_name(trip_id)
        await self.channel_layer.group_add(group_name, self.channel_name)
        self.subscribed_trips.add(trip_id)
        
        await self.send_json({
            'type': 'SUBSCRIBED',
            'data': {'trip_id': trip_id, 'status': 'success'}
        })
        
        logger.info(f"Client {self.channel_name} subscribed to trip {trip_id}")
    
    async def _handle_unsubscribe(self, data):
        """Handle UNSUBSCRIBE_FROM_TRIP_LOCATION message."""
        trip_id = data.get('trip_id')
        
        if not trip_id:
            await self.send_json({
                'type': 'ERROR',
                'data': {'message': 'Missing trip_id'}
            })
            return
        
        await self._unsubscribe_from_trip(trip_id)
        
        await self.send_json({
            'type': 'UNSUBSCRIBED',
            'data': {'trip_id': trip_id, 'status': 'success'}
        })
    
    async def _unsubscribe_from_trip(self, trip_id):
        """Unsubscribe from a trip's channel group."""
        if trip_id in self.subscribed_trips:
            group_name = self._get_group_name(trip_id)
            await self.channel_layer.group_discard(group_name, self.channel_name)
            self.subscribed_trips.discard(trip_id)
            logger.info(f"Client {self.channel_name} unsubscribed from trip {trip_id}")
    
    async def trip_location_update(self, event):
        """Handle TRIP_LOCATION_UPDATE broadcast from Kafka consumer."""
        await self.send_json({
            'type': 'TRIP_LOCATION_UPDATE',
            'data': event['data']
        })
    
    @staticmethod
    def _get_group_name(trip_id):
        """Get the channel group name for a trip."""
        return f"trip_location_{trip_id}"
    
    @database_sync_to_async
    def _trip_exists(self, trip_id):
        """Check if a trip exists."""
        return Trip.objects.filter(id=trip_id).exists()

