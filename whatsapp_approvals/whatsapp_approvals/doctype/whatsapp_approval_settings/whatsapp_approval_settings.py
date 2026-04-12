import frappe
from frappe.model.document import Document


class WhatsAppApprovalSettings(Document):
    def validate(self):
        if self.approver_phone:
            c = self.approver_phone.replace("+","").replace("-","").replace(" ","")
            if not c.isdigit():
                frappe.throw("Fallback Approver Phone must be digits only.")
            self.approver_phone = c
