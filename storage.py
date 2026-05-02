"""SQLite-backed storage for posts, schedules, analytics, orders, customers, tickets, and accounting."""
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
    conn.execute("PRAGMA foreign_keys=ON")
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
            -- ── Social media ─────────────────────────────────────────────
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

            -- ── Customers ─────────────────────────────────────────────────
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                name TEXT,
                wc_customer_id TEXT,
                phone TEXT,
                tags TEXT DEFAULT '[]',
                total_orders INTEGER DEFAULT 0,
                total_spent REAL DEFAULT 0.0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                last_order_at TEXT
            );

            -- ── Orders ────────────────────────────────────────────────────
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wc_order_id TEXT UNIQUE,
                customer_email TEXT,
                customer_name TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                total REAL DEFAULT 0.0,
                items TEXT DEFAULT '[]',
                shipping_address TEXT DEFAULT '{}',
                tracking_number TEXT,
                shipped_at TEXT,
                fulfilled_at TEXT,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            -- ── Inventory ─────────────────────────────────────────────────
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                lot_number TEXT,
                quantity INTEGER DEFAULT 0,
                reorder_point INTEGER DEFAULT 10,
                unit_cost REAL DEFAULT 0.0,
                last_updated TEXT NOT NULL DEFAULT (datetime('now'))
            );

            -- ── Support tickets ───────────────────────────────────────────
            CREATE TABLE IF NOT EXISTS support_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_email TEXT,
                customer_name TEXT,
                subject TEXT NOT NULL,
                message TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                priority TEXT DEFAULT 'normal',
                category TEXT,
                auto_response TEXT,
                resolution TEXT,
                order_id INTEGER REFERENCES orders(id),
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                resolved_at TEXT
            );

            -- ── Email log ─────────────────────────────────────────────────
            CREATE TABLE IF NOT EXISTS email_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipient_email TEXT NOT NULL,
                email_type TEXT NOT NULL,
                subject TEXT,
                status TEXT DEFAULT 'sent',
                order_id INTEGER REFERENCES orders(id),
                error TEXT,
                sent_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            -- ── Accounting ────────────────────────────────────────────────
            CREATE TABLE IF NOT EXISTS accounting_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_type TEXT NOT NULL,
                amount REAL NOT NULL,
                gst_amount REAL DEFAULT 0.0,
                description TEXT,
                category TEXT,
                reference_id TEXT,
                entry_date TEXT NOT NULL DEFAULT (date('now')),
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            -- ── COA deliveries ────────────────────────────────────────────
            CREATE TABLE IF NOT EXISTS coa_deliveries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER REFERENCES orders(id),
                customer_email TEXT,
                product_sku TEXT,
                lot_number TEXT,
                coa_filename TEXT,
                delivered_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            -- ── Automation run log ────────────────────────────────────────
            CREATE TABLE IF NOT EXISTS automation_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                automation_name TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT,
                records_processed INTEGER DEFAULT 0,
                ran_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            -- ── Automation config ─────────────────────────────────────────
            CREATE TABLE IF NOT EXISTS automation_config (
                name TEXT PRIMARY KEY,
                enabled INTEGER NOT NULL DEFAULT 1,
                last_run TEXT,
                run_count INTEGER DEFAULT 0
            );

            -- Indexes
            CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status);
            CREATE INDEX IF NOT EXISTS idx_posts_scheduled ON posts(scheduled_at);
            CREATE INDEX IF NOT EXISTS idx_posts_platform ON posts(platform);
            CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
            CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_email);
            CREATE INDEX IF NOT EXISTS idx_tickets_status ON support_tickets(status);
            CREATE INDEX IF NOT EXISTS idx_accounting_date ON accounting_entries(entry_date);
        """)

        # Seed default automation config rows (ignore if already exist)
        automations = [
            ("order_processing", 1),
            ("inventory_sync", 1),
            ("accounting_record", 1),
            ("welcome_email", 1),
            ("abandoned_cart_email", 1),
            ("post_purchase_email", 1),
            ("review_request_email", 1),
            ("support_auto_respond", 1),
            ("coa_delivery", 1),
            ("backup", 1),
            ("social_marketing", 1),
            ("low_stock_alert", 1),
        ]
        for name, enabled in automations:
            db.execute(
                "INSERT OR IGNORE INTO automation_config (name, enabled) VALUES (?, ?)",
                (name, enabled),
            )


# ── Social media ──────────────────────────────────────────────────────────────

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


# ── Orders ────────────────────────────────────────────────────────────────────

def upsert_order(wc_order_id: str, customer_email: str, customer_name: str,
                 status: str, total: float, items: list, shipping_address: dict) -> int:
    with get_db() as db:
        existing = db.execute("SELECT id FROM orders WHERE wc_order_id=?", (wc_order_id,)).fetchone()
        if existing:
            db.execute(
                """UPDATE orders SET status=?, total=?, items=?, shipping_address=?
                   WHERE wc_order_id=?""",
                (status, total, json.dumps(items), json.dumps(shipping_address), wc_order_id)
            )
            return existing["id"]
        cursor = db.execute(
            """INSERT INTO orders (wc_order_id, customer_email, customer_name, status, total, items, shipping_address)
               VALUES (?,?,?,?,?,?,?)""",
            (wc_order_id, customer_email, customer_name, status, total,
             json.dumps(items), json.dumps(shipping_address))
        )
        return cursor.lastrowid


def get_orders(status: Optional[str] = None, limit: int = 50) -> list[dict]:
    query = "SELECT * FROM orders WHERE 1=1"
    params = []
    if status:
        query += " AND status=?"
        params.append(status)
    query += f" ORDER BY created_at DESC LIMIT {limit}"
    with get_db() as db:
        rows = db.execute(query, params).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["items"] = json.loads(d.get("items") or "[]")
            d["shipping_address"] = json.loads(d.get("shipping_address") or "{}")
            result.append(d)
        return result


def update_order(order_id: int, **kwargs):
    if not kwargs:
        return
    fields = ", ".join(f"{k}=?" for k in kwargs)
    values = list(kwargs.values()) + [order_id]
    with get_db() as db:
        db.execute(f"UPDATE orders SET {fields} WHERE id=?", values)


def count_orders_today() -> int:
    with get_db() as db:
        row = db.execute(
            "SELECT COUNT(*) as n FROM orders WHERE date(created_at)=date('now')"
        ).fetchone()
        return row["n"]


def revenue_today() -> float:
    with get_db() as db:
        row = db.execute(
            "SELECT COALESCE(SUM(total),0) as rev FROM orders WHERE date(created_at)=date('now')"
        ).fetchone()
        return row["rev"]


# ── Customers ─────────────────────────────────────────────────────────────────

def upsert_customer(email: str, name: str = "", wc_customer_id: str = "") -> int:
    with get_db() as db:
        existing = db.execute("SELECT id FROM customers WHERE email=?", (email,)).fetchone()
        if existing:
            db.execute(
                "UPDATE customers SET name=COALESCE(NULLIF(?,''),name), wc_customer_id=COALESCE(NULLIF(?,''),wc_customer_id) WHERE email=?",
                (name, wc_customer_id, email)
            )
            return existing["id"]
        cursor = db.execute(
            "INSERT INTO customers (email, name, wc_customer_id) VALUES (?,?,?)",
            (email, name, wc_customer_id)
        )
        return cursor.lastrowid


def get_customer(email: str) -> Optional[dict]:
    with get_db() as db:
        row = db.execute("SELECT * FROM customers WHERE email=?", (email,)).fetchone()
        return dict(row) if row else None


def increment_customer_orders(email: str, order_total: float):
    with get_db() as db:
        db.execute(
            """UPDATE customers SET total_orders=total_orders+1, total_spent=total_spent+?,
               last_order_at=datetime('now') WHERE email=?""",
            (order_total, email)
        )


# ── Inventory ─────────────────────────────────────────────────────────────────

def upsert_inventory(sku: str, name: str, quantity: int,
                     lot_number: str = "", reorder_point: int = 10,
                     unit_cost: float = 0.0) -> int:
    with get_db() as db:
        existing = db.execute("SELECT id FROM inventory WHERE sku=?", (sku,)).fetchone()
        if existing:
            db.execute(
                """UPDATE inventory SET name=?, quantity=?, lot_number=COALESCE(NULLIF(?,''),lot_number),
                   reorder_point=?, unit_cost=?, last_updated=datetime('now') WHERE sku=?""",
                (name, quantity, lot_number, reorder_point, unit_cost, sku)
            )
            return existing["id"]
        cursor = db.execute(
            """INSERT INTO inventory (sku, name, quantity, lot_number, reorder_point, unit_cost)
               VALUES (?,?,?,?,?,?)""",
            (sku, name, quantity, lot_number, reorder_point, unit_cost)
        )
        return cursor.lastrowid


def get_inventory(low_stock_only: bool = False) -> list[dict]:
    query = "SELECT * FROM inventory"
    if low_stock_only:
        query += " WHERE quantity <= reorder_point"
    query += " ORDER BY name ASC"
    with get_db() as db:
        return [dict(r) for r in db.execute(query).fetchall()]


def adjust_inventory(sku: str, delta: int):
    with get_db() as db:
        db.execute(
            "UPDATE inventory SET quantity=MAX(0,quantity+?), last_updated=datetime('now') WHERE sku=?",
            (delta, sku)
        )


# ── Support tickets ───────────────────────────────────────────────────────────

def create_ticket(customer_email: str, subject: str, message: str,
                  customer_name: str = "", category: str = "", order_id: Optional[int] = None) -> int:
    with get_db() as db:
        cursor = db.execute(
            """INSERT INTO support_tickets (customer_email, customer_name, subject, message, category, order_id)
               VALUES (?,?,?,?,?,?)""",
            (customer_email, customer_name, subject, message, category, order_id)
        )
        return cursor.lastrowid


def update_ticket(ticket_id: int, **kwargs):
    kwargs["updated_at"] = datetime.utcnow().isoformat()
    fields = ", ".join(f"{k}=?" for k in kwargs)
    values = list(kwargs.values()) + [ticket_id]
    with get_db() as db:
        db.execute(f"UPDATE support_tickets SET {fields} WHERE id=?", values)


def get_tickets(status: Optional[str] = None, limit: int = 50) -> list[dict]:
    query = "SELECT * FROM support_tickets WHERE 1=1"
    params = []
    if status:
        query += " AND status=?"
        params.append(status)
    query += f" ORDER BY created_at DESC LIMIT {limit}"
    with get_db() as db:
        return [dict(r) for r in db.execute(query, params).fetchall()]


def count_open_tickets() -> int:
    with get_db() as db:
        row = db.execute("SELECT COUNT(*) as n FROM support_tickets WHERE status='open'").fetchone()
        return row["n"]


# ── Accounting ────────────────────────────────────────────────────────────────

def record_accounting_entry(entry_type: str, amount: float, description: str = "",
                             category: str = "", reference_id: str = "",
                             gst_amount: float = 0.0, entry_date: Optional[str] = None):
    date = entry_date or datetime.utcnow().strftime("%Y-%m-%d")
    with get_db() as db:
        db.execute(
            """INSERT INTO accounting_entries (entry_type, amount, gst_amount, description, category, reference_id, entry_date)
               VALUES (?,?,?,?,?,?,?)""",
            (entry_type, amount, gst_amount, description, category, reference_id, date)
        )


def get_accounting_summary(period_start: Optional[str] = None, period_end: Optional[str] = None) -> dict:
    query_base = "SELECT * FROM accounting_entries WHERE 1=1"
    params = []
    if period_start:
        query_base += " AND entry_date >= ?"
        params.append(period_start)
    if period_end:
        query_base += " AND entry_date <= ?"
        params.append(period_end)
    with get_db() as db:
        rows = [dict(r) for r in db.execute(query_base, params).fetchall()]
    sales = sum(r["amount"] for r in rows if r["entry_type"] == "sale")
    expenses = sum(r["amount"] for r in rows if r["entry_type"] == "expense")
    gst_collected = sum(r["gst_amount"] for r in rows if r["entry_type"] == "sale")
    gst_paid = sum(r["gst_amount"] for r in rows if r["entry_type"] == "expense")
    return {
        "sales": round(sales, 2),
        "expenses": round(expenses, 2),
        "profit": round(sales - expenses, 2),
        "gst_collected": round(gst_collected, 2),
        "gst_paid": round(gst_paid, 2),
        "gst_net_payable": round(gst_collected - gst_paid, 2),
        "entries": rows,
    }


def log_email(recipient_email: str, email_type: str, subject: str = "",
              order_id: Optional[int] = None, status: str = "sent", error: str = ""):
    with get_db() as db:
        db.execute(
            """INSERT INTO email_log (recipient_email, email_type, subject, order_id, status, error)
               VALUES (?,?,?,?,?,?)""",
            (recipient_email, email_type, subject, order_id, status, error)
        )


def log_coa_delivery(order_id: int, customer_email: str, product_sku: str,
                     lot_number: str, coa_filename: str):
    with get_db() as db:
        db.execute(
            """INSERT INTO coa_deliveries (order_id, customer_email, product_sku, lot_number, coa_filename)
               VALUES (?,?,?,?,?)""",
            (order_id, customer_email, product_sku, lot_number, coa_filename)
        )


def log_automation_run(automation_name: str, status: str, message: str = "",
                       records_processed: int = 0):
    with get_db() as db:
        db.execute(
            """INSERT INTO automation_runs (automation_name, status, message, records_processed)
               VALUES (?,?,?,?)""",
            (automation_name, status, message, records_processed)
        )
        db.execute(
            """UPDATE automation_config SET last_run=datetime('now'), run_count=run_count+1
               WHERE name=?""",
            (automation_name,)
        )


def get_automation_config() -> list[dict]:
    with get_db() as db:
        return [dict(r) for r in db.execute("SELECT * FROM automation_config ORDER BY name").fetchall()]


def set_automation_enabled(name: str, enabled: bool):
    with get_db() as db:
        db.execute("UPDATE automation_config SET enabled=? WHERE name=?", (int(enabled), name))


def get_recent_automation_runs(limit: int = 20) -> list[dict]:
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT * FROM automation_runs ORDER BY ran_at DESC LIMIT ?", (limit,)
        ).fetchall()]
