import frappe
from frappe.model.document import Document
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

_CUSTOM_FIELDS = [
    {"fieldname":"wa_approval_section","fieldtype":"Section Break",
     "label":"WhatsApp Approvals","insert_after":"amended_from","collapsible":1},
    {"fieldname":"wa_approval_status","fieldtype":"Select",
     "label":"WA Approval Status","options":"\nPending\nApproved\nRejected",
     "insert_after":"wa_approval_section","read_only":1,"in_list_view":1,"bold":1},
    {"fieldname":"wa_approval_message_id","fieldtype":"Data",
     "label":"WA Message ID","insert_after":"wa_approval_status","read_only":1,"hidden":1},
    {"fieldname":"wa_approval_responded_by","fieldtype":"Data",
     "label":"WA Responded By","insert_after":"wa_approval_message_id","read_only":1},
    {"fieldname":"wa_approval_responded_at","fieldtype":"Datetime",
     "label":"WA Responded At","insert_after":"wa_approval_responded_by","read_only":1},
]

_PROTECTED = {
    "WA Approval Rule","WA Approval Rule Field",
    "WhatsApp Approval Log","WhatsApp Approval Settings",
    "DocType","DocField","Custom Field","User","Role",
}


class WaApprovalRule(Document):
    def validate(self):
        if self.approver_phone:
            cleaned = (self.approver_phone
                       .replace("+","").replace("-","").replace(" ",""))
            if not cleaned.isdigit():
                frappe.throw("Approver Phone must be digits only (include country code, no +).")
            self.approver_phone = cleaned
        if not self.message_title:
            self.message_title = f"{self.document_type} Approval Request"

    def after_save(self):
        if self.document_type and self.document_type not in _PROTECTED:
            _ensure_custom_fields(self.document_type)


def _ensure_custom_fields(doctype):
    try:
        meta = frappe.get_meta(doctype)
        print("\nmeta\n",meta)
        existing = {f.fieldname for f in meta.fields}
        to_add = [f for f in _CUSTOM_FIELDS if f["fieldname"] not in existing]
        if not to_add:
            return
        create_custom_fields({doctype: to_add}, ignore_validate=True)
        frappe.clear_cache(doctype=doctype)
        frappe.msgprint(
            f"WhatsApp Approval tracking fields added to <b>{doctype}</b>.",
            indicator="green", alert=True,
        )
    except Exception:
        frappe.log_error(
            title=f"WA Approval: failed to add custom fields to {doctype}",
            message=frappe.get_traceback(),
        )
