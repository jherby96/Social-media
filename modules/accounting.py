"""Accounting & Tax — record sales/expenses, generate BAS summary."""
import logging
from datetime import datetime, date
from typing import Optional

import config
import storage

logger = logging.getLogger(__name__)

GST_RATE = config.accounting.gst_rate  # default 0.10 (10%)


def record_sale_from_order(order: dict) -> None:
    """Create an accounting entry for a completed order."""
    total = float(order.get("total", 0))
    # GST-inclusive: GST = total * rate / (1 + rate)
    gst = round(total * GST_RATE / (1 + GST_RATE), 2)
    ex_gst = round(total - gst, 2)
    storage.record_accounting_entry(
        entry_type="sale",
        amount=ex_gst,
        gst_amount=gst,
        description=f"Order #{order.get('wc_order_id', order.get('id', ''))}",
        category="peptide_sales",
        reference_id=str(order.get("wc_order_id", "")),
    )
    storage.log_automation_run(
        "accounting_record", "success",
        f"Recorded sale ${total:.2f} (GST ${gst:.2f})", 1
    )


def record_expense(amount: float, description: str, category: str = "general",
                   gst_included: bool = True, reference_id: str = "") -> None:
    if gst_included:
        gst = round(amount * GST_RATE / (1 + GST_RATE), 2)
        ex_gst = round(amount - gst, 2)
    else:
        gst = 0.0
        ex_gst = amount
    storage.record_accounting_entry(
        entry_type="expense",
        amount=ex_gst,
        gst_amount=gst,
        description=description,
        category=category,
        reference_id=reference_id,
    )


def generate_bas_report(period_start: str, period_end: str) -> dict:
    """Generate a BAS (Business Activity Statement) summary for a date range."""
    summary = storage.get_accounting_summary(period_start, period_end)
    bas = {
        "period_start": period_start,
        "period_end": period_end,
        "currency": config.accounting.currency,
        "business_name": config.accounting.business_name,
        "abn": config.accounting.abn,
        "total_sales_ex_gst": summary["sales"],
        "total_expenses_ex_gst": summary["expenses"],
        "gross_profit": summary["profit"],
        "g1_total_sales": round(summary["sales"] + summary["gst_collected"], 2),
        "1a_gst_on_sales": summary["gst_collected"],
        "1b_gst_on_purchases": summary["gst_paid"],
        "net_gst_payable": summary["gst_net_payable"],
    }
    return bas


def current_quarter_dates() -> tuple[str, str]:
    today = date.today()
    quarter = (today.month - 1) // 3
    start_month = quarter * 3 + 1
    start = date(today.year, start_month, 1)
    # End of quarter
    end_month = start_month + 2
    if end_month == 12:
        end = date(today.year, 12, 31)
    else:
        import calendar
        end = date(today.year, end_month, calendar.monthrange(today.year, end_month)[1])
    return start.isoformat(), end.isoformat()


def get_dashboard_financials() -> dict:
    """Quick financials for the dashboard KPI cards."""
    today = date.today().isoformat()
    month_start = date.today().replace(day=1).isoformat()
    month_summary = storage.get_accounting_summary(month_start, today)
    q_start, q_end = current_quarter_dates()
    quarter_summary = storage.get_accounting_summary(q_start, q_end)
    return {
        "month_revenue": month_summary["sales"],
        "month_expenses": month_summary["expenses"],
        "month_profit": month_summary["profit"],
        "quarter_gst_payable": quarter_summary["gst_net_payable"],
    }
