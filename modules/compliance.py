"""Compliance & Documentation — COA delivery, lot tracking, database backups."""
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

import config
import storage
from modules.email_comms import send_coa_email

logger = logging.getLogger(__name__)


def get_coa_path(product_sku: str, lot_number: str) -> Optional[Path]:
    """Look up the COA file for a given SKU + lot number."""
    coa_dir = Path(config.compliance.coa_directory)
    if not coa_dir.exists():
        return None
    # Search for matching file (PDF or image)
    for ext in ("pdf", "PDF", "jpg", "png"):
        candidates = list(coa_dir.glob(f"*{product_sku}*{lot_number}*.{ext}"))
        if candidates:
            return candidates[0]
        # Fallback: any file with just the SKU
        candidates = list(coa_dir.glob(f"*{product_sku}*.{ext}"))
        if candidates:
            return candidates[0]
    return None


def deliver_coas_for_order(order: dict) -> list[dict]:
    """Find and email COAs for every line item in an order."""
    results = []
    items = order.get("items", [])
    if isinstance(items, str):
        import json
        items = json.loads(items)

    for item in items:
        sku = item.get("sku", "")
        if not sku:
            continue

        # Find lot number from inventory
        inv = storage.get_inventory()
        lot = next((i["lot_number"] for i in inv if i["sku"] == sku and i.get("lot_number")), "")

        coa_path = get_coa_path(sku, lot)
        if coa_path:
            ok = send_coa_email(order, coa_path, item["name"], lot or "N/A")
            storage.log_coa_delivery(
                order_id=order.get("id", 0),
                customer_email=order.get("customer_email", ""),
                product_sku=sku,
                lot_number=lot or "N/A",
                coa_filename=coa_path.name,
            )
            results.append({"sku": sku, "sent": ok, "coa_file": coa_path.name})
        else:
            logger.warning("No COA found for SKU %s lot %s", sku, lot)
            results.append({"sku": sku, "sent": False, "coa_file": None})

    if results:
        storage.log_automation_run(
            "coa_delivery", "success",
            f"Delivered {sum(1 for r in results if r['sent'])} COAs for order #{order.get('wc_order_id', '')}",
            len(results),
        )
    return results


def update_lot_number(sku: str, lot_number: str) -> bool:
    """Update the lot number for an inventory item."""
    inv = storage.get_inventory()
    existing = next((i for i in inv if i["sku"] == sku), None)
    if not existing:
        return False
    storage.upsert_inventory(
        sku=sku,
        name=existing["name"],
        quantity=existing["quantity"],
        lot_number=lot_number,
        reorder_point=existing["reorder_point"],
        unit_cost=existing.get("unit_cost", 0.0),
    )
    return True


def run_backup() -> dict:
    """Back up the SQLite database to the backup directory."""
    backup_dir = Path(config.compliance.backup_directory)
    backup_dir.mkdir(parents=True, exist_ok=True)
    db_path = Path(config.agent.db_path)
    if not db_path.exists():
        return {"success": False, "error": "Database file not found"}

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    dest = backup_dir / f"backup_{timestamp}_{db_path.name}"
    try:
        shutil.copy2(db_path, dest)
        # Keep only the 30 most recent backups
        backups = sorted(backup_dir.glob("backup_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in backups[30:]:
            old.unlink(missing_ok=True)
        storage.log_automation_run("backup", "success", f"Backup saved: {dest.name}", 1)
        return {"success": True, "file": str(dest), "size_kb": round(dest.stat().st_size / 1024, 1)}
    except Exception as exc:
        logger.exception("Backup failed")
        storage.log_automation_run("backup", "error", str(exc))
        return {"success": False, "error": str(exc)}


def list_coa_files() -> list[dict]:
    """List all COA files available in the COA directory."""
    coa_dir = Path(config.compliance.coa_directory)
    if not coa_dir.exists():
        return []
    files = []
    for f in sorted(coa_dir.iterdir()):
        if f.suffix.lower() in (".pdf", ".jpg", ".jpeg", ".png"):
            files.append({
                "name": f.name,
                "size_kb": round(f.stat().st_size / 1024, 1),
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            })
    return files
