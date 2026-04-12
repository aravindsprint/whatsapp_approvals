"""
whatsapp_approvals.utils.approver
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Resolves the approver's WhatsApp phone number from a WA Approval Rule.

Three strategies
----------------
Fixed Number       → phone stored directly on the rule
Field on Document  → a fieldname on the document that holds the phone
Role               → finds the first active ERPNext User with that Role
                     and reads their mobile_no
"""
import frappe


def resolve_approver_phone(rule, doc):
    source = _get(rule, "approver_source")

    if source == "Fixed Number":
        return _clean(_get(rule, "approver_phone"))

    if source == "Field on Document":
        field = _get(rule, "approver_phone_field")
        if field:
            return _clean(doc.get(field))

    if source == "Role":
        role = _get(rule, "approver_role")
        if role:
            return _phone_from_role(role)

    return None


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _clean(phone):
    if not phone:
        return None
    cleaned = str(phone).replace("+","").replace(" ","").replace("-","").strip()
    return cleaned if (cleaned.isdigit() and len(cleaned) >= 7) else None


def _phone_from_role(role):
    users = frappe.get_all(
        "Has Role",
        filters={"role": role, "parenttype": "User"},
        pluck="parent",
    )
    for user in users:
        if not frappe.db.get_value("User", user, "enabled"):
            continue
        mobile = frappe.db.get_value("User", user, "mobile_no")
        cleaned = _clean(mobile)
        if cleaned:
            return cleaned
    return None
