"""
Management command to run the Kafka consumer for location updates.
"""

import asyncio
import signal
from django.core.management.base import BaseCommand
from trips.kafka_client import start_kafka_consumer, stop_kafka_consumer


class Command(BaseCommand):
    help = 'Run the Kafka consumer for processing trip location updates'
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Kafka consumer...'))
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Handle shutdown signals
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(
                sig,
                lambda: asyncio.create_task(self._shutdown(loop))
            )
        
        try:
            loop.run_until_complete(start_kafka_consumer())
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('Received interrupt signal'))
        finally:
            loop.run_until_complete(stop_kafka_consumer())
            loop.close()
            self.stdout.write(self.style.SUCCESS('Kafka consumer stopped'))
    
    async def _shutdown(self, loop):
        self.stdout.write(self.style.WARNING('Shutting down...'))
        await stop_kafka_consumer()
        loop.stop()

