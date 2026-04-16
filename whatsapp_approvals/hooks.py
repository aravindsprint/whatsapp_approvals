app_name = "whatsapp_approvals"
app_title = "WhatsApp Approvals"
app_publisher = "Aravind"
app_description = "Generic pre-submission WhatsApp approval for any ERPNext DocType"
app_email = "aravindsprint@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "whatsapp_approvals",
# 		"logo": "/assets/whatsapp_approvals/logo.png",
# 		"title": "WhatsApp Approvals",
# 		"route": "/whatsapp_approvals",
# 		"has_permission": "whatsapp_approvals.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/whatsapp_approvals/css/whatsapp_approvals.css"
# app_include_js = "/assets/whatsapp_approvals/js/whatsapp_approvals.js"

# include js, css files in header of web template
# web_include_css = "/assets/whatsapp_approvals/css/whatsapp_approvals.css"
# web_include_js = "/assets/whatsapp_approvals/js/whatsapp_approvals.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "whatsapp_approvals/public/scss/website"

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "whatsapp_approvals/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "whatsapp_approvals.utils.jinja_methods",
# 	"filters": "whatsapp_approvals.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "whatsapp_approvals.install.before_install"
# after_install = "whatsapp_approvals.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "whatsapp_approvals.uninstall.before_uninstall"
# after_uninstall = "whatsapp_approvals.uninstall.after_uninstall"

# Integration Setup
# ------------------
# before_app_install = "whatsapp_approvals.utils.before_app_install"
# after_app_install = "whatsapp_approvals.utils.after_app_install"

# Integration Cleanup
# -------------------
# before_app_uninstall = "whatsapp_approvals.utils.before_app_uninstall"
# after_app_uninstall = "whatsapp_approvals.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# notification_config = "whatsapp_approvals.notifications.get_notification_config"

# Permissions
# -----------
# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Wire the engine into every DocType using the "*" wildcard.
# engine.dispatch() reads the WA Approval Rule for the DocType + event,
# checks the condition, resolves the approver phone, and sends the message.

doc_events = {
    "*": {
        "on_save":                "whatsapp_approvals.engine.dispatch",
        "before_submit":          "whatsapp_approvals.engine.dispatch",
        "on_submit":              "whatsapp_approvals.engine.dispatch",
        "on_update_after_submit": "whatsapp_approvals.engine.dispatch",
        "on_cancel":              "whatsapp_approvals.engine.on_cancel",
    }
}

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

# Testing
# -------

# before_tests = "whatsapp_approvals.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "whatsapp_approvals.event.get_events"
# }
#
# override_doctype_dashboards = {
# 	"Task": "whatsapp_approvals.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------
# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["whatsapp_approvals.utils.before_request"]
# after_request = ["whatsapp_approvals.utils.after_request"]

# Job Events
# ----------
# before_job = ["whatsapp_approvals.utils.before_job"]
# after_job = ["whatsapp_approvals.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"whatsapp_approvals.auth.validate"
# ]

# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }