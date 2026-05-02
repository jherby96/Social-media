"""Twitter/X platform connector using Tweepy v4."""
from typing import Optional
import config
from .base import BasePlatform, PostResult


class TwitterPlatform(BasePlatform):
    name = "twitter"
    max_chars = 280
    supports_images = True
    supports_videos = True

    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            import tweepy
            self._client = tweepy.Client(
                bearer_token=config.twitter.bearer_token,
                consumer_key=config.twitter.api_key,
                consumer_secret=config.twitter.api_secret,
                access_token=config.twitter.access_token,
                access_token_secret=config.twitter.access_secret,
            )
        return self._client

    def post(self, content: str, image_url: Optional[str] = None) -> PostResult:
        valid, msg = self.validate_content(content)
        if not valid:
            return PostResult(success=False, error=msg)
        try:
            client = self._get_client()
            response = client.create_tweet(text=content)
            tweet_id = str(response.data["id"])
            return PostResult(
                success=True,
                platform_post_id=tweet_id,
                url=f"https://twitter.com/i/web/status/{tweet_id}",
            )
        except Exception as e:
            return PostResult(success=False, error=str(e))
