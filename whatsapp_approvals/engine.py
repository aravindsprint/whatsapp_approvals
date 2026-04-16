"""
whatsapp_approvals.engine
~~~~~~~~~~~~~~~~~~~~~~~~~
The rule engine — called by Frappe's "*" wildcard doc_events.

Trigger behaviour
-----------------
before_submit
    The CORRECT gate for approvals.
    • Checks if the document already has wa_approval_status = "Approved"
      (set by the webhook after the approver taps ✅) — if so, lets submission
      through immediately.
    • If not yet approved, sends the WhatsApp message (unless a Pending log
      already exists, to avoid duplicate sends), commits the log to the DB,
      then raises ValidationError to BLOCK the submission.
    • The document stays in Draft until the approver responds.
    • Webhook on Approve  → sets wa_approval_status = "Approved" then calls
      doc.submit() programmatically.
    • Webhook on Reject   → adds a comment, sets wa_approval_status = "Rejected".

on_save (stored as trigger_event on the rule)
    Frappe fires "on_update" after every doc save; we map that back to "on_save"
    so existing WA Approval Rules with trigger_event = "on_save" keep working.
    Does NOT block — just sends the WA message once (deduped by Pending log).

on_submit
    For Pattern 3: pure post-submit notification (not a real gate).
    The document is already submitted; the WA message is informational.
    No blocking, no auto-submit from webhook.

on_update_after_submit
    Same as on_save but for already-submitted documents.

on_cancel
    Marks any Pending approval logs as Expired.
"""
import frappe
from whatsapp_approvals.utils.approver import resolve_approver_phone
from whatsapp_approvals.utils.whatsapp import send_approval_message


_SKIP_DOCTYPES = {
    "WA Approval Rule",
    "WA Approval Rule Field",
    "WhatsApp Approval Log",
    "WhatsApp Approval Settings",
}

# Maps Frappe's internal event name (what hooks.py registers) →
# the trigger_event value stored on WA Approval Rule records.
#
# KEY POINT: Frappe calls "on_update" after every save, never "on_save".
# We map "on_update" → looks up rules with trigger_event = "on_save"
# so existing rules created with "on_save" continue to work unchanged.
_EVENT_MAP = {
    "before_submit":          "before_submit",
    "on_update":              "on_save",        # Frappe save → our "on_save" rules
    "on_submit":              "on_submit",
    "on_update_after_submit": "on_update_after_submit",
}


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def dispatch(doc, method=None):
    if doc.doctype in _SKIP_DOCTYPES:
        return

    trigger = _EVENT_MAP.get(method)
    if not trigger:
        return

    # ── Special handling for before_submit ───────────────────────────────────
    if trigger == "before_submit":
        _handle_before_submit(doc)
        return

    # ── on_save / on_submit / on_update_after_submit — non-blocking ──────────
    rules = _get_rules(doc.doctype, trigger)
    if not rules:
        return

    for rule in rules:
        try:
            # ── Dedup: don't re-send if a Pending log already exists ──────────
            # Prevents spamming the approver on every save.
            already_pending = frappe.db.exists(
                "WhatsApp Approval Log",
                {
                    "reference_doctype": doc.doctype,
                    "reference_name":    doc.name,
                    "status":            "Pending",
                },
            )
            if already_pending:
                continue

            _fire_rule(doc, rule, blocking=False)

        except Exception:
            frappe.log_error(frappe.get_traceback())


def on_cancel(doc, method=None):
    """Expire pending logs when a document is cancelled."""
    if doc.doctype in _SKIP_DOCTYPES:
        return

    pending = frappe.get_all(
        "WhatsApp Approval Log",
        filters={
            "reference_doctype": doc.doctype,
            "reference_name":    doc.name,
            "status":            "Pending",
        },
        pluck="name",
    )
    for log_name in pending:
        frappe.db.set_value(
            "WhatsApp Approval Log", log_name,
            {"status": "Expired", "notes": f"{doc.doctype} {doc.name} was cancelled."},
            update_modified=True,
        )
    if pending:
        frappe.db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# before_submit — the approval gate
# ─────────────────────────────────────────────────────────────────────────────

def _handle_before_submit(doc):
    rules = _get_rules(doc.doctype, "before_submit")
    if not rules:
        return

    if doc.get("wa_approval_status") == "Approved":
        return

    applicable_rules = [r for r in rules if _condition_passes(doc, r)]
    if not applicable_rules:
        return

    existing_pending = frappe.db.exists(
        "WhatsApp Approval Log",
        {
            "reference_doctype": doc.doctype,
            "reference_name":    doc.name,
            "status":            "Pending",
        },
    )

    if not existing_pending:
        for rule in applicable_rules:
            try:
                _fire_rule(doc, rule, blocking=True)
            except Exception:
                frappe.log_error(frappe.get_traceback())

        # Commit BEFORE throw — frappe.throw() rolls back the transaction.
        # Without this commit the log insert would be lost.
        frappe.db.commit()

    msg = (
        f"A WhatsApp approval request is already pending for "
        f"<b>{doc.doctype} {doc.name}</b>. "
        "The document will be submitted automatically once the approver responds."
        if existing_pending else
        f"WhatsApp approval request sent for <b>{doc.doctype} {doc.name}</b>. "
        "The document will be submitted automatically once the approver taps ✅ Approve."
    )

    frappe.throw(msg, title="Pending WhatsApp Approval", exc=frappe.ValidationError)


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_rules(doctype, trigger):
    return frappe.get_all(
        "WA Approval Rule",
        filters={
            "document_type": doctype,
            "trigger_event": trigger,
            "is_active":     1,
        },
        fields=[
            "name", "condition",
            "approver_source", "approver_phone",
            "approver_phone_field", "approver_role",
        ],
    )


def _condition_passes(doc, rule):
    condition = rule.get("condition") if isinstance(rule, dict) else getattr(rule, "condition", "")
    if not condition or not condition.strip():
        return True
    try:
        return bool(frappe.safe_eval(
            condition,
            eval_globals={"doc": doc, "frappe": frappe},
        ))
    except Exception as exc:
        rule_name = rule.get("name") if isinstance(rule, dict) else rule.name
        frappe.log_error(f"WA Approval condition error in rule {rule_name}: {exc}")
        return False


def _fire_rule(doc, rule, blocking=False):
    """Evaluate condition (if not already done), resolve phone, send message."""
    if not blocking:
        if not _condition_passes(doc, rule):
            return

    phone = resolve_approver_phone(rule, doc)
    if not phone:
        rule_name = rule.get("name") if isinstance(rule, dict) else rule.name
        frappe.log_error(
            f"WA Approval: phone not resolved. Rule: {rule_name} | Doc: {doc.doctype} {doc.name}",
        )
        return

    rule_name = rule.get("name") if isinstance(rule, dict) else rule.name
    rule_doc  = frappe.get_doc("WA Approval Rule", rule_name)
    send_approval_message(doc, rule_doc, phone)