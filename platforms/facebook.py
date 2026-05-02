"""Facebook Page connector via the Meta Graph API."""
from typing import Optional
import requests
import config
from .base import BasePlatform, PostResult


class FacebookPlatform(BasePlatform):
    name = "facebook"
    max_chars = 63206
    supports_images = True
    supports_videos = True
    _GRAPH = "https://graph.facebook.com/v19.0"

    def post(self, content: str, image_url: Optional[str] = None) -> PostResult:
        valid, msg = self.validate_content(content)
        if not valid:
            return PostResult(success=False, error=msg)
        try:
            endpoint = f"{self._GRAPH}/{config.facebook.page_id}/feed"
            payload: dict = {
                "message": content,
                "access_token": config.facebook.page_access_token,
            }
            if image_url:
                endpoint = f"{self._GRAPH}/{config.facebook.page_id}/photos"
                payload["url"] = image_url
            resp = requests.post(endpoint, data=payload, timeout=15)
            resp.raise_for_status()
            post_id = resp.json().get("id", "")
            return PostResult(
                success=True,
                platform_post_id=post_id,
                url=f"https://www.facebook.com/{post_id}",
            )
        except Exception as e:
            return PostResult(success=False, error=str(e))
