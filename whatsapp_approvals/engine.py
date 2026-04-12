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

on_save
    For the Frappe Workflow pattern.
    Fires when a document is saved. Typically used with a condition such as
    doc.workflow_state == "Pending Approval".
    Does NOT block — just sends the WA message.

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

_EVENT_MAP = {
    "before_submit":          "before_submit",
    "on_save":                "on_save",
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
            _fire_rule(doc, rule, blocking=False)
        except Exception:
            frappe.log_error(
                title=f"WA Approval: rule {rule.name} failed on {doc.doctype} {doc.name}",
                message=frappe.get_traceback(),
            )


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
        return  # No rule for this DocType → submit normally

    # ── Gate already cleared by the webhook ──────────────────────────────────
    if doc.get("wa_approval_status") == "Approved":
        return  # Webhook already approved → let submission through

    # ── Evaluate conditions — if ALL rules fail their condition, don't block ─
    applicable_rules = []
    for rule in rules:
        if _condition_passes(doc, rule):
            applicable_rules.append(rule)

    if not applicable_rules:
        return  # No rule's condition is met → submit normally

    # ── Check if a pending log already exists (avoid duplicate WA sends) ─────
    existing_pending = frappe.db.exists(
        "WhatsApp Approval Log",
        {
            "reference_doctype": doc.doctype,
            "reference_name":    doc.name,
            "status":            "Pending",
        },
    )

    if not existing_pending:
        # Send WA message for each applicable rule
        for rule in applicable_rules:
            try:
                _fire_rule(doc, rule, blocking=True)
            except Exception:
                frappe.log_error(
                    title=f"WA Approval: send failed for {doc.doctype} {doc.name}",
                    message=frappe.get_traceback(),
                )

        # ── CRITICAL: commit the log BEFORE throwing ─────────────────────────
        # frappe.throw() triggers a DB rollback.  We commit here so the log
        # row persists in the DB — otherwise the webhook has nothing to look up.
        frappe.db.commit()

    # ── Block the submission ──────────────────────────────────────────────────
    if existing_pending:
        msg = (
            f"A WhatsApp approval request is already pending for "
            f"<b>{doc.doctype} {doc.name}</b>. "
            "The document will be submitted automatically once the approver responds."
        )
    else:
        msg = (
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
    condition = rule.get("condition") or (rule.condition if hasattr(rule, "condition") else "")
    if not condition or not condition.strip():
        return True
    try:
        return bool(frappe.safe_eval(
            condition,
            eval_globals={"doc": doc, "frappe": frappe},
        ))
    except Exception as exc:
        frappe.log_error(
            title=f"WA Approval: condition error in rule {rule.get('name') or rule.name}",
            message=str(exc),
        )
        return False


def _fire_rule(doc, rule, blocking=False):
    """Evaluate condition (if not already done), resolve phone, send message."""
    if not blocking:
        # For non-before_submit triggers we still evaluate condition here
        if not _condition_passes(doc, rule):
            return

    phone = resolve_approver_phone(rule, doc)
    if not phone:
        frappe.log_error(
            title="WA Approval: approver phone not resolved",
            message=f"Rule: {rule.get('name') or rule.name} | Doc: {doc.doctype} {doc.name}",
        )
        return

    rule_doc = frappe.get_doc("WA Approval Rule", rule.get("name") or rule.name)
    send_approval_message(doc, rule_doc, phone)
