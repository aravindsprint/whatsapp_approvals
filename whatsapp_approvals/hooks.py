app_name = "whatsapp_approvals"
app_title = "WhatsApp Approvals"
app_publisher = "Aravind"
app_description = "Generic pre-submission WhatsApp approval for any ERPNext DocType"
app_email = "aravindsprint@gmail.com"
app_license = "mit"

# Document Events
# ---------------
# Wire the engine into every DocType using the "*" wildcard.
#
# IMPORTANT: Frappe's internal save event is called "on_update" NOT "on_save".
# Using "on_save" as a hook key is silently ignored by Frappe — the handler
# never fires. Always use "on_update" for post-save triggers.

doc_events = {
    "*": {
        "on_update":              "whatsapp_approvals.engine.dispatch",
        "before_submit":          "whatsapp_approvals.engine.dispatch",
        "on_submit":              "whatsapp_approvals.engine.dispatch",
        "on_update_after_submit": "whatsapp_approvals.engine.dispatch",
        "on_cancel":              "whatsapp_approvals.engine.on_cancel",
    }
}

# Website Route Rules
# -------------------
# Expose the webhook at a clean URL:
#   GET  /api/wa-webhook  → Meta verification challenge
#   POST /api/wa-webhook  → button reply payloads
#
# Configure in Meta Developer Console → WhatsApp → Configuration → Webhook URL:
#   https://erp.pranera.in/api/wa-webhook

website_route_rules = [
    {
        "from_route": "/api/wa-webhook",
        "to_route":   "whatsapp_approvals.api.webhook.handle",
    },
]

# Scheduled Tasks
# ---------------

# scheduler_events = {
#   "all": [
#       "whatsapp_approvals.tasks.all"
#   ],
#   "daily": [
#       "whatsapp_approvals.tasks.daily"
#   ],
#   "hourly": [
#       "whatsapp_approvals.tasks.hourly"
#   ],
#   "weekly": [
#       "whatsapp_approvals.tasks.weekly"
#   ],
#   "monthly": [
#       "whatsapp_approvals.tasks.monthly"
#   ],
# }