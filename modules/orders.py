"""Order processing & fulfilment — WooCommerce REST API integration."""
import hashlib
import hmac
import json
import logging
from typing import Optional

import requests

import config
import storage

logger = logging.getLogger(__name__)


class WooCommerceClient:
    def __init__(self):
        self.base = config.woocommerce.site_url.rstrip("/") + "/wp-json/wc/v3"
        self.auth = (config.woocommerce.consumer_key, config.woocommerce.consumer_secret)

    def _get(self, endpoint: str, params: dict = None) -> list | dict:
        url = f"{self.base}/{endpoint}"
        resp = requests.get(url, auth=self.auth, params=params or {}, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def _put(self, endpoint: str, data: dict) -> dict:
        url = f"{self.base}/{endpoint}"
        resp = requests.put(url, auth=self.auth, json=data, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def get_orders(self, status: str = "processing", per_page: int = 50) -> list:
        return self._get("orders", {"status": status, "per_page": per_page})

    def get_products(self, per_page: int = 100) -> list:
        return self._get("products", {"per_page": per_page})

    def update_order_status(self, wc_order_id: str, status: str) -> dict:
        return self._put(f"orders/{wc_order_id}", {"status": status})

    def add_order_note(self, wc_order_id: str, note: str, customer_note: bool = False) -> dict:
        url = f"{self.base}/orders/{wc_order_id}/notes"
        resp = requests.post(url, auth=self.auth,
                             json={"note": note, "customer_note": customer_note}, timeout=15)
        resp.raise_for_status()
        return resp.json()


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    secret = config.woocommerce.webhook_secret
    if not secret:
        return True  # Skip verification if no secret configured
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


def process_webhook_order(order_data: dict) -> dict:
    """Handle an incoming WooCommerce order webhook payload."""
    wc_id = str(order_data.get("id", ""))
    customer_email = order_data.get("billing", {}).get("email", "")
    customer_name = (
        order_data.get("billing", {}).get("first_name", "") + " "
        + order_data.get("billing", {}).get("last_name", "")
    ).strip()
    status = order_data.get("status", "pending")
    total = float(order_data.get("total", 0))

    items = [
        {
            "sku": li.get("sku", ""),
            "name": li.get("name", ""),
            "quantity": li.get("quantity", 1),
            "price": float(li.get("price", 0)),
        }
        for li in order_data.get("line_items", [])
    ]

    shipping = order_data.get("shipping", {})

    order_id = storage.upsert_order(
        wc_order_id=wc_id,
        customer_email=customer_email,
        customer_name=customer_name,
        status=status,
        total=total,
        items=items,
        shipping_address=shipping,
    )

    # Keep customer record up to date
    storage.upsert_customer(
        email=customer_email,
        name=customer_name,
        wc_customer_id=str(order_data.get("customer_id", "")),
    )

    # Deduct inventory for new/processing orders
    if status in ("processing", "completed"):
        for item in items:
            if item["sku"]:
                storage.adjust_inventory(item["sku"], -item["quantity"])
        storage.increment_customer_orders(customer_email, total)

    storage.log_automation_run(
        "order_processing", "success",
        f"Processed order #{wc_id} ({status}) for {customer_email}",
        records_processed=1,
    )
    return {"order_id": order_id, "wc_order_id": wc_id, "status": status}


def fetch_and_sync_orders() -> int:
    """Pull pending WooCommerce orders and store them locally."""
    if not config.woocommerce.is_configured:
        return 0
    client = WooCommerceClient()
    try:
        wc_orders = client.get_orders(status="processing")
        count = 0
        for o in wc_orders:
            process_webhook_order(o)
            count += 1
        storage.log_automation_run("order_processing", "success",
                                   f"Synced {count} orders from WooCommerce", count)
        return count
    except Exception as exc:
        logger.exception("Order sync failed")
        storage.log_automation_run("order_processing", "error", str(exc))
        return 0


def sync_inventory_from_woocommerce() -> int:
    """Pull product stock levels from WooCommerce into local inventory."""
    if not config.woocommerce.is_configured:
        return 0
    client = WooCommerceClient()
    try:
        products = client.get_products()
        count = 0
        for p in products:
            sku = p.get("sku", "") or f"wc-{p['id']}"
            storage.upsert_inventory(
                sku=sku,
                name=p.get("name", ""),
                quantity=int(p.get("stock_quantity") or 0),
                reorder_point=10,
                unit_cost=float(p.get("regular_price") or 0),
            )
            count += 1
        storage.log_automation_run("inventory_sync", "success",
                                   f"Synced {count} products", count)
        return count
    except Exception as exc:
        logger.exception("Inventory sync failed")
        storage.log_automation_run("inventory_sync", "error", str(exc))
        return 0


def get_low_stock_items() -> list[dict]:
    return storage.get_inventory(low_stock_only=True)
