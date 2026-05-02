"""Instagram connector via the Meta Graph API (Instagram Basic Display / Content Publishing)."""
from typing import Optional
import requests
import config
from .base import BasePlatform, PostResult


class InstagramPlatform(BasePlatform):
    name = "instagram"
    max_chars = 2200
    supports_images = True
    supports_videos = True
    _GRAPH = "https://graph.facebook.com/v19.0"

    def post(self, content: str, image_url: Optional[str] = None) -> PostResult:
        """
        Instagram requires a public image URL to create a media container,
        then a second call to publish it. If no image_url is provided we
        cannot post to Instagram (images/reels are mandatory).
        """
        valid, msg = self.validate_content(content)
        if not valid:
            return PostResult(success=False, error=msg)
        if not image_url:
            return PostResult(success=False, error="Instagram requires an image_url to publish a post.")
        try:
            token = config.instagram.access_token
            account_id = config.instagram.account_id

            # Step 1: create media container
            container_resp = requests.post(
                f"{self._GRAPH}/{account_id}/media",
                data={
                    "image_url": image_url,
                    "caption": content,
                    "access_token": token,
                },
                timeout=15,
            )
            container_resp.raise_for_status()
            container_id = container_resp.json()["id"]

            # Step 2: publish
            publish_resp = requests.post(
                f"{self._GRAPH}/{account_id}/media_publish",
                data={"creation_id": container_id, "access_token": token},
                timeout=15,
            )
            publish_resp.raise_for_status()
            media_id = publish_resp.json().get("id", container_id)
            return PostResult(
                success=True,
                platform_post_id=media_id,
                url=f"https://www.instagram.com/p/{media_id}/",
            )
        except Exception as e:
            return PostResult(success=False, error=str(e))
