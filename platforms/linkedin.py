"""LinkedIn platform connector via the LinkedIn REST API."""
from typing import Optional
import requests
import config
from .base import BasePlatform, PostResult


class LinkedInPlatform(BasePlatform):
    name = "linkedin"
    max_chars = 3000
    supports_images = True
    _API = "https://api.linkedin.com/v2"

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {config.linkedin.access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

    def _get_profile_urn(self) -> str:
        resp = requests.get(f"{self._API}/me", headers=self._headers(), timeout=15)
        resp.raise_for_status()
        return f"urn:li:person:{resp.json()['id']}"

    def post(self, content: str, image_url: Optional[str] = None) -> PostResult:
        valid, msg = self.validate_content(content)
        if not valid:
            return PostResult(success=False, error=msg)
        try:
            author = self._get_profile_urn()
            payload = {
                "author": author,
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": content},
                        "shareMediaCategory": "NONE",
                    }
                },
                "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
            }
            resp = requests.post(
                f"{self._API}/ugcPosts",
                json=payload,
                headers=self._headers(),
                timeout=15,
            )
            resp.raise_for_status()
            post_id = resp.headers.get("x-restli-id", resp.json().get("id", ""))
            return PostResult(
                success=True,
                platform_post_id=post_id,
                url=f"https://www.linkedin.com/feed/update/{post_id}",
            )
        except Exception as e:
            return PostResult(success=False, error=str(e))
