"""
whatsapp_approvals.api.manual
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Whitelisted API methods called from the client-side JS.
"""
import frappe
from frappe import _
from whatsapp_approvals.utils.approver import resolve_approver_phone
from whatsapp_approvals.utils.whatsapp import send_approval_message


@frappe.whitelist()
def send_approval(doctype, docname):
    """
    Manually (re-)send the WhatsApp approval request for any document.
    Called from the "Send WA Approval" / "Re-send WA Approval" form button.

    Works for all trigger patterns:
      before_submit  → document is in Draft, waiting for WA approval
      on_save        → document is saved in a workflow state
      on_submit      → document is already submitted (notification pattern)
    """
    if not frappe.has_permission(doctype, "write", docname):
        frappe.throw(_("Insufficient permissions."), frappe.PermissionError)

    doc = frappe.get_doc(doctype, docname)

    # Don't re-send if already approved
    if doc.get("wa_approval_status") == "Approved":
        frappe.throw(_("This document has already been approved via WhatsApp."))

    # Find active rules for this doctype (any trigger event)
    rules = frappe.get_all(
        "WA Approval Rule",
        filters={"document_type": doctype, "is_active": 1},
        fields=["name", "approver_source", "approver_phone",
                "approver_phone_field", "approver_role"],
    )

    if not rules:
        frappe.throw(_(f"No active WA Approval Rule found for DocType: {doctype}"))

    sent_logs = []
    for rule in rules:
        phone = resolve_approver_phone(rule, doc)
        if not phone:
            continue
        rule_doc = frappe.get_doc("WA Approval Rule", rule.name)
        log_name = send_approval_message(doc, rule_doc, phone)
        sent_logs.append(log_name)

    if not sent_logs:
        frappe.throw(_("Could not resolve approver phone for any active rule."))

    frappe.db.commit()
    return {"logs": sent_logs}


@frappe.whitelist(allow_guest=False)
def get_active_rule_doctypes():
    """
    Returns list of DocTypes with at least one active WA Approval Rule.
    Called once by the client JS to know which forms to inject buttons into.
    """
    rows = frappe.get_all(
        "WA Approval Rule",
        filters={"is_active": 1},
        fields=["document_type"],
        distinct=True,
    )
    return list({r.document_type for r in rows})


@frappe.whitelist()
def get_pending_log(doctype, docname):
    """Returns name of most recent Pending log for a document, or None."""
    return frappe.db.get_value(
        "WhatsApp Approval Log",
        {
            "reference_doctype": doctype,
            "reference_name":    docname,
            "status":            "Pending",
        },
        "name",
        order_by="creation desc",
    )
