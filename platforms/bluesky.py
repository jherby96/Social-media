"""Bluesky connector via the AT Protocol (atproto SDK)."""
from typing import Optional
import config
from .base import BasePlatform, PostResult


class BlueskyPlatform(BasePlatform):
    name = "bluesky"
    max_chars = 300
    supports_images = True
    _BASE_URL = "https://bsky.social"

    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            from atproto import Client
            c = Client(base_url=self._BASE_URL)
            c.login(config.bluesky.handle, config.bluesky.password)
            self._client = c
        return self._client

    def post(self, content: str, image_url: Optional[str] = None) -> PostResult:
        valid, msg = self.validate_content(content)
        if not valid:
            return PostResult(success=False, error=msg)
        try:
            client = self._get_client()
            response = client.send_post(text=content)
            uri = response.uri
            post_id = uri.split("/")[-1]
            handle = config.bluesky.handle.lstrip("@")
            return PostResult(
                success=True,
                platform_post_id=uri,
                url=f"https://bsky.app/profile/{handle}/post/{post_id}",
            )
        except Exception as e:
            return PostResult(success=False, error=str(e))
