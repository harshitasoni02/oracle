import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger('oracle')

GROUP_NAME = 'live_prices'


class PriceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add(GROUP_NAME, self.channel_name)
        await self.accept()
        logger.info(f"WS client connected: {self.channel_name}")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(GROUP_NAME, self.channel_name)
        logger.info(f"WS client disconnected: {self.channel_name}")

    async def receive(self, text_data=None, bytes_data=None):
        if text_data:
            try:
                msg = json.loads(text_data)
                if msg.get('type') == 'ping':
                    await self.send(text_data=json.dumps({'type': 'pong'}))
            except json.JSONDecodeError:
                pass

    async def price_update(self, event):
        """Handler for price_update messages from channel layer."""
        await self.send(text_data=json.dumps(event['data']))

    async def sentiment_update(self, event):
        """Handler for sentiment_update messages pushed from refresh_sentiment task."""
        await self.send(text_data=json.dumps(event['data']))
