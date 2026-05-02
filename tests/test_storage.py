"""Unit tests for storage layer (no external dependencies)."""
import os
import tempfile
import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "test")


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    """Each test gets its own temporary SQLite database file."""
    db_file = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", db_file)
    # Force config reload so DB_PATH picks up the new value
    import importlib, config, storage
    importlib.reload(config)
    importlib.reload(storage)
    storage.init_db()
    yield


def test_init_and_save_post():
    import storage
    post_id = storage.save_post("AI trends", "twitter", "Hello #AI", content_brief="test")
    assert isinstance(post_id, int)
    assert post_id > 0


def test_get_posts():
    import storage
    storage.save_post("topic", "linkedin", "LinkedIn content")
    posts = storage.get_posts(platform="linkedin")
    assert len(posts) >= 1
    assert posts[0]["platform"] == "linkedin"


def test_update_post_status():
    import storage
    post_id = storage.save_post("topic", "twitter", "tweet")
    storage.update_post_status(post_id, "posted", platform_post_id="123abc")
    posts = storage.get_posts(status="posted")
    ids = [p["id"] for p in posts]
    assert post_id in ids


def test_analytics_summary_empty():
    import storage
    summary = storage.get_analytics_summary()
    assert isinstance(summary, list)
