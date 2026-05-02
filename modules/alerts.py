"""Alert system — checks all conditions and sends notifications."""
import logging
from datetime import datetime

import config
import storage
from modules.email_comms import send_low_stock_alert

logger = logging.getLogger(__name__)


def check_low_stock() -> list[dict]:
    items = storage.get_inventory(low_stock_only=True)
    if items:
        send_low_stock_alert(items)
        storage.log_automation_run(
            "low_stock_alert", "success",
            f"{len(items)} low-stock item(s) alerted", len(items),
        )
    return items


def get_all_alerts() -> list[dict]:
    """Return current active alerts for the dashboard."""
    alerts = []

    low_stock = storage.get_inventory(low_stock_only=True)
    for item in low_stock:
        level = "critical" if item["quantity"] == 0 else "warning"
        alerts.append({
            "level": level,
            "type": "low_stock",
            "message": f"{'Out of stock' if item['quantity'] == 0 else 'Low stock'}: {item['name']} ({item['quantity']} units)",
            "timestamp": item["last_updated"],
        })

    open_tickets = storage.count_open_tickets()
    if open_tickets > 10:
        alerts.append({
            "level": "warning",
            "type": "support_backlog",
            "message": f"{open_tickets} open support tickets — backlog building up",
            "timestamp": datetime.utcnow().isoformat(),
        })

    if not config.email.is_configured:
        alerts.append({
            "level": "warning",
            "type": "config",
            "message": "Email (SMTP) not configured — customer communication automations are paused",
            "timestamp": datetime.utcnow().isoformat(),
        })

    if not config.woocommerce.is_configured:
        alerts.append({
            "level": "info",
            "type": "config",
            "message": "WooCommerce not configured — connect via .env to enable order sync",
            "timestamp": datetime.utcnow().isoformat(),
        })

    return alerts
