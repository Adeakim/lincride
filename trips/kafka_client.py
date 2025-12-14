"""
Kafka producer and consumer clients for real-time location updates.
"""

import json
import logging
import asyncio
from typing import Optional
from django.conf import settings
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


class KafkaProducerClient:
    """
    Async Kafka producer for publishing location updates.
    
    Uses aiokafka for asynchronous message production.
    """
    
    def __init__(self):
        self.producer = None
        self.topic = settings.KAFKA_LOCATION_TOPIC
        self.bootstrap_servers = settings.KAFKA_BOOTSTRAP_SERVERS
    
    async def start(self):
        """Start the Kafka producer."""
        try:
            from aiokafka import AIOKafkaProducer
            
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            )
            await self.producer.start()
            logger.info("Kafka producer started")
        except Exception as e:
            logger.warning(f"Failed to start Kafka producer: {e}. Running without Kafka.")
            self.producer = None
    
    async def stop(self):
        """Stop the Kafka producer."""
        if self.producer:
            await self.producer.stop()
            logger.info("Kafka producer stopped")
    
    async def publish_location(self, location_data: dict):
        """
        Publish a location update to Kafka.
        
        Args:
            location_data: Dict containing trip_id, latitude, longitude, timestamp
        """
        if not self.producer:
            # If Kafka is not available, broadcast directly
            logger.debug("Kafka not available, broadcasting directly")
            await self._broadcast_location(location_data)
            return
        
        try:
            await self.producer.send_and_wait(self.topic, location_data)
            logger.debug(f"Published location for trip {location_data.get('trip_id')}")
        except Exception as e:
            logger.error(f"Failed to publish to Kafka: {e}")
            # Fallback to direct broadcast
            await self._broadcast_location(location_data)
    
    async def _broadcast_location(self, location_data: dict):
        """Broadcast location directly via channel layer."""
        channel_layer = get_channel_layer()
        trip_id = location_data.get('trip_id')
        group_name = f"trip_location_{trip_id}"
        
        await channel_layer.group_send(
            group_name,
            {
                'type': 'trip_location_update',
                'data': location_data,
            }
        )


class KafkaConsumerClient:
    """
    Async Kafka consumer for processing location updates.
    
    Consumes messages from the location topic and broadcasts
    to WebSocket subscribers via Django Channels.
    """
    
    def __init__(self):
        self.consumer = None
        self.topic = settings.KAFKA_LOCATION_TOPIC
        self.bootstrap_servers = settings.KAFKA_BOOTSTRAP_SERVERS
        self.running = False
    
    async def start(self):
        """Start the Kafka consumer."""
        try:
            from aiokafka import AIOKafkaConsumer
            
            self.consumer = AIOKafkaConsumer(
                self.topic,
                bootstrap_servers=self.bootstrap_servers,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                group_id='location-update-consumers',
                auto_offset_reset='latest',
            )
            await self.consumer.start()
            self.running = True
            logger.info("Kafka consumer started")
        except Exception as e:
            logger.warning(f"Failed to start Kafka consumer: {e}")
            self.consumer = None
            self.running = False
    
    async def stop(self):
        """Stop the Kafka consumer."""
        self.running = False
        if self.consumer:
            await self.consumer.stop()
            logger.info("Kafka consumer stopped")
    
    async def consume(self):
        """
        Consume messages and broadcast to WebSocket subscribers.
        
        This method runs indefinitely and should be started as a background task.
        """
        if not self.consumer:
            logger.warning("Consumer not initialized, cannot consume messages")
            return
        
        channel_layer = get_channel_layer()
        
        try:
            async for message in self.consumer:
                if not self.running:
                    break
                
                location_data = message.value
                trip_id = location_data.get('trip_id')
                
                if trip_id:
                    group_name = f"trip_location_{trip_id}"
                    
                    await channel_layer.group_send(
                        group_name,
                        {
                            'type': 'trip_location_update',
                            'data': location_data,
                        }
                    )
                    logger.debug(f"Broadcast location update for trip {trip_id}")
        except Exception as e:
            logger.error(f"Error consuming messages: {e}")


# Global consumer instance for management commands
_consumer_instance: Optional[KafkaConsumerClient] = None


async def start_kafka_consumer():
    """Start the global Kafka consumer."""
    global _consumer_instance
    _consumer_instance = KafkaConsumerClient()
    await _consumer_instance.start()
    await _consumer_instance.consume()


async def stop_kafka_consumer():
    """Stop the global Kafka consumer."""
    global _consumer_instance
    if _consumer_instance:
        await _consumer_instance.stop()
        _consumer_instance = None

