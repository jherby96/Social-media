"""Post scheduler — runs scheduled posts via APScheduler and can also run a simple flush loop."""
import logging
from datetime import datetime, timedelta
from typing import Optional

import storage
from platforms import get_available_platforms

logger = logging.getLogger(__name__)


def flush_due_posts() -> list[dict]:
    """Publish all posts whose scheduled_at <= now. Returns results."""
    now = datetime.utcnow().isoformat()
    pending = storage.get_pending_posts(before=now)
    platforms = get_available_platforms()
    results = []

    for post in pending:
        platform_name = post["platform"]
        platform = platforms.get(platform_name)
        if platform is None:
            logger.warning("Platform %s not configured — skipping post %s", platform_name, post["id"])
            storage.update_post_status(post["id"], "skipped", error_message="Platform not configured")
            results.append({**post, "result": "skipped", "error": "Platform not configured"})
            continue

        logger.info("Publishing post %s to %s", post["id"], platform_name)
        result = platform.post(post["content"])
        if result.success:
            storage.update_post_status(post["id"], "posted", platform_post_id=result.platform_post_id)
            logger.info("Posted %s -> %s", platform_name, result.url)
            results.append({**post, "result": "posted", "url": result.url})
        else:
            storage.update_post_status(post["id"], "failed", error_message=result.error)
            logger.error("Failed %s: %s", platform_name, result.error)
            results.append({**post, "result": "failed", "error": result.error})
    return results


def schedule_post(
    topic: str,
    platform: str,
    content: str,
    delay_minutes: int = 0,
    scheduled_at: Optional[str] = None,
    content_brief: Optional[str] = None,
) -> int:
    """Save a post to the database for future publishing."""
    if scheduled_at is None:
        dt = datetime.utcnow() + timedelta(minutes=delay_minutes)
        scheduled_at = dt.isoformat()
    return storage.save_post(topic, platform, content, scheduled_at, content_brief)


def start_scheduler(interval_seconds: int = 60):
    """Run a blocking scheduler loop that flushes due posts every interval."""
    import time
    logger.info("Scheduler started — checking every %ds", interval_seconds)
    while True:
        try:
            results = flush_due_posts()
            if results:
                logger.info("Flushed %d post(s)", len(results))
        except Exception as exc:
            logger.exception("Scheduler error: %s", exc)
        time.sleep(interval_seconds)
