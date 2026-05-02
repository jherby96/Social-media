"""Unit tests for platform connectors (offline — no real API calls)."""
import pytest
from unittest.mock import MagicMock, patch


def test_twitter_content_too_long():
    from platforms.twitter import TwitterPlatform
    p = TwitterPlatform()
    valid, msg = p.validate_content("x" * 281)
    assert not valid
    assert "280" in msg


def test_twitter_content_ok():
    from platforms.twitter import TwitterPlatform
    p = TwitterPlatform()
    valid, msg = p.validate_content("Hello world!")
    assert valid


def test_bluesky_content_too_long():
    from platforms.bluesky import BlueskyPlatform
    p = BlueskyPlatform()
    valid, msg = p.validate_content("x" * 301)
    assert not valid


def test_instagram_requires_image():
    import os
    os.environ["INSTAGRAM_ACCOUNT_ID"] = "123"
    os.environ["INSTAGRAM_ACCESS_TOKEN"] = "tok"
    from platforms.instagram import InstagramPlatform
    p = InstagramPlatform()
    result = p.post("Caption without image")
    assert not result.success
    assert "image_url" in result.error


def test_base_empty_content():
    from platforms.twitter import TwitterPlatform
    p = TwitterPlatform()
    valid, msg = p.validate_content("   ")
    assert not valid
    assert "empty" in msg.lower()
