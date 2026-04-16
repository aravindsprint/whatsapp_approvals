app_name = "whatsapp_approvals"
app_title = "WhatsApp Approvals"
app_publisher = "Aravind"
app_description = "Generic pre-submission WhatsApp approval for any ERPNext DocType"
app_email = "aravindsprint@gmail.com"
app_license = "mit"

# Document Events
# ---------------
# Wire the engine into every DocType using the "*" wildcard.

doc_events = {
    "*": {
        "on_save":                "whatsapp_approvals.engine.dispatch",
        "before_submit":          "whatsapp_approvals.engine.dispatch",
        "on_submit":              "whatsapp_approvals.engine.dispatch",
        "on_update_after_submit": "whatsapp_approvals.engine.dispatch",
        "on_cancel":              "whatsapp_approvals.engine.on_cancel",
    }
}

# Website Route Rules
# -------------------
# Expose the webhook at a clean URL so Meta can reach it via both GET and POST.
# Meta sends:
#   GET  /api/wa-webhook?hub.mode=subscribe&hub.challenge=...&hub.verify_token=...
#   POST /api/wa-webhook  (button reply payloads)
#
# Configure this URL in Meta Developer Console → WhatsApp → Configuration → Webhook URL:
#   https://pranera.erpnext.com/api/wa-webhook

website_route_rules = [
    {
        "from_route": "/api/wa-webhook",
        "to_route":   "whatsapp_approvals.api.webhook.handle",
    },
]

# Override Whitelisted Methods
# ----------------------------
# Also keep the standard API path working as fallback:
#   https://pranera.erpnext.com/api/method/whatsapp_approvals.api.webhook.handle

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"whatsapp_approvals.tasks.all"
# 	],
# 	"daily": [
# 		"whatsapp_approvals.tasks.daily"
# 	],
# 	"hourly": [
# 		"whatsapp_approvals.tasks.hourly"
# 	],
# 	"weekly": [
# 		"whatsapp_approvals.tasks.weekly"
# 	],
# 	"monthly": [
# 		"whatsapp_approvals.tasks.monthly"
# 	],
# }