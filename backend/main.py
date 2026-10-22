"""
main.py — TrayTrack API (FastAPI)

Covers every screen that used to live in the Streamlit app:
  - Google Sign-In                (student identity)
  - Submit Complaint (+ photo)    (public-facing, requires sign-in)
  - My Reports                   (student's own history + resolve button)
  - Public Dashboard              (open, no auth)
  - History / Trends             (open, no auth)
  - Inspector Entry               (password-protected)
  - Admin Panel                   (password-protected)
"""

import os
import uuid
import threading
import time
import csv
import io
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Header, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from dotenv import load_dotenv

load_dotenv()

import database as db
import alert_engine
import fssai_rules as rules
import auth

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173")

UPLOAD_DIR = Path(__file__).parent / "uploads" / "complaints"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="TrayTrack API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR.parent)), name="uploads")

db.init_db()


def _escalation_loop():
    """Runs the 7-day auto-escalation check every hour in the background,
    so alerts don't sit stale just because nobody happens to load a page."""
    while True:
        try:
            count = alert_engine.escalate_stale_alerts(days=7)
            if count:
                print(f"[escalation] Auto-escalated {count} stale alert(s).")
        except Exception as e:
            print(f"[escalation] Check failed: {e}")
        time.sleep(60 * 60)  # 1 hour


threading.Thread(target=_escalation_loop, daemon=True).start()


def require_admin(authorization: Optional[str] = Header(None)):
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[len("Bearer "):]
    if not token or not auth.verify_admin_token(token):
        raise HTTPException(status_code=401, detail="Session expired or invalid — please log in again.")
    return True


def require_user(authorization: Optional[str] = Header(None)):
    token = authorization[len("Bearer "):] if authorization and authorization.startswith("Bearer ") else None
    email = auth.verify_user_token(token) if token else None
    if not email:
        raise HTTPException(status_code=401, detail="Not signed in")
    return email


# ==================== AUTH ====================

class GoogleLoginRequest(BaseModel):
    credential: str


@app.post("/auth/google")
def google_login(payload: GoogleLoginRequest):
    try:
        info = id_token.verify_oauth2_token(
            payload.credential, google_requests.Request(), GOOGLE_CLIENT_ID
        )
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Google token")

    if not info.get("email_verified"):
        raise HTTPException(status_code=401, detail="Email not verified by Google")

    return {
        "email": info["email"],
        "name": info.get("name", ""),
        "hd": info.get("hd", ""),
        "token": auth.create_user_token(info["email"]),
    }


class AdminLoginRequest(BaseModel):
    password: str


@app.post("/admin/login")
def admin_login(payload: AdminLoginRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"

    locked_seconds = auth.check_lockout(client_ip)
    if locked_seconds is not None:
        hours = locked_seconds // 3600
        minutes = (locked_seconds % 3600) // 60
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed attempts. Try again in {hours}h {minutes}m.",
        )

    if not auth.check_admin_password(payload.password):
        auth.record_failed_attempt(client_ip)
        remaining = auth.MAX_ATTEMPTS - auth._attempts.get(client_ip, {}).get("count", 0)
        if remaining > 0:
            raise HTTPException(status_code=401, detail=f"Incorrect password. {remaining} attempt(s) left.")
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 6 hours.")

    auth.reset_attempts(client_ip)
    return {"token": auth.create_admin_token()}


# ==================== COLLEGES / MESS HALLS (public reference data) ====================

@app.get("/colleges")
def list_colleges():
    return db.list_colleges()


@app.get("/admin/college-directory")
def admin_college_directory(
    state: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    authorization: str = Header(None),
):
    require_admin(authorization)
    return db.list_college_directory(state=state, search=search, limit=limit)


@app.get("/admin/college-directory/states")
def admin_college_directory_states(authorization: str = Header(None)):
    require_admin(authorization)
    return db.list_directory_states()


@app.get("/mess-halls")
def list_mess_halls(college_id: int):
    return db.list_mess_halls(college_id)


@app.get("/categories")
def list_categories():
    return list(rules.COMPLAINT_CATEGORIES.keys())


@app.get("/checklist")
def list_checklist():
    return rules.CHECKLIST


# ==================== COMPLAINTS ====================

MAX_PHOTO_SIZE_BYTES = 4 * 1024 * 1024  # 4 MB
ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}


@app.post("/complaints")
async def submit_complaint(
    college_id: int = Form(...),
    mess_id: int = Form(...),
    student_name: str = Form(...),
    category: str = Form(...),
    description: str = Form(""),
    photo: Optional[UploadFile] = File(None),
    authorization: Optional[str] = Header(None),
):
    x_user_email = require_user(authorization)

    photo_path = None
    if photo is not None:
        if photo.content_type not in ALLOWED_PHOTO_TYPES:
            raise HTTPException(status_code=400, detail="Photo must be a JPEG, PNG, or WEBP image.")

        contents = await photo.read()
        if len(contents) > MAX_PHOTO_SIZE_BYTES:
            raise HTTPException(status_code=400, detail="Photo must be 4MB or smaller.")

        ext = Path(photo.filename or "").suffix or ".jpg"
        filename = f"{uuid.uuid4().hex}{ext}"
        dest = UPLOAD_DIR / filename
        with open(dest, "wb") as f:
            f.write(contents)
        photo_path = str(dest)

    alert_id, level, reason, category_count, mess_count = alert_engine.create_complaint_alert(
        college_id, mess_id, x_user_email, student_name, category, description, photo_path
    )

    if reason == "unauthorized":
        raise HTTPException(status_code=403, detail="Your email doesn't match this college's registered domain.")
    if reason == "invalid_mess":
        raise HTTPException(status_code=400, detail="That mess hall does not belong to the selected college.")

    return {
        "alert_created": alert_id is not None,
        "level": level,
        "reason": reason,
        "category_count": category_count,
        "mess_count": mess_count,
        "category_threshold": alert_engine.CATEGORY_THRESHOLD,
        "mess_threshold": alert_engine.MESS_THRESHOLD,
    }


# ==================== MY REPORTS ====================

@app.get("/my-complaints")
def my_complaints(authorization: Optional[str] = Header(None)):
    x_user_email = require_user(authorization)
    complaints = db.get_my_complaints(x_user_email)
    result = []
    for c in complaints:
        alert = db.get_alert_for_complaint(c["id"])
        result.append({**c, "alert": alert})
    return result


class ResolveByStudentRequest(BaseModel):
    alert_id: int


@app.post("/my-complaints/resolve")
def resolve_my_alert(payload: ResolveByStudentRequest, authorization: Optional[str] = Header(None)):
    x_user_email = require_user(authorization)

    alerts = db.get_alerts()
    alert = next((a for a in alerts if a["id"] == payload.alert_id), None)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert["resolved"]:
        raise HTTPException(status_code=400, detail="Already resolved")

    last_escalated = alert["last_escalated_at"]
    if isinstance(last_escalated, str):
        last_escalated = datetime.strptime(last_escalated, "%Y-%m-%d %H:%M:%S")
    if datetime.utcnow() - last_escalated < timedelta(days=2):
        raise HTTPException(status_code=400, detail="Too early — must be escalating for 2+ days first")

    if not db.mark_alert_resolved_by_student(payload.alert_id, x_user_email):
        raise HTTPException(status_code=403, detail="You may only resolve alerts linked to your own complaint.")
    return {"ok": True}


# ==================== PUBLIC DASHBOARD ====================

@app.get("/dashboard-status")
def dashboard_status(college_id: int):
    mess_halls = db.list_mess_halls(college_id)
    result = []
    for mess in mess_halls:
        open_alerts = db.get_alerts(mess_id=mess["id"], resolved=False)
        if not open_alerts:
            result.append({"mess": mess, "status": "clear", "open_count": 0, "worst_level": None})
        else:
            worst = max(open_alerts, key=lambda a: rules.LEVELS.index(a["level"]))
            result.append({
                "mess": mess,
                "status": "alert",
                "open_count": len(open_alerts),
                "worst_level": worst["level"],
                "authority": rules.get_authority(worst["level"]),
            })
    return result


@app.get("/alerts")
def open_alerts(college_id: Optional[int] = None, mess_id: Optional[int] = None):
    return db.get_alerts(college_id=college_id, mess_id=mess_id, resolved=False)


@app.get("/analytics")
def analytics(college_id: int):
    """Auto-updating chart data + the raw complaint descriptions behind
    each period, so the dashboard always reflects live data with no
    manual curation needed."""
    now = datetime.utcnow()
    week_start = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    month_start = (now - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")

    weekly_complaints = db.get_complaints_since(college_id, week_start)
    monthly_complaints = db.get_complaints_since(college_id, month_start)

    def category_counts(complaints):
        counts = {}
        for c in complaints:
            counts[c["category"]] = counts.get(c["category"], 0) + 1
        return [{"category": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: -x[1])]

    def strip_email(complaints):
        return [
            {
                "id": c["id"],
                "mess_name": c["mess_name"],
                "category": c["category"],
                "description": c["description"],
                "created_at": str(c["created_at"]),
            }
            for c in complaints
        ]

    return {
        "weekly_chart": category_counts(weekly_complaints),
        "weekly_complaints": strip_email(weekly_complaints),
        "monthly_chart": category_counts(monthly_complaints),
        "monthly_complaints": strip_email(monthly_complaints),
    }


# ==================== HISTORY / TRENDS ====================

@app.get("/trends")
def trends(college_id: Optional[int] = None, start_date: Optional[str] = None, end_date: Optional[str] = None):
    return db.get_alerts_with_details(college_id=college_id, start_date=start_date, end_date=end_date)


# ==================== INSPECTOR ====================

class InspectionRequest(BaseModel):
    mess_id: int
    inspector_name: str
    responses: dict  # {checklist_item_id: bool}


@app.post("/inspections")
def submit_inspection(payload: InspectionRequest, authorization: str = Header(None)):
    require_admin(authorization)
    alert_id, level, score, reason = alert_engine.create_inspection_alert(
        payload.mess_id, payload.inspector_name, payload.responses
    )
    return {"alert_id": alert_id, "level": level, "score": score, "reason": reason}


# ==================== ADMIN ====================

class AddCollegeRequest(BaseModel):
    name: str
    email_domain: str
    mess_head_email: Optional[str] = None
    principal_email: Optional[str] = None
    fssai_contact_email: Optional[str] = None


@app.post("/admin/colleges/import")
async def admin_import_colleges(file: UploadFile = File(...), authorization: str = Header(None)):
    require_admin(authorization)
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file.")

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        required = {"college_name", "email_domain"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError("CSV must contain college_name and email_domain columns")

        rows = []
        for line_number, row in enumerate(reader, start=2):
            rows.append({
                "name": row.get("college_name", ""),
                "email_domain": row.get("email_domain", ""),
                "mess_head_email": row.get("mess_head_email", "").strip(),
                "principal_email": row.get("principal_email", "").strip(),
                "fssai_contact_email": row.get("fssai_contact_email", "").strip(),
                "mess_hall_name": row.get("mess_hall_name", "").strip(),
            })
            if not rows[-1]["name"].strip() or not rows[-1]["email_domain"].strip():
                raise ValueError(f"Row {line_number}: college_name and email_domain are required")
        if not rows:
            raise ValueError("CSV contains no data rows")
        imported = db.bulk_import_colleges(rows)
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Import failed; no rows were saved. ({e})")
    return {"ok": True, "rows_imported": imported}


@app.post("/admin/colleges")
def admin_add_college(payload: AddCollegeRequest, authorization: str = Header(None)):
    require_admin(authorization)
    try:
        db.add_college(
            payload.name, payload.email_domain,
            payload.mess_head_email, payload.principal_email, payload.fssai_contact_email,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Couldn't add college — it may already exist. ({e})")
    return {"ok": True}


class UpdateContactsRequest(BaseModel):
    mess_head_email: Optional[str] = None
    principal_email: Optional[str] = None
    fssai_contact_email: Optional[str] = None


@app.patch("/admin/colleges/{college_id}/contacts")
def admin_update_college_contacts(college_id: int, payload: UpdateContactsRequest, authorization: str = Header(None)):
    require_admin(authorization)
    db.update_college_contacts(
        college_id, payload.mess_head_email, payload.principal_email, payload.fssai_contact_email
    )
    return {"ok": True}


class AddMessHallRequest(BaseModel):
    college_id: int
    name: str


@app.post("/admin/mess-halls")
def admin_add_mess_hall(payload: AddMessHallRequest, authorization: str = Header(None)):
    require_admin(authorization)
    try:
        db.add_mess_hall(payload.college_id, payload.name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Couldn't add mess hall — it may already exist. ({e})")
    return {"ok": True}


@app.delete("/admin/mess-halls/{mess_id}")
def admin_delete_mess_hall(mess_id: int, authorization: str = Header(None)):
    require_admin(authorization)
    try:
        db.delete_mess_hall(mess_id)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail="Couldn't delete — this mess hall still has complaints, inspections, or alerts linked to it.",
        )
    return {"ok": True}


@app.delete("/admin/colleges/{college_id}")
def admin_delete_college(college_id: int, authorization: str = Header(None)):
    require_admin(authorization)
    try:
        db.delete_college(college_id)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail="Couldn't delete — remove all of this college's mess halls first.",
        )
    return {"ok": True}


@app.get("/admin/alerts")
def admin_list_alerts(resolved: Optional[bool] = False, authorization: str = Header(None)):
    require_admin(authorization)
    alerts = db.get_alerts(resolved=resolved)
    result = []
    for a in alerts:
        detail = dict(a)
        if a["source"] in ("complaint", "complaint_pattern") and a["source_id"]:
            complaint = db.get_complaint_private(a["source_id"])
            if complaint:
                detail["complaint"] = {
                    "masked_email": auth.mask_email(complaint["student_email"]),
                    "category": complaint["category"],
                    "description": complaint["description"],
                    "photo_url": (f"/uploads/complaints/{Path(complaint['photo_path']).name}"
                                  if complaint.get("photo_path") else None),
                }
        result.append(detail)
    return result


class ResolveAlertRequest(BaseModel):
    notes: str = ""


@app.post("/admin/alerts/{alert_id}/resolve")
def admin_resolve_alert(alert_id: int, payload: ResolveAlertRequest, authorization: str = Header(None)):
    require_admin(authorization)
    db.resolve_alert(alert_id, payload.notes)
    return {"ok": True}
