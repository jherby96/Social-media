"""SQLite-backed storage for posts, schedules, and analytics."""
import sqlite3
import json
from datetime import datetime
from typing import Optional
from contextlib import contextmanager
import config


@contextmanager
def get_db():
    conn = sqlite3.connect(config.agent.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                content_brief TEXT,
                platform TEXT NOT NULL,
                content TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                scheduled_at TEXT,
                posted_at TEXT,
                platform_post_id TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                topic TEXT NOT NULL,
                platforms TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER REFERENCES posts(id),
                platform TEXT NOT NULL,
                platform_post_id TEXT,
                likes INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                shares INTEGER DEFAULT 0,
                impressions INTEGER DEFAULT 0,
                recorded_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status);
            CREATE INDEX IF NOT EXISTS idx_posts_scheduled ON posts(scheduled_at);
            CREATE INDEX IF NOT EXISTS idx_posts_platform ON posts(platform);
        """)


def save_post(topic: str, platform: str, content: str, scheduled_at: Optional[str] = None,
              content_brief: Optional[str] = None) -> int:
    with get_db() as db:
        cursor = db.execute(
            "INSERT INTO posts (topic, platform, content, scheduled_at, content_brief) VALUES (?,?,?,?,?)",
            (topic, platform, content, scheduled_at, content_brief)
        )
        return cursor.lastrowid


def update_post_status(post_id: int, status: str, platform_post_id: Optional[str] = None,
                       error_message: Optional[str] = None):
    posted_at = datetime.utcnow().isoformat() if status == "posted" else None
    with get_db() as db:
        db.execute(
            """UPDATE posts SET status=?, platform_post_id=?, error_message=?, posted_at=?
               WHERE id=?""",
            (status, platform_post_id, error_message, posted_at, post_id)
        )


def get_pending_posts(before: Optional[str] = None) -> list[dict]:
    query = "SELECT * FROM posts WHERE status='pending'"
    params = []
    if before:
        query += " AND scheduled_at <= ?"
        params.append(before)
    query += " ORDER BY scheduled_at ASC"
    with get_db() as db:
        rows = db.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_posts(platform: Optional[str] = None, status: Optional[str] = None,
              limit: int = 20) -> list[dict]:
    query = "SELECT * FROM posts WHERE 1=1"
    params = []
    if platform:
        query += " AND platform=?"
        params.append(platform)
    if status:
        query += " AND status=?"
        params.append(status)
    query += f" ORDER BY created_at DESC LIMIT {limit}"
    with get_db() as db:
        rows = db.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def save_analytics(post_id: int, platform: str, platform_post_id: str,
                   likes: int = 0, comments: int = 0, shares: int = 0, impressions: int = 0):
    with get_db() as db:
        db.execute(
            """INSERT INTO analytics (post_id, platform, platform_post_id, likes, comments, shares, impressions)
               VALUES (?,?,?,?,?,?,?)""",
            (post_id, platform, platform_post_id, likes, comments, shares, impressions)
        )


def get_analytics_summary() -> list[dict]:
    with get_db() as db:
        rows = db.execute("""
            SELECT p.platform,
                   COUNT(DISTINCT p.id) as total_posts,
                   SUM(a.likes) as total_likes,
                   SUM(a.comments) as total_comments,
                   SUM(a.shares) as total_shares,
                   SUM(a.impressions) as total_impressions
            FROM posts p
            LEFT JOIN analytics a ON p.id = a.post_id
            WHERE p.status = 'posted'
            GROUP BY p.platform
        """).fetchall()
        return [dict(r) for r in rows]
