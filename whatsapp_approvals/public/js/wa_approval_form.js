/**
 * whatsapp_approval — Generic form script  (v3)
 *
 * Loaded on every Frappe page via app_include_js.
 * Fetches active-rule DocTypes once per session, then registers a refresh
 * handler on each of them that injects:
 *
 *   • WA status badge in the dashboard  (Pending / Approved / Rejected)
 *   • "Send for WA Approval"  — sends the WA message; document stays Draft
 *   • "Re-send WA Approval"   — re-sends if a pending log already exists
 *   • "View Approval Log"     — navigates to filtered log list
 *
 * For before_submit rules the "Submit" button is effectively replaced by
 * "Send for WA Approval".  The document submits automatically when the
 * approver taps ✅ Approve in WhatsApp.
 */

(function () {
    "use strict";

    let _ruleDocTypes = null;
    let _fetchPromise  = null;

    function getRuleDocTypes() {
        if (_ruleDocTypes !== null) return Promise.resolve(_ruleDocTypes);
        if (_fetchPromise)          return _fetchPromise;

        _fetchPromise = frappe.call({
            method: "whatsapp_approvals.api.manual.get_active_rule_doctypes",
            freeze: false,
        }).then(r => {
            _ruleDocTypes = new Set(r.message || []);
            _fetchPromise = null;
            return _ruleDocTypes;
        }).catch(() => {
            _ruleDocTypes = new Set();
            _fetchPromise = null;
            return _ruleDocTypes;
        });

        return _fetchPromise;
    }

    // Register handlers once the doctype list is known
    frappe.after_ajax(function () {
        getRuleDocTypes().then(function (doctypes) {
            doctypes.forEach(function (dt) {
                frappe.ui.form.on(dt, {
                    refresh: function (frm) { injectButtons(frm); }
                });
            });
        });
    });

    function injectButtons(frm) {
        if (frm.is_new()) return;

        const status   = frm.doc.wa_approval_status;
        const docstatus = frm.doc.docstatus;

        // ── Status badge ─────────────────────────────────────────────────────
        if (status) {
            const color = status === "Approved" ? "green"
                        : status === "Rejected"  ? "red"
                        : "orange";
            frm.dashboard.add_indicator(__("WA: {0}", [status]), color);
        }

        // ── View Approval Log — always visible ───────────────────────────────
        frm.add_custom_button(
            __("View Approval Log"),
            function () {
                frappe.set_route("List", "WhatsApp Approval Log", {
                    reference_doctype: frm.doctype,
                    reference_name:    frm.docname,
                });
            },
            __("WhatsApp")
        );

        // ── No action buttons if already approved / rejected / submitted ──────
        if (status === "Approved" || status === "Rejected" || docstatus === 1) return;

        // ── Check for existing pending log to label the button correctly ──────
        frappe.call({
            method:  "whatsapp_approvals.api.manual.get_pending_log",
            args:    { doctype: frm.doctype, docname: frm.docname },
            freeze:  false,
            callback: function (r) {
                const hasPending = !!r.message;

                const btnLabel = hasPending
                    ? __("Re-send WA Approval")
                    : __("Send for WA Approval");

                const confirmMsg = hasPending
                    ? __("A pending approval already exists. Re-send the WhatsApp message to <b>{0}</b>?", [frm.docname])
                    : __("Send WhatsApp approval request for <b>{0}</b>?<br><br>"
                       + "<small>The document will be submitted <b>automatically</b> "
                       + "once the approver taps ✅ Approve.</small>", [frm.docname]);

                frm.add_custom_button(
                    btnLabel,
                    function () {
                        frappe.confirm(confirmMsg, function () {
                            frappe.call({
                                method:         "whatsapp_approvals.api.manual.send_approval",
                                args:           { doctype: frm.doctype, docname: frm.docname },
                                freeze:         true,
                                freeze_message: __("Sending WhatsApp approval request…"),
                                callback: function (res) {
                                    if (!res.exc) {
                                        frappe.show_alert({
                                            message: __(
                                                "Approval request sent via WhatsApp ✅<br>"
                                                + "<small>Document will submit automatically once approved.</small>"
                                            ),
                                            indicator: "green",
                                        }, 6);
                                        frm.reload_doc();
                                    }
                                },
                            });
                        });
                    },
                    __("WhatsApp")
                );
            },
        });
    }

})();
