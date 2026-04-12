"""
whatsapp_approvals.utils.whatsapp
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Meta WhatsApp Cloud API wrapper.

Public functions
----------------
send_approval_message(doc, rule_doc, phone)
    Builds an interactive-button message from the rule's fields_to_display
    list and sends it to `phone`.  Creates a WhatsApp Approval Log entry.

send_text_message(phone, text)
    Sends a plain text message (confirmations, rejections).

mark_as_read(wamid)
    Marks an incoming message as read (double blue tick).
"""
import frappe
import requests
from frappe import _
from frappe.utils import now_datetime, fmt_money


def _settings():
    s = frappe.get_single("WhatsApp Approval Settings")
    if not s.phone_number_id or not s.access_token:
        frappe.throw(
            _("WhatsApp Approval Settings are incomplete. Configure Phone Number ID and Access Token."),
            title=_("Configuration Error"),
        )
    return s


def _api_url(s):
    return f"https://graph.facebook.com/{s.api_version or 'v19.0'}/{s.phone_number_id}/messages"


def _headers(s):
    return {
        "Authorization": f"Bearer {s.get_password('access_token')}",
        "Content-Type":  "application/json",
    }


def _post(s, payload):
    """POST to Meta API. Returns (wamid | None, error_msg | None)."""
    try:
        r = requests.post(_api_url(s), headers=_headers(s), json=payload, timeout=15)
        data = r.json()
        if r.status_code == 200 and data.get("messages"):
            return data["messages"][0]["id"], None
        return None, data.get("error", {}).get("message", str(data))
    except Exception as e:
        return None, str(e)


# ─────────────────────────────────────────────────────────────────────────────
# Dynamic message builder
# ─────────────────────────────────────────────────────────────────────────────

def _format_value(doc, row):
    raw = doc.get(row.fieldname)
    if raw is None or raw == "":
        return "—"

    ft = (row.fieldtype or "").strip()

    if ft == "Currency":
        return fmt_money(raw, currency=doc.get("currency") or "INR")

    if ft == "Date":
        return frappe.format(raw, {"fieldtype": "Date"})

    if ft == "Datetime":
        return frappe.format(raw, {"fieldtype": "Datetime"})

    if ft == "Check":
        return "Yes" if raw else "No"

    if ft == "Table":
        rows = doc.get(row.fieldname) or []
        if not rows:
            return "—"
        lines = []
        currency = doc.get("currency") or "INR"
        for i, child in enumerate(rows[:5]):
            name   = child.get("item_name") or child.get("item_code") or f"Row {i+1}"
            qty    = child.get("qty", "")
            uom    = child.get("uom", "")
            rate   = child.get("rate")
            parts  = [name]
            if qty:
                parts.append(f"{qty} {uom}".strip())
            if rate is not None:
                parts.append(f"@ {fmt_money(rate, currency=currency)}")
            lines.append("  • " + "  ".join(filter(None, parts)))
        if len(rows) > 5:
            lines.append(f"  …and {len(rows) - 5} more row(s)")
        return "\n" + "\n".join(lines)

    return str(raw)


def _build_body(doc, rule_doc):
    title = rule_doc.message_title or f"{doc.doctype} Approval Request"
    lines = [f"📋 *{title}*\n", f"*Reference:* {doc.name}\n"]
    for row in rule_doc.fields_to_display:
        label = row.label or row.fieldname
        value = _format_value(doc, row)
        lines.append(f"*{label}:* {value}")
    lines.append("\n_Please review and tap a button below._")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def send_approval_message(doc, rule_doc, phone):
    """
    Build and send the interactive button message.
    Creates a WhatsApp Approval Log. Returns the log name.

    Button ID format:  ACTION|DOCTYPE|DOCNAME
    """
    s         = _settings()
    body_text = _build_body(doc, rule_doc)

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type":    "individual",
        "to":                phone,
        "type":              "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body_text},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {
                        "id":    f"APPROVE|{doc.doctype}|{doc.name}",
                        "title": "✅ Approve",
                    }},
                    {"type": "reply", "reply": {
                        "id":    f"REJECT|{doc.doctype}|{doc.name}",
                        "title": "❌ Reject",
                    }},
                ]
            },
        },
    }

    wamid, error = _post(s, payload)

    # Create Approval Log
    log = frappe.get_doc({
        "doctype":           "WhatsApp Approval Log",
        "reference_doctype": doc.doctype,
        "reference_name":    doc.name,
        "rule_name":         rule_doc.name,
        "status":            "Pending" if wamid else "Failed",
        "wa_message_id":     wamid or "",
        "approver_phone":    phone,
        "sent_at":           now_datetime(),
        "notes":             f"Error: {error}" if error else "",
    })
    log.insert(ignore_permissions=True)

    if error:
        frappe.log_error(title=f"WA send failed: {doc.doctype} {doc.name}", message=error)
        frappe.msgprint(_(f"WhatsApp message could not be sent: {error}"), indicator="red", alert=True)
    else:
        # Write wa_approval_status on the document if custom field exists
        meta = frappe.get_meta(doc.doctype)
        if meta.has_field("wa_approval_status"):
            frappe.db.set_value(
                doc.doctype, doc.name,
                {"wa_approval_status": "Pending", "wa_approval_message_id": wamid},
                update_modified=False,
            )

    return log.name


def send_text_message(phone, text):
    """Send a plain text WhatsApp message. Returns wamid or None."""
    s = _settings()
    wamid, error = _post(s, {
        "messaging_product": "whatsapp",
        "recipient_type":    "individual",
        "to":                phone,
        "type":              "text",
        "text":              {"preview_url": False, "body": text},
    })
    if error:
        frappe.log_error(title="WA text send failed", message=error)
    return wamid


def mark_as_read(wamid):
    """Mark incoming message as read (shows double blue tick)."""
    s = _settings()
    try:
        requests.post(
            _api_url(s), headers=_headers(s),
            json={"messaging_product": "whatsapp", "status": "read", "message_id": wamid},
            timeout=10,
        )
    except Exception:
        pass
