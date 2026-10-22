"""
alert_engine.py — turns raw inspection/complaint data into alerts, and
handles the 7-day auto-escalation rule.

Escalation rule: any alert unresolved 7 days after creation (or after its
last escalation) automatically moves up one severity level, which is also
a handoff up the authority chain: Mess Head -> Principal -> FSSAI.
"""

import json
import database as db
import fssai_rules as rules
import email_service


def _notify(mess_id, level, reason, fssai_reference=""):
    """Looks up the real contact for this college+level and emails them.
    Never raises — a failed/unconfigured email should never break the
    alert itself from being recorded."""
    try:
        mess = db.get_mess_hall(mess_id)
        if not mess:
            return
        contact_email = db.get_contact_email_for_level(mess["college_id"], level)
        email_service.send_alert_email(contact_email, mess["name"], level, reason, fssai_reference)
    except Exception as e:
        print(f"[alert_engine] Notification failed (alert still recorded): {e}")


def create_inspection_alert(mess_id, inspector_name, responses: dict):
    level, score, reason = rules.compute_inspection_severity(responses)
    inspection_id = db.insert_inspection(mess_id, inspector_name, json.dumps(responses), score)
    fssai_ref = "FSSAI Schedule 4 — Sanitary & Hygiene Requirements"
    alert_id = db.insert_alert(
        mess_id=mess_id,
        source="inspection",
        source_id=inspection_id,
        level=level,
        reason=reason,
        fssai_reference=fssai_ref,
    )
    _notify(mess_id, level, reason, fssai_ref)
    return alert_id, level, score, reason


CATEGORY_THRESHOLD = 20  # complaints in the same category, same mess, all-time
MESS_THRESHOLD = 45      # complaints of any category, same mess, all-time


def create_complaint_alert(college_id, mess_id, student_email, student_name, category, description, photo_path=None):
    """Validates the student's email domain matches the selected college
    before accepting the complaint. Returns None, None, "unauthorized", None, None if not.

    Every valid complaint is always stored (kept as proof/evidence), but an
    alert is only raised once a pattern is confirmed — either 20+ complaints
    in the same category at this mess, or 45+ complaints of any category at
    this mess (both all-time counts). This avoids a single complaint (which
    could be mistaken, exaggerated, or malicious) triggering escalation on
    its own. Once a given pattern has triggered an alert, it won't trigger
    a duplicate alert on every complaint after that.

    Returns: (alert_id or None, level or None, reason, category_count, mess_count)
    """
    if not db.is_authorized_email(college_id, student_email):
        return None, None, "unauthorized", None, None

    complaint_id = db.insert_complaint(
        college_id, mess_id, student_email, student_name, category, description, photo_path
    )

    category_count = db.count_complaints(mess_id, category=category)
    mess_count = db.count_complaints(mess_id)

    pattern_key_category = f"mess{mess_id}_category_{category}"
    pattern_key_mess = f"mess{mess_id}_all_categories"

    alert_id = None
    level = None
    reason = f"Complaint recorded ({category_count} of {CATEGORY_THRESHOLD} needed for '{category}' at this mess)."

    if category_count >= CATEGORY_THRESHOLD and not db.pattern_alert_exists(pattern_key_category):
        base_level = rules.COMPLAINT_CATEGORIES.get(category, "Low")
        idx = min(rules.LEVELS.index(base_level) + 1, len(rules.LEVELS) - 1)
        level = rules.LEVELS[idx]
        reason = (
            f"Pattern confirmed: {category_count} complaints for '{category}' "
            f"at this mess hall (all-time) — treated as a verified issue."
        )
        alert_id = db.insert_alert(
            mess_id=mess_id,
            source="complaint_pattern",
            source_id=complaint_id,
            level=level,
            reason=reason,
            fssai_reference="FSSAI consumer complaint escalation guidance",
            pattern_key=pattern_key_category,
        )
        _notify(mess_id, level, reason, "FSSAI consumer complaint escalation guidance")
    elif mess_count >= MESS_THRESHOLD and not db.pattern_alert_exists(pattern_key_mess):
        level = "High"
        reason = (
            f"Pattern confirmed: {mess_count} total complaints (all categories) "
            f"at this mess hall (all-time) — broad issue, treated as verified."
        )
        alert_id = db.insert_alert(
            mess_id=mess_id,
            source="complaint_pattern",
            source_id=complaint_id,
            level=level,
            reason=reason,
            fssai_reference="FSSAI consumer complaint escalation guidance",
            pattern_key=pattern_key_mess,
        )
        _notify(mess_id, level, reason, "FSSAI consumer complaint escalation guidance")

    return alert_id, level, reason, category_count, mess_count


def escalate_stale_alerts(days=7):
    """Call this periodically — cheap query, and guarantees no alert
    silently sits unresolved past the 1-week window."""
    stale = db.get_unresolved_stale_alerts(days=days)
    escalated_count = 0
    for alert in stale:
        idx = rules.LEVELS.index(alert["level"])
        if idx < len(rules.LEVELS) - 1:
            new_level = rules.LEVELS[idx + 1]
            db.escalate_alert(alert["id"], new_level)
            escalated_count += 1
            escalation_reason = (
                f"Auto-escalated: unresolved for {days}+ days. Original reason: {alert['reason']}"
            )
            _notify(alert["mess_id"], new_level, escalation_reason, alert.get("fssai_reference", ""))
    return escalated_count
