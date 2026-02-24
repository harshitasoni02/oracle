from django.core.management.base import BaseCommand

from oracle.services.live_streamer import LiveStreamer


class Command(BaseCommand):
    help = 'Run the live price streamer (polls yfinance, broadcasts via WebSocket)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting live price streamer...'))
        streamer = LiveStreamer()
        streamer.run()
