"""Customer communication — SMTP-based email flows (no 3rd-party required)."""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import Optional

import config
import storage

logger = logging.getLogger(__name__)


class SMTPMailer:
    def __init__(self):
        self.cfg = config.email

    def send(self, to: str, subject: str, html_body: str,
             text_body: str = "", attachments: list[Path] = None) -> bool:
        if not self.cfg.is_configured:
            logger.warning("Email not configured — skipping send to %s", to)
            return False
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = f"{self.cfg.from_name} <{self.cfg.from_email}>"
            msg["To"] = to
            msg["Subject"] = subject
            if text_body:
                msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            for path in (attachments or []):
                if path.exists():
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(path.read_bytes())
                    encoders.encode_base64(part)
                    part.add_header("Content-Disposition", f'attachment; filename="{path.name}"')
                    msg.attach(part)

            with smtplib.SMTP(self.cfg.smtp_host, self.cfg.smtp_port) as smtp:
                smtp.starttls()
                smtp.login(self.cfg.smtp_user, self.cfg.smtp_password)
                smtp.send_message(msg)
            return True
        except Exception:
            logger.exception("Failed to send email to %s", to)
            return False


_mailer: Optional[SMTPMailer] = None


def get_mailer() -> SMTPMailer:
    global _mailer
    if _mailer is None:
        _mailer = SMTPMailer()
    return _mailer


def _html_wrapper(title: str, body_html: str) -> str:
    brand = config.agent.brand_name
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
  body{{font-family:Arial,sans-serif;background:#f4f4f4;margin:0;padding:0}}
  .wrap{{max-width:600px;margin:40px auto;background:#fff;border-radius:8px;overflow:hidden}}
  .header{{background:#0d9488;padding:24px 32px;color:#fff}}
  .header h1{{margin:0;font-size:22px}}
  .body{{padding:32px;color:#333;line-height:1.6}}
  .footer{{background:#f9fafb;padding:16px 32px;font-size:12px;color:#888;text-align:center}}
  .btn{{display:inline-block;background:#0d9488;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;margin-top:16px}}
</style></head>
<body><div class="wrap">
  <div class="header"><h1>{brand}</h1><p style="margin:4px 0 0;opacity:.85">{title}</p></div>
  <div class="body">{body_html}</div>
  <div class="footer">© {brand} · <a href="mailto:{config.email.support_email or config.email.from_email}">{config.email.support_email or config.email.from_email}</a></div>
</div></body></html>"""


def send_welcome_email(customer_email: str, customer_name: str) -> bool:
    name = customer_name.split()[0] if customer_name else "there"
    brand = config.agent.brand_name
    subject = f"Welcome to {brand}!"
    body = f"""
<p>Hi {name},</p>
<p>Thank you for creating an account with <strong>{brand}</strong>. We're thrilled to have you as part of our community.</p>
<p>As a trusted supplier of research-grade peptides, we're committed to quality, compliance, and fast delivery.</p>
<p><strong>What happens next?</strong></p>
<ul>
  <li>Browse our catalogue and place your first order</li>
  <li>Every order ships with a Certificate of Analysis (COA)</li>
  <li>Our support team is here if you have any questions</li>
</ul>
<a href="{config.woocommerce.site_url}" class="btn">Shop Now</a>
<p>Thanks again,<br>The {brand} Team</p>
"""
    ok = get_mailer().send(customer_email, subject, _html_wrapper("Welcome!", body))
    storage.log_email(customer_email, "welcome", subject, status="sent" if ok else "failed")
    return ok


def send_order_confirmation(order: dict) -> bool:
    email = order.get("customer_email", "")
    name = (order.get("customer_name", "") or "").split()[0] or "there"
    order_ref = order.get("wc_order_id") or order.get("id", "")
    total = float(order.get("total", 0))
    items = order.get("items", [])
    items_html = "".join(
        f"<tr><td>{i['name']}</td><td style='text-align:right'>x{i['quantity']}</td>"
        f"<td style='text-align:right'>${float(i['price'])*i['quantity']:.2f}</td></tr>"
        for i in items
    )
    subject = f"Order Confirmation #{order_ref}"
    body = f"""
<p>Hi {name},</p>
<p>We've received your order <strong>#{order_ref}</strong> and it's being processed now.</p>
<table style="width:100%;border-collapse:collapse;margin:16px 0">
  <thead><tr style="background:#f3f4f6"><th style="text-align:left;padding:8px">Item</th>
  <th style="text-align:right;padding:8px">Qty</th><th style="text-align:right;padding:8px">Amount</th></tr></thead>
  <tbody>{items_html}</tbody>
  <tfoot><tr><td colspan="2" style="text-align:right;padding:8px;font-weight:bold">Total</td>
  <td style="text-align:right;padding:8px;font-weight:bold">${total:.2f}</td></tr></tfoot>
</table>
<p>Your Certificate of Analysis (COA) will be emailed once your order ships.</p>
<p>Thanks,<br>The {config.agent.brand_name} Team</p>
"""
    ok = get_mailer().send(email, subject, _html_wrapper(f"Order #{order_ref}", body))
    storage.log_email(email, "order_confirmation", subject,
                      order_id=order.get("id"), status="sent" if ok else "failed")
    return ok


def send_shipping_notification(order: dict, tracking_number: str) -> bool:
    email = order.get("customer_email", "")
    name = (order.get("customer_name", "") or "").split()[0] or "there"
    order_ref = order.get("wc_order_id") or order.get("id", "")
    subject = f"Your order #{order_ref} has shipped!"
    body = f"""
<p>Hi {name},</p>
<p>Great news — your order <strong>#{order_ref}</strong> is on its way!</p>
<p><strong>Tracking number:</strong> {tracking_number}</p>
<p>Please allow 1–2 business days for tracking to update.</p>
<p>Thanks,<br>The {config.agent.brand_name} Team</p>
"""
    ok = get_mailer().send(email, subject, _html_wrapper("Your order has shipped!", body))
    storage.log_email(email, "shipping_notification", subject,
                      order_id=order.get("id"), status="sent" if ok else "failed")
    return ok


def send_post_purchase_email(order: dict) -> bool:
    email = order.get("customer_email", "")
    name = (order.get("customer_name", "") or "").split()[0] or "there"
    order_ref = order.get("wc_order_id") or order.get("id", "")
    subject = f"How was your order #{order_ref}?"
    body = f"""
<p>Hi {name},</p>
<p>We hope you're happy with your recent order from <strong>{config.agent.brand_name}</strong>.</p>
<p>If you have any questions about your peptides or need support with your research, our team is here to help.</p>
<p>We'd also love to hear your feedback — it helps us improve.</p>
<a href="mailto:{config.email.support_email or config.email.from_email}?subject=Feedback on order #{order_ref}" class="btn">Share Feedback</a>
<p>Thanks for choosing us,<br>The {config.agent.brand_name} Team</p>
"""
    ok = get_mailer().send(email, subject, _html_wrapper("Post-Purchase Check-in", body))
    storage.log_email(email, "post_purchase", subject,
                      order_id=order.get("id"), status="sent" if ok else "failed")
    return ok


def send_review_request(order: dict) -> bool:
    email = order.get("customer_email", "")
    name = (order.get("customer_name", "") or "").split()[0] or "there"
    order_ref = order.get("wc_order_id") or order.get("id", "")
    site = config.woocommerce.site_url
    subject = f"Quick favour — leave us a review?"
    body = f"""
<p>Hi {name},</p>
<p>It's been a little while since your order <strong>#{order_ref}</strong> arrived, and we'd love to know what you think.</p>
<p>Would you mind leaving us a quick review? It takes less than a minute and helps other researchers find us.</p>
<a href="{site}/#reviews" class="btn">Leave a Review</a>
<p>Thank you so much,<br>The {config.agent.brand_name} Team</p>
"""
    ok = get_mailer().send(email, subject, _html_wrapper("Leave Us a Review", body))
    storage.log_email(email, "review_request", subject,
                      order_id=order.get("id"), status="sent" if ok else "failed")
    return ok


def send_coa_email(order: dict, coa_path: Path, product_name: str, lot_number: str) -> bool:
    email = order.get("customer_email", "")
    name = (order.get("customer_name", "") or "").split()[0] or "there"
    order_ref = order.get("wc_order_id") or order.get("id", "")
    subject = f"Certificate of Analysis — {product_name} (Order #{order_ref})"
    body = f"""
<p>Hi {name},</p>
<p>Please find attached the <strong>Certificate of Analysis (COA)</strong> for your order.</p>
<ul>
  <li><strong>Product:</strong> {product_name}</li>
  <li><strong>Lot Number:</strong> {lot_number}</li>
  <li><strong>Order:</strong> #{order_ref}</li>
</ul>
<p>Please store this document for your records. If you have any questions, contact our team.</p>
<p>Best regards,<br>The {config.agent.brand_name} Team</p>
"""
    attachments = [coa_path] if coa_path and coa_path.exists() else []
    ok = get_mailer().send(email, subject, _html_wrapper("Certificate of Analysis", body),
                           attachments=attachments)
    storage.log_email(email, "coa_delivery", subject,
                      order_id=order.get("id"), status="sent" if ok else "failed")
    return ok


def send_low_stock_alert(items: list[dict]) -> bool:
    """Internal alert email to the store owner."""
    to = config.email.support_email or config.email.from_email
    if not to:
        return False
    rows = "".join(
        f"<tr><td>{i['name']}</td><td>{i['sku']}</td>"
        f"<td style='color:{'#dc2626' if i['quantity']==0 else '#d97706'}'>{i['quantity']}</td>"
        f"<td>{i['reorder_point']}</td></tr>"
        for i in items
    )
    subject = f"Low Stock Alert — {len(items)} item(s) need restocking"
    body = f"""
<p>The following products are at or below their reorder threshold:</p>
<table style="width:100%;border-collapse:collapse;margin:16px 0">
  <thead><tr style="background:#f3f4f6">
    <th style="text-align:left;padding:8px">Product</th>
    <th style="text-align:left;padding:8px">SKU</th>
    <th style="text-align:right;padding:8px">Stock</th>
    <th style="text-align:right;padding:8px">Reorder At</th>
  </tr></thead>
  <tbody>{rows}</tbody>
</table>
<p>Please restock these items promptly to avoid order delays.</p>
"""
    return get_mailer().send(to, subject, _html_wrapper("Low Stock Alert", body))
