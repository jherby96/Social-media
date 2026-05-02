"""Flask web dashboard — single entry point for all business automations."""
import json
import logging
from datetime import datetime, date
from pathlib import Path

from flask import Flask, jsonify, render_template, request, abort

import config
import storage
from modules import orders as order_module
from modules import accounting as acct_module
from modules import email_comms
from modules import support as support_module
from modules import compliance as compliance_module
from modules import alerts as alert_module

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = config.dashboard.secret_key


def _ok(data: dict | list = None, **kwargs):
    payload = {"ok": True}
    if data is not None:
        payload["data"] = data
    payload.update(kwargs)
    return jsonify(payload)


def _err(msg: str, code: int = 400):
    return jsonify({"ok": False, "error": msg}), code


# ── Dashboard UI ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html",
                           brand_name=config.agent.brand_name,
                           currency=config.accounting.currency)


# ── Dashboard summary ─────────────────────────────────────────────────────────

@app.route("/api/dashboard")
def api_dashboard():
    storage.init_db()
    financials = acct_module.get_dashboard_financials()
    alerts = alert_module.get_all_alerts()
    low_stock_count = len(storage.get_inventory(low_stock_only=True))
    recent_runs = storage.get_recent_automation_runs(limit=10)
    return _ok({
        "orders_today": storage.count_orders_today(),
        "revenue_today": storage.revenue_today(),
        "open_tickets": storage.count_open_tickets(),
        "low_stock_items": low_stock_count,
        "financials": financials,
        "alerts": alerts,
        "recent_runs": recent_runs,
        "automations": storage.get_automation_config(),
    })


# ── Orders ────────────────────────────────────────────────────────────────────

@app.route("/api/orders")
def api_orders():
    storage.init_db()
    status_filter = request.args.get("status")
    limit = int(request.args.get("limit", 50))
    orders = storage.get_orders(status=status_filter, limit=limit)
    return _ok(orders)


@app.route("/api/orders/sync", methods=["POST"])
def api_orders_sync():
    storage.init_db()
    count = order_module.fetch_and_sync_orders()
    return _ok({"synced": count})


@app.route("/api/orders/<int:order_id>/ship", methods=["POST"])
def api_order_ship(order_id: int):
    storage.init_db()
    body = request.get_json(silent=True) or {}
    tracking = body.get("tracking_number", "")
    storage.update_order(order_id, status="shipped", tracking_number=tracking,
                         shipped_at=datetime.utcnow().isoformat())
    orders = storage.get_orders()
    order = next((o for o in orders if o["id"] == order_id), None)
    if order and tracking:
        email_comms.send_shipping_notification(order, tracking)
        compliance_module.deliver_coas_for_order(order)
    return _ok({"order_id": order_id, "tracking_number": tracking})


# ── WooCommerce webhook ────────────────────────────────────────────────────────

@app.route("/api/webhooks/woocommerce", methods=["POST"])
def woocommerce_webhook():
    storage.init_db()
    payload = request.get_data()
    sig = request.headers.get("X-WC-Webhook-Signature", "")
    if config.woocommerce.webhook_secret and not order_module.verify_webhook_signature(payload, sig):
        return _err("Invalid signature", 403)

    topic = request.headers.get("X-WC-Webhook-Topic", "")
    try:
        data = json.loads(payload)
    except Exception:
        return _err("Invalid JSON", 400)

    if topic.startswith("order."):
        result = order_module.process_webhook_order(data)
        # Auto-send order confirmation for new orders
        if topic == "order.created":
            orders = storage.get_orders()
            order = next((o for o in orders if o["id"] == result["order_id"]), None)
            if order:
                email_comms.send_order_confirmation(order)
                acct_module.record_sale_from_order(order)
    elif topic.startswith("customer."):
        storage.upsert_customer(
            email=data.get("email", ""),
            name=f"{data.get('first_name','')} {data.get('last_name','')}".strip(),
            wc_customer_id=str(data.get("id", "")),
        )

    return _ok({"topic": topic})


# ── Inventory ─────────────────────────────────────────────────────────────────

@app.route("/api/inventory")
def api_inventory():
    storage.init_db()
    low_stock_only = request.args.get("low_stock") == "true"
    return _ok(storage.get_inventory(low_stock_only=low_stock_only))


@app.route("/api/inventory/sync", methods=["POST"])
def api_inventory_sync():
    storage.init_db()
    count = order_module.sync_inventory_from_woocommerce()
    return _ok({"synced": count})


@app.route("/api/inventory/<sku>/lot", methods=["PUT"])
def api_update_lot(sku: str):
    storage.init_db()
    body = request.get_json(silent=True) or {}
    lot = body.get("lot_number", "")
    ok = compliance_module.update_lot_number(sku, lot)
    return _ok({"updated": ok})


# ── Support tickets ───────────────────────────────────────────────────────────

@app.route("/api/tickets")
def api_tickets():
    storage.init_db()
    status_filter = request.args.get("status")
    limit = int(request.args.get("limit", 50))
    return _ok(storage.get_tickets(status=status_filter, limit=limit))


@app.route("/api/tickets", methods=["POST"])
def api_create_ticket():
    storage.init_db()
    body = request.get_json(silent=True) or {}
    required = ("customer_email", "subject", "message")
    if not all(body.get(f) for f in required):
        return _err("customer_email, subject, and message are required")
    result = support_module.handle_inbound_ticket(
        customer_email=body["customer_email"],
        subject=body["subject"],
        message=body["message"],
        customer_name=body.get("customer_name", ""),
    )
    return _ok(result)


@app.route("/api/tickets/<int:ticket_id>/close", methods=["POST"])
def api_close_ticket(ticket_id: int):
    storage.init_db()
    body = request.get_json(silent=True) or {}
    storage.update_ticket(ticket_id, status="closed",
                          resolution=body.get("resolution", ""),
                          resolved_at=datetime.utcnow().isoformat())
    return _ok({"ticket_id": ticket_id, "status": "closed"})


@app.route("/api/tickets/<int:ticket_id>/respond", methods=["POST"])
def api_respond_ticket(ticket_id: int):
    storage.init_db()
    body = request.get_json(silent=True) or {}
    response_text = body.get("response", "")
    tickets = storage.get_tickets()
    ticket = next((t for t in tickets if t["id"] == ticket_id), None)
    if not ticket:
        return _err("Ticket not found", 404)
    if response_text and config.email.is_configured:
        html = f"<p>{response_text.replace(chr(10), '<br>')}</p>"
        email_comms.get_mailer().send(
            ticket["customer_email"],
            f"Re: {ticket['subject']} [Ticket #{ticket_id}]",
            email_comms._html_wrapper("Support Response", html),
        )
    storage.update_ticket(ticket_id, status="resolved",
                          resolution=response_text,
                          resolved_at=datetime.utcnow().isoformat())
    return _ok({"ticket_id": ticket_id, "sent": bool(response_text)})


# ── Accounting ────────────────────────────────────────────────────────────────

@app.route("/api/accounting")
def api_accounting():
    storage.init_db()
    period_start = request.args.get("from")
    period_end = request.args.get("to")
    return _ok(storage.get_accounting_summary(period_start, period_end))


@app.route("/api/accounting/bas")
def api_bas():
    storage.init_db()
    q_start, q_end = acct_module.current_quarter_dates()
    start = request.args.get("from", q_start)
    end = request.args.get("to", q_end)
    return _ok(acct_module.generate_bas_report(start, end))


@app.route("/api/accounting/expense", methods=["POST"])
def api_record_expense():
    storage.init_db()
    body = request.get_json(silent=True) or {}
    if not body.get("amount") or not body.get("description"):
        return _err("amount and description are required")
    acct_module.record_expense(
        amount=float(body["amount"]),
        description=body["description"],
        category=body.get("category", "general"),
        gst_included=body.get("gst_included", True),
        reference_id=body.get("reference_id", ""),
    )
    return _ok({"recorded": True})


# ── Marketing / social media ──────────────────────────────────────────────────

@app.route("/api/posts")
def api_posts():
    storage.init_db()
    platform = request.args.get("platform")
    status = request.args.get("status")
    limit = int(request.args.get("limit", 20))
    return _ok(storage.get_posts(platform=platform, status=status, limit=limit))


@app.route("/api/posts/generate", methods=["POST"])
def api_generate_post():
    storage.init_db()
    body = request.get_json(silent=True) or {}
    topic = body.get("topic", "")
    platform = body.get("platform", "linkedin")
    content_type = body.get("content_type", "educational")
    if not topic:
        return _err("topic is required")
    import agent as ag
    agent = ag.get_agent()
    resp = agent.run(
        f"Generate a {content_type} post about '{topic}' for {platform} and schedule it."
    )
    return _ok({"response": resp})


@app.route("/api/posts/flush", methods=["POST"])
def api_flush_posts():
    storage.init_db()
    from scheduler import flush_due_posts
    results = flush_due_posts()
    return _ok({"flushed": len(results), "results": results})


# ── Compliance ────────────────────────────────────────────────────────────────

@app.route("/api/compliance/coas")
def api_coa_files():
    return _ok(compliance_module.list_coa_files())


@app.route("/api/compliance/backup", methods=["POST"])
def api_backup():
    storage.init_db()
    result = compliance_module.run_backup()
    return _ok(result)


# ── Automations ───────────────────────────────────────────────────────────────

@app.route("/api/automations")
def api_automations():
    storage.init_db()
    return _ok(storage.get_automation_config())


@app.route("/api/automations/<name>/toggle", methods=["POST"])
def api_toggle_automation(name: str):
    storage.init_db()
    body = request.get_json(silent=True) or {}
    enabled = bool(body.get("enabled", True))
    storage.set_automation_enabled(name, enabled)
    return _ok({"name": name, "enabled": enabled})


@app.route("/api/automations/<name>/run", methods=["POST"])
def api_run_automation(name: str):
    storage.init_db()
    result = _run_automation(name)
    return _ok(result)


def _run_automation(name: str) -> dict:
    """Manually trigger a named automation."""
    if name == "inventory_sync":
        count = order_module.sync_inventory_from_woocommerce()
        return {"automation": name, "result": f"Synced {count} products"}

    if name == "order_processing":
        count = order_module.fetch_and_sync_orders()
        return {"automation": name, "result": f"Processed {count} orders"}

    if name == "low_stock_alert":
        items = alert_module.check_low_stock()
        return {"automation": name, "result": f"{len(items)} low-stock alerts sent"}

    if name == "backup":
        result = compliance_module.run_backup()
        return {"automation": name, "result": result}

    if name == "social_marketing":
        from scheduler import flush_due_posts
        results = flush_due_posts()
        return {"automation": name, "result": f"Published {len(results)} scheduled posts"}

    return {"automation": name, "result": "No runner registered for this automation"}


# ── Alerts ────────────────────────────────────────────────────────────────────

@app.route("/api/alerts")
def api_alerts():
    storage.init_db()
    return _ok(alert_module.get_all_alerts())


# ── App entry point ────────────────────────────────────────────────────────────

def create_app():
    storage.init_db()
    # Ensure COA and backup dirs exist
    Path(config.compliance.coa_directory).mkdir(parents=True, exist_ok=True)
    Path(config.compliance.backup_directory).mkdir(parents=True, exist_ok=True)
    return app


if __name__ == "__main__":
    create_app()
    app.run(
        host=config.dashboard.host,
        port=config.dashboard.port,
        debug=config.dashboard.debug,
    )
