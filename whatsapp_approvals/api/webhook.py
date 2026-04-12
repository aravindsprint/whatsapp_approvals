"""
whatsapp_approvals.api.webhook
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Meta WhatsApp Cloud API webhook.

  GET  → verify token challenge
  POST → receive button replies

On APPROVE
  1. Update WhatsApp Approval Log  → Approved
  2. Set wa_approval_status = "Approved" on the document (so before_submit passes)
  3. Call doc.submit() — this is what actually submits the ERPNext document
  4. Send confirmation WA back to approver
  5. Notify document owner via Frappe bell

On REJECT
  1. Update WhatsApp Approval Log  → Rejected
  2. Set wa_approval_status = "Rejected" on the document
  3. Add a visible Comment on the document ("Rejected via WhatsApp by …")
  4. Send confirmation WA back to approver
  5. Notify document owner via Frappe bell
"""
import json
import frappe
from frappe import _
from frappe.utils import now_datetime
from whatsapp_approvals.utils.whatsapp import send_text_message, mark_as_read


@frappe.whitelist(allow_guest=True)
def handle():
    method = frappe.local.request.method
    if method == "GET":
        return _verify()
    if method == "POST":
        return _receive()
    frappe.local.response.http_status_code = 405
    return "Method Not Allowed"


# ─────────────────────────────────────────────────────────────────────────────
# GET — webhook verification
# ─────────────────────────────────────────────────────────────────────────────

def _verify():
    p         = frappe.local.request.args
    mode      = p.get("hub.mode")
    challenge = p.get("hub.challenge")
    token     = p.get("hub.verify_token")

    if mode != "subscribe":
        frappe.local.response.http_status_code = 400
        return "Bad Request"

    expected = frappe.get_single("WhatsApp Approval Settings").webhook_verify_token
    if token != expected:
        frappe.local.response.http_status_code = 403
        return "Forbidden"

    frappe.local.response["type"]   = "text"
    frappe.local.response["result"] = challenge
    return challenge


# ─────────────────────────────────────────────────────────────────────────────
# POST — receive messages
# ─────────────────────────────────────────────────────────────────────────────

def _receive():
    try:
        payload = json.loads(frappe.local.request.data or b"{}")
    except Exception:
        frappe.local.response.http_status_code = 400
        return "Invalid JSON"

    # Always return 200 quickly — process errors internally
    try:
        _process(payload)
    except Exception:
        frappe.log_error(title="WA Webhook processing error", message=frappe.get_traceback())

    frappe.local.response.http_status_code = 200
    return "OK"


def _process(payload):
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for msg in value.get("messages", []):
                if msg.get("type") == "interactive":
                    _handle_button(msg, value)


def _handle_button(msg, value):
    interactive = msg.get("interactive", {})
    if interactive.get("type") != "button_reply":
        return

    button         = interactive.get("button_reply", {})
    button_id      = button.get("id", "")
    from_phone     = msg.get("from")
    incoming_wamid = msg.get("id")

    # Mark as read (double blue tick)
    if incoming_wamid:
        mark_as_read(incoming_wamid)

    # Button ID format:  ACTION|DOCTYPE|DOCNAME
    parts = button_id.split("|", 2)
    if len(parts) != 3:
        frappe.log_error(title="WA Webhook: unexpected button_id", message=button_id)
        return

    action, doctype, docname = parts
    action = action.upper()
    if action not in ("APPROVE", "REJECT"):
        return

    # Safety — validate doctype exists
    if not frappe.db.exists("DocType", doctype):
        frappe.log_error(
            title="WA Webhook: unknown doctype in button_id",
            message=button_id,
        )
        return

    # Verify document still exists
    if not frappe.db.exists(doctype, docname):
        frappe.log_error(
            title=f"WA Webhook: document not found — {doctype} {docname}",
            message=button_id,
        )
        return

    # Fetch settings for approver display name
    settings     = frappe.get_single("WhatsApp Approval Settings")
    approver_display = (
        settings.approver_phone_display or settings.approver_name or from_phone or "Approver"
    )

    # Find the most recent pending log
    log_name = frappe.db.get_value(
        "WhatsApp Approval Log",
        {
            "reference_doctype": doctype,
            "reference_name":    docname,
            "status":            "Pending",
        },
        "name",
        order_by="creation desc",
    )

    if not log_name:
        frappe.log_error(
            title=f"WA Webhook: no pending log for {doctype} {docname}",
            message=f"button_id={button_id}, from={from_phone}",
        )
        return

    new_status = "Approved" if action == "APPROVE" else "Rejected"

    # ── 1. Update Approval Log ────────────────────────────────────────────────
    frappe.db.set_value(
        "WhatsApp Approval Log", log_name,
        {
            "status":           new_status,
            "responded_at":     now_datetime(),
            "response_payload": json.dumps(value, indent=2),
        },
        update_modified=True,
    )

    # ── 2. Update document custom fields ─────────────────────────────────────
    meta = frappe.get_meta(doctype)

    doc_updates = {}
    if meta.has_field("wa_approval_status"):
        doc_updates["wa_approval_status"] = new_status
    if meta.has_field("wa_approval_responded_by"):
        doc_updates["wa_approval_responded_by"] = approver_display
    if meta.has_field("wa_approval_responded_at"):
        doc_updates["wa_approval_responded_at"] = now_datetime()

    if doc_updates:
        frappe.db.set_value(doctype, docname, doc_updates, update_modified=False)

    frappe.db.commit()

    # ── 3a. APPROVE — auto-submit the document ────────────────────────────────
    if action == "APPROVE":
        _auto_submit(doctype, docname, approver_display)

    # ── 3b. REJECT — add a comment on the document ───────────────────────────
    elif action == "REJECT":
        _add_rejection_comment(doctype, docname, approver_display)

    # ── 4. Confirmation WA back to approver ──────────────────────────────────
    if settings.send_confirmation_to_approver:
        emoji = "✅" if action == "APPROVE" else "❌"
        send_text_message(
            from_phone or settings.approver_phone,
            f"{emoji} *{new_status}* — {doctype} *{docname}* has been "
            f"{'submitted in ERPNext ✔' if action == 'APPROVE' else 'marked as Rejected. The creator has been notified.'}",
        )

    # ── 5. Bell notification for document owner ───────────────────────────────
    if settings.send_notification_to_creator:
        _notify_owner(doctype, docname, new_status, approver_display)

    frappe.logger().info(f"WA Approval: {doctype} {docname} → {new_status} by {from_phone}")


# ─────────────────────────────────────────────────────────────────────────────
# Auto-submit
# ─────────────────────────────────────────────────────────────────────────────

def _auto_submit(doctype, docname, approver):
    """
    Submit the document programmatically.
    wa_approval_status is already "Approved" in the DB, so when before_submit
    fires again it will see the approved status and pass through immediately.
    """
    try:
        doc = frappe.get_doc(doctype, docname)

        if doc.docstatus == 1:
            # Already submitted (race condition / duplicate webhook delivery)
            frappe.logger().info(
                f"WA Approval: {doctype} {docname} already submitted — skipping auto-submit."
            )
            return

        if doc.docstatus == 2:
            frappe.log_error(
                title=f"WA Approval: cannot submit cancelled doc {doctype} {docname}",
                message=f"Approved by {approver}",
            )
            return

        # docstatus == 0 → Draft, safe to submit
        doc.submit()
        frappe.db.commit()

        frappe.logger().info(
            f"WA Approval: auto-submitted {doctype} {docname} after WhatsApp approval by {approver}"
        )

    except Exception:
        frappe.log_error(
            title=f"WA Approval: auto-submit failed for {doctype} {docname}",
            message=frappe.get_traceback(),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Rejection comment
# ─────────────────────────────────────────────────────────────────────────────

def _add_rejection_comment(doctype, docname, approver):
    """Add a visible comment on the rejected document."""
    try:
        frappe.get_doc({
            "doctype":           "Comment",
            "comment_type":      "Comment",
            "reference_doctype": doctype,
            "reference_name":    docname,
            "content": (
                f"❌ <b>Rejected via WhatsApp</b> by <b>{approver}</b>.<br>"
                "Please review and make corrections before resubmitting for approval."
            ),
        }).insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        frappe.log_error(
            title=f"WA Approval: failed to add rejection comment on {doctype} {docname}",
            message=frappe.get_traceback(),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Owner notification
# ─────────────────────────────────────────────────────────────────────────────

def _notify_owner(doctype, docname, status, approver):
    try:
        owner = frappe.db.get_value(doctype, docname, "owner")
        if not owner:
            return

        emoji = "✅" if status == "Approved" else "❌"
        action_text = (
            "has been <b>submitted</b> automatically."
            if status == "Approved"
            else "was <b>rejected</b>. Please revise and resubmit."
        )

        frappe.get_doc({
            "doctype":       "Notification Log",
            "subject":       f"{emoji} {doctype} {docname} {status} via WhatsApp",
            "email_content": (
                f"{doctype} <b>{docname}</b> was <b>{status.lower()}</b> "
                f"by <b>{approver}</b> via WhatsApp and {action_text}"
            ),
            "for_user":      owner,
            "from_user":     "Administrator",
            "document_type": doctype,
            "document_name": docname,
            "type":          "Alert",
        }).insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        frappe.log_error(
            title=f"WA Approval: owner notification failed for {doctype} {docname}",
            message=frappe.get_traceback(),
        )
