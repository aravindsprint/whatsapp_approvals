"""
whatsapp_approvals.tasks
~~~~~~~~~~~~~~~~~~~~~~~~
Hourly scheduled task — re-sends pending approval reminders.
"""
import frappe
from frappe.utils import now_datetime, time_diff_in_hours
from whatsapp_approvals.utils.approver import resolve_approver_phone
from whatsapp_approvals.utils.whatsapp import send_approval_message


def send_pending_reminders():
    settings = frappe.get_single("WhatsApp Approval Settings")
    reminder_hours = settings.reminder_hours or 0
    max_reminders  = settings.max_reminders  or 0

    if reminder_hours <= 0 or max_reminders <= 0:
        return

    pending_logs = frappe.get_all(
        "WhatsApp Approval Log",
        filters={"status": "Pending"},
        fields=["name", "reference_doctype", "reference_name",
                "rule_name", "sent_at", "reminder_count"],
    )

    for log in pending_logs:
        if (log.reminder_count or 0) >= max_reminders:
            continue

        if time_diff_in_hours(now_datetime(), log.sent_at) < reminder_hours:
            continue

        if not frappe.db.exists(log.reference_doctype, log.reference_name):
            _expire(log.name, "Document no longer exists.")
            continue

        # For before_submit rules: if doc is already submitted, expire the log
        docstatus = frappe.db.get_value(log.reference_doctype, log.reference_name, "docstatus")
        if docstatus == 1:
            _expire(log.name, "Document already submitted.")
            continue
        if docstatus == 2:
            _expire(log.name, "Document was cancelled.")
            continue

        # Check custom field status
        meta = frappe.get_meta(log.reference_doctype)
        if meta.has_field("wa_approval_status"):
            current = frappe.db.get_value(
                log.reference_doctype, log.reference_name, "wa_approval_status"
            )
            if current and current != "Pending":
                _expire(log.name, f"Status changed to {current}.")
                continue

        if not (log.rule_name and frappe.db.exists("WA Approval Rule", log.rule_name)):
            _expire(log.name, "Rule no longer exists.")
            continue

        rule = frappe.db.get_value(
            "WA Approval Rule", log.rule_name,
            ["is_active", "approver_source", "approver_phone",
             "approver_phone_field", "approver_role"],
            as_dict=True,
        )
        if not rule or not rule.is_active:
            _expire(log.name, "Rule is inactive.")
            continue

        try:
            doc      = frappe.get_doc(log.reference_doctype, log.reference_name)
            phone    = resolve_approver_phone(rule, doc)
            if not phone:
                continue
            rule_doc = frappe.get_doc("WA Approval Rule", log.rule_name)
            send_approval_message(doc, rule_doc, phone)

            frappe.db.set_value(
                "WhatsApp Approval Log", log.name,
                {"reminder_count": (log.reminder_count or 0) + 1, "sent_at": now_datetime()},
            )
        except Exception:
            frappe.log_error(
                title=f"WA Reminder failed: {log.reference_doctype} {log.reference_name}",
                message=frappe.get_traceback(),
            )

    frappe.db.commit()


def _expire(log_name, reason):
    frappe.db.set_value(
        "WhatsApp Approval Log", log_name,
        {"status": "Expired", "notes": reason},
        update_modified=True,
    )
