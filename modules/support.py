"""Customer support — Claude-powered auto-responses and ticket routing."""
import json
import logging
from typing import Optional

import anthropic

import config
import storage
from modules.email_comms import get_mailer, _html_wrapper

logger = logging.getLogger(__name__)

CATEGORIES = {
    "order_status": "Order tracking / status enquiry",
    "shipping": "Shipping / delivery question",
    "product_info": "Product information / peptide question",
    "coa_request": "COA / documentation request",
    "return_refund": "Return or refund request",
    "billing": "Billing / payment issue",
    "technical": "Technical / research question",
    "other": "Other / general enquiry",
}

SUPPORT_SYSTEM = f"""You are a knowledgeable and empathetic customer support agent for {config.agent.brand_name},
a peptide ecommerce store selling research-grade peptides.

Your role:
- Answer customer questions clearly and accurately
- Be warm, professional, and concise
- For order-specific queries you don't have data for, apologise and say the team will follow up within 1 business day
- Never make up information about specific orders or stock
- For COA requests, confirm the team will send it promptly
- Keep responses under 200 words

Peptide knowledge:
- Peptides are for research purposes only
- Common peptides: BPC-157, TB-500, Semaglutide, Tirzepatide, HGH, IGF-1, etc.
- All products come with COAs from third-party labs
- Standard shipping is 2-5 business days domestically
- Returns accepted within 30 days for unopened products
"""


def classify_and_respond(subject: str, message: str) -> tuple[str, str]:
    """Use Claude to classify a ticket and draft an auto-response. Returns (category, response)."""
    client = anthropic.Anthropic(api_key=config.agent.anthropic_api_key)

    prompt = f"""A customer submitted a support ticket.

Subject: {subject}
Message: {message}

Step 1: Classify this ticket into ONE of these categories:
{json.dumps(CATEGORIES, indent=2)}

Step 2: Write a helpful auto-response to send to the customer.

Respond in JSON format only:
{{
  "category": "<category_key>",
  "response": "<the auto-response text>"
}}"""

    resp = client.messages.create(
        model=config.agent.model,
        max_tokens=512,
        system=SUPPORT_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    data = json.loads(text)
    return data.get("category", "other"), data.get("response", "")


def handle_inbound_ticket(customer_email: str, subject: str, message: str,
                           customer_name: str = "", order_id: Optional[int] = None) -> dict:
    """Create a ticket, auto-classify, auto-respond, and email the customer."""
    # Create ticket
    ticket_id = storage.create_ticket(
        customer_email=customer_email,
        subject=subject,
        message=message,
        customer_name=customer_name,
        order_id=order_id,
    )

    category = "other"
    auto_response = ""

    # Claude auto-classify and draft response
    if config.agent.is_configured:
        try:
            category, auto_response = classify_and_respond(subject, message)
        except Exception:
            logger.exception("Claude classification failed for ticket %d", ticket_id)

    # Save classification and auto-response
    storage.update_ticket(ticket_id, category=category, auto_response=auto_response)

    # Email the auto-response back to the customer
    if auto_response and config.email.is_configured:
        name = customer_name.split()[0] if customer_name else "there"
        html_body = f"""
<p>Hi {name},</p>
<p>Thank you for contacting <strong>{config.agent.brand_name}</strong> support. We've received your message and here's an initial response:</p>
<blockquote style="border-left:3px solid #0d9488;margin:16px 0;padding:8px 16px;color:#555">
  {auto_response.replace(chr(10), '<br>')}
</blockquote>
<p>A member of our team will review your ticket and follow up if needed.</p>
<p>Your ticket reference: <strong>#{ticket_id}</strong></p>
<p>The {config.agent.brand_name} Support Team</p>
"""
        email_subject = f"Re: {subject} [Ticket #{ticket_id}]"
        mailer = get_mailer()
        ok = mailer.send(customer_email, email_subject, _html_wrapper("Support Response", html_body))
        storage.log_email(customer_email, "support_auto_response", email_subject,
                          status="sent" if ok else "failed")

    storage.log_automation_run(
        "support_auto_respond", "success",
        f"Ticket #{ticket_id} created and auto-responded (category: {category})", 1,
    )

    return {
        "ticket_id": ticket_id,
        "category": category,
        "auto_response": auto_response,
    }


def get_ticket_summary() -> dict:
    open_tickets = storage.get_tickets(status="open", limit=100)
    by_category: dict[str, int] = {}
    for t in open_tickets:
        cat = t.get("category") or "other"
        by_category[cat] = by_category.get(cat, 0) + 1
    return {
        "open": len(open_tickets),
        "by_category": by_category,
    }
