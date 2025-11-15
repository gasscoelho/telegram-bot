import logging

import aiohttp

logger = logging.getLogger(__name__)


class WebhookNotifier:
    """HTTP webhook notifier for sending messages to external services."""

    def __init__(self, webhook_url: str | None):
        self.webhook_url = webhook_url

    async def post(self, payload: dict) -> bool:
        """
        Post a JSON payload to the configured webhook URL.

        Returns:
            bool: True if the request was successful (2xx status), False otherwise.
        """
        if not self.webhook_url:
            logger.warning("WebhookNotifier: no URL configured")
            return False
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=payload) as resp:
                    return 200 <= resp.status < 300
        except Exception as e:
            logger.error(f"WebhookNotifier error: {e}")
            return False
