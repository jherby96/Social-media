from .base import BasePlatform, PostResult
from .twitter import TwitterPlatform
from .linkedin import LinkedInPlatform
from .facebook import FacebookPlatform
from .instagram import InstagramPlatform
from .bluesky import BlueskyPlatform

__all__ = [
    "BasePlatform",
    "PostResult",
    "TwitterPlatform",
    "LinkedInPlatform",
    "FacebookPlatform",
    "InstagramPlatform",
    "BlueskyPlatform",
]


def get_available_platforms() -> dict[str, BasePlatform]:
    """Return only platforms that are fully configured."""
    import config
    candidates = {
        "twitter": (TwitterPlatform, config.twitter),
        "linkedin": (LinkedInPlatform, config.linkedin),
        "facebook": (FacebookPlatform, config.facebook),
        "instagram": (InstagramPlatform, config.instagram),
        "bluesky": (BlueskyPlatform, config.bluesky),
    }
    return {
        name: cls()
        for name, (cls, cfg) in candidates.items()
        if cfg.is_configured
    }
