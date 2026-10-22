"""
database.py — MySQL storage layer for the Mess Monitoring System.

Multi-college design:
- Each college has an authorized email domain (e.g. "nitrkl.ac.in"). A student
  is considered "authorized" simply by their college email matching that
  domain — no manually maintained roster needed, which is what makes this
  scale to many colleges later.
- Mess halls belong to a specific college.
- Student email is stored ONLY in the `complaints` table, and is never
  selected by any public-facing query. Admin views only ever see a masked
  email (see auth.mask_email), never the raw value.
- Alerts track `last_escalated_at` so the 7-day auto-escalation rule
  (see alert_engine.escalate_stale_alerts) has a clock to check against.

Connection settings are read from environment variables so the same code
works locally and in production:
  DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
"""

import os
import ssl
import pymysql
import pymysql.cursors
from datetime import datetime
from dotenv import load_dotenv

# Automatically load variables from a .env file in the project folder,
# so you don't need to manually export them before running streamlit.
load_dotenv()

LEVELS = ["Low", "Medium", "High"]  # index order matters — used for escalation

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", "3306"))
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_NAME = os.environ.get("DB_NAME", "mess_monitor")
DB_SSL_CA = os.environ.get("DB_SSL_CA", "").strip()


def _ssl_context():
    if not DB_SSL_CA:
        return None
    context = ssl.create_default_context()
    context.load_verify_locations(cadata=DB_SSL_CA)
    return context


def get_connection():
    connection_options = dict(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )
    ssl_context = _ssl_context()
    if ssl_context:
        connection_options["ssl"] = ssl_context
    return pymysql.connect(**connection_options)


def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS colleges (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL,
            email_domain VARCHAR(255) UNIQUE NOT NULL,
            mess_head_email VARCHAR(255),
            principal_email VARCHAR(255),
            fssai_contact_email VARCHAR(255)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS college_directory (
            id INT AUTO_INCREMENT PRIMARY KEY,
            source_id VARCHAR(100) UNIQUE NOT NULL,
            name VARCHAR(255) NOT NULL,
            state VARCHAR(100) NOT NULL,
            district VARCHAR(100),
            address TEXT,
            institution_type VARCHAR(100),
            source_name VARCHAR(100) NOT NULL DEFAULT 'AICTE',
            synced_at DATETIME NOT NULL,
            INDEX directory_name (name),
            INDEX directory_state (state)
        )
    """)

    # Migration safety: add contact columns to pre-existing colleges tables
    for col in ("mess_head_email", "principal_email", "fssai_contact_email"):
        c.execute("""
            SELECT COUNT(*) as cnt FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'colleges' AND column_name = %s
        """, (col,))
        if c.fetchone()["cnt"] == 0:
            c.execute(f"ALTER TABLE colleges ADD COLUMN {col} VARCHAR(255)")
            conn.commit()

    c.execute("""
        CREATE TABLE IF NOT EXISTS mess_halls (
            id INT AUTO_INCREMENT PRIMARY KEY,
            college_id INT NOT NULL,
            name VARCHAR(255) NOT NULL,
            UNIQUE KEY college_name (college_id, name),
            FOREIGN KEY (college_id) REFERENCES colleges(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INT AUTO_INCREMENT PRIMARY KEY,
            college_id INT NOT NULL,
            mess_id INT NOT NULL,
            student_email VARCHAR(255) NOT NULL,
            student_name VARCHAR(255),
            category VARCHAR(100) NOT NULL,
            description TEXT,
            photo_path VARCHAR(500),
            created_at DATETIME NOT NULL,
            FOREIGN KEY (college_id) REFERENCES colleges(id),
            FOREIGN KEY (mess_id) REFERENCES mess_halls(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS inspections (
            id INT AUTO_INCREMENT PRIMARY KEY,
            mess_id INT NOT NULL,
            inspector_name VARCHAR(255) NOT NULL,
            responses TEXT NOT NULL,
            score FLOAT NOT NULL,
            created_at DATETIME NOT NULL,
            FOREIGN KEY (mess_id) REFERENCES mess_halls(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            mess_id INT NOT NULL,
            source VARCHAR(50) NOT NULL,
            source_id INT,
            level VARCHAR(20) NOT NULL,
            reason TEXT NOT NULL,
            fssai_reference VARCHAR(255),
            pattern_key VARCHAR(255),
            created_at DATETIME NOT NULL,
            last_escalated_at DATETIME NOT NULL,
            resolved TINYINT NOT NULL DEFAULT 0,
            resolved_at DATETIME,
            resolution_notes TEXT,
            FOREIGN KEY (mess_id) REFERENCES mess_halls(id)
        )
    """)

    # Migration safety: add pattern_key to pre-existing alerts tables that
    # were created before this column existed.
    c.execute("""
        SELECT COUNT(*) as cnt FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'alerts' AND column_name = 'pattern_key'
    """)
    if c.fetchone()["cnt"] == 0:
        c.execute("ALTER TABLE alerts ADD COLUMN pattern_key VARCHAR(255)")
        conn.commit()

    c.execute("""
        CREATE TABLE IF NOT EXISTS alert_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            alert_id INT NOT NULL,
            event VARCHAR(50) NOT NULL,
            level VARCHAR(20) NOT NULL,
            note TEXT,
            timestamp DATETIME NOT NULL,
            FOREIGN KEY (alert_id) REFERENCES alerts(id)
        )
    """)

    conn.commit()

    # Seed one sample college + its mess halls, only on a fresh DB
    c.execute("SELECT COUNT(*) as cnt FROM colleges")
    if c.fetchone()["cnt"] == 0:
        c.execute("INSERT INTO colleges (name, email_domain) VALUES (%s, %s)",
                   ("Sample Institute of Technology", "sample-college.edu"))
        college_id = c.lastrowid
        c.executemany("INSERT INTO mess_halls (college_id, name) VALUES (%s, %s)", [
            (college_id, "Mess A - North Block"),
            (college_id, "Mess B - South Block"),
        ])
        conn.commit()

    conn.close()


def now_iso():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


# ---------- Colleges ----------

def list_colleges():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM colleges ORDER BY name")
    rows = cur.fetchall()
    conn.close()
    return list(rows)


def upsert_college_directory(rows):
    conn = get_connection()
    cur = conn.cursor()
    try:
        for row in rows:
            cur.execute(
                """
                INSERT INTO college_directory
                    (source_id, name, state, district, address, institution_type, source_name, synced_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    name = VALUES(name),
                    state = VALUES(state),
                    district = VALUES(district),
                    address = VALUES(address),
                    institution_type = VALUES(institution_type),
                    synced_at = VALUES(synced_at)
                """,
                (
                    row["source_id"], row["name"], row["state"],
                    row.get("district"), row.get("address"),
                    row.get("institution_type"), row.get("source_name", "AICTE"),
                    now_iso(),
                ),
            )
        conn.commit()
        return len(rows)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_college_directory(state=None, search=None, limit=100):
    conn = get_connection()
    cur = conn.cursor()
    query = "SELECT * FROM college_directory WHERE 1=1"
    params = []
    if state:
        query += " AND state = %s"
        params.append(state)
    if search:
        query += " AND name LIKE %s"
        params.append(f"%{search}%")
    query += " ORDER BY name LIMIT %s"
    params.append(min(max(int(limit), 1), 500))
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return list(rows)


def list_directory_states():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT state FROM college_directory ORDER BY state")
    rows = cur.fetchall()
    conn.close()
    return [row["state"] for row in rows]


def get_college(college_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM colleges WHERE id = %s", (college_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def add_college(name: str, email_domain: str, mess_head_email: str = None,
                 principal_email: str = None, fssai_contact_email: str = None):
    domain = email_domain.strip().lower().lstrip("@")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO colleges (name, email_domain, mess_head_email, principal_email, fssai_contact_email) "
        "VALUES (%s, %s, %s, %s, %s)",
        (name.strip(), domain, mess_head_email, principal_email, fssai_contact_email),
    )
    conn.commit()
    conn.close()


def update_college_contacts(college_id, mess_head_email=None, principal_email=None, fssai_contact_email=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE colleges SET mess_head_email = %s, principal_email = %s, fssai_contact_email = %s WHERE id = %s",
        (mess_head_email, principal_email, fssai_contact_email, college_id),
    )
    conn.commit()
    conn.close()


def get_contact_email_for_level(college_id, level):
    """Looks up the right real contact for a given alert severity level.
    Returns None if that college hasn't set that contact yet — callers
    should handle that gracefully (skip sending, don't crash)."""
    college = get_college(college_id)
    if not college:
        return None
    return {
        "Low": college.get("mess_head_email"),
        "Medium": college.get("principal_email"),
        "High": college.get("fssai_contact_email"),
    }.get(level)


def is_authorized_email(college_id, email: str):
    """A student is authorized simply if their email domain matches the
    college's registered domain — no per-student roster to maintain."""
    college = get_college(college_id)
    if not college:
        return False
    email = email.strip().lower()
    if "@" not in email:
        return False
    domain = email.split("@")[-1]
    return domain == college["email_domain"]


# ---------- Mess halls ----------

def list_mess_halls(college_id=None):
    conn = get_connection()
    cur = conn.cursor()
    if college_id:
        cur.execute("SELECT * FROM mess_halls WHERE college_id = %s ORDER BY name", (college_id,))
    else:
        cur.execute("SELECT * FROM mess_halls ORDER BY name")
    rows = cur.fetchall()
    conn.close()
    return list(rows)


def get_mess_hall(mess_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM mess_halls WHERE id = %s", (mess_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def add_mess_hall(college_id, name: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO mess_halls (college_id, name) VALUES (%s, %s)", (college_id, name.strip()))
    conn.commit()
    conn.close()


def bulk_import_colleges(rows):
    """Create or update colleges and optionally add their mess halls atomically."""
    conn = get_connection()
    cur = conn.cursor()
    imported = 0
    try:
        for row in rows:
            name = row["name"].strip()
            domain = row["email_domain"].strip().lower().lstrip("@")
            if not name or not domain:
                raise ValueError("college_name and email_domain are required")

            cur.execute(
                """
                INSERT INTO colleges
                    (name, email_domain, mess_head_email, principal_email, fssai_contact_email)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    email_domain = VALUES(email_domain),
                    mess_head_email = COALESCE(VALUES(mess_head_email), mess_head_email),
                    principal_email = COALESCE(VALUES(principal_email), principal_email),
                    fssai_contact_email = COALESCE(VALUES(fssai_contact_email), fssai_contact_email)
                """,
                (
                    name,
                    domain,
                    row.get("mess_head_email") or None,
                    row.get("principal_email") or None,
                    row.get("fssai_contact_email") or None,
                ),
            )
            cur.execute("SELECT id FROM colleges WHERE name = %s", (name,))
            college_id = cur.fetchone()["id"]
            mess_name = row.get("mess_hall_name", "").strip()
            if mess_name:
                cur.execute(
                    "INSERT IGNORE INTO mess_halls (college_id, name) VALUES (%s, %s)",
                    (college_id, mess_name),
                )
            imported += 1
        conn.commit()
        return imported
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_mess_hall(mess_id):
    """Deletes a mess hall. Will fail if complaints/inspections/alerts still
    reference it (foreign key constraint) — caller should catch and surface
    a clear message rather than silently losing data."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM mess_halls WHERE id = %s", (mess_id,))
    conn.commit()
    conn.close()


def delete_college(college_id):
    """Deletes a college. Will fail if any mess halls still exist under it
    (delete those first) — same reasoning as delete_mess_hall."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM colleges WHERE id = %s", (college_id,))
    conn.commit()
    conn.close()


# ---------- Complaints ----------

def insert_complaint(college_id, mess_id, student_email, student_name, category, description, photo_path=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO complaints (college_id, mess_id, student_email, student_name, category, description, photo_path, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (college_id, mess_id, student_email.strip().lower(), student_name, category, description, photo_path, now_iso()),
    )
    conn.commit()
    complaint_id = cur.lastrowid
    conn.close()
    return complaint_id


def recent_complaint_count(mess_id, category, hours=24):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) as cnt FROM complaints WHERE mess_id = %s AND category = %s "
        "AND created_at >= (NOW() - INTERVAL %s HOUR)",
        (mess_id, category, hours),
    )
    row = cur.fetchone()
    conn.close()
    return row["cnt"]


def count_complaints(mess_id, category=None):
    """All-time count of complaints for a mess hall — used to check whether
    enough independent reports exist to treat an issue as verified.
    If category is given, counts only that category; otherwise counts all."""
    conn = get_connection()
    cur = conn.cursor()
    if category:
        cur.execute(
            "SELECT COUNT(*) as cnt FROM complaints WHERE mess_id = %s AND category = %s",
            (mess_id, category),
        )
    else:
        cur.execute("SELECT COUNT(*) as cnt FROM complaints WHERE mess_id = %s", (mess_id,))
    row = cur.fetchone()
    conn.close()
    return row["cnt"]


def pattern_alert_exists(pattern_key):
    """Checks whether an alert has already been raised for this specific
    pattern (e.g. 'mess 5, category Stale food' or 'mess 5, all categories'),
    so we don't create a duplicate alert every time the threshold is exceeded
    further (e.g. at complaint #21, #22, ...)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM alerts WHERE pattern_key = %s LIMIT 1", (pattern_key,))
    row = cur.fetchone()
    conn.close()
    return row is not None


def get_complaints_since(college_id, since_date):
    """Raw complaints (not alerts) within a college, since a given date —
    used to power the dashboard charts + description lists."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT complaints.*, mess_halls.name as mess_name FROM complaints "
        "JOIN mess_halls ON complaints.mess_id = mess_halls.id "
        "WHERE complaints.college_id = %s AND complaints.created_at >= %s "
        "ORDER BY complaints.created_at DESC",
        (college_id, since_date),
    )
    rows = cur.fetchall()
    conn.close()
    return list(rows)


def get_my_complaints(email):
    """All complaints filed by this verified email, newest first."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT complaints.*, mess_halls.name as mess_name FROM complaints "
        "JOIN mess_halls ON complaints.mess_id = mess_halls.id "
        "WHERE complaints.student_email = %s ORDER BY complaints.created_at DESC",
        (email.strip().lower(),),
    )
    rows = cur.fetchall()
    conn.close()
    return list(rows)


def get_alert_for_complaint(complaint_id):
    """The pattern alert (if any) that this specific complaint helped trigger."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM alerts WHERE source_id = %s AND source = 'complaint_pattern'",
        (complaint_id,),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def mark_alert_resolved_by_student(alert_id, student_email):
    """Lets the student who triggered the alert close it out themselves,
    once it's been escalating for 2+ days. Records who resolved it."""
    ts = now_iso()
    conn = get_connection()
    cur = conn.cursor()
    notes = f"Marked resolved by reporting student ({student_email})"
    cur.execute(
        "UPDATE alerts a JOIN complaints c ON a.source = 'complaint_pattern' "
        "AND a.source_id = c.id SET a.resolved = 1, a.resolved_at = %s, "
        "a.resolution_notes = %s WHERE a.id = %s AND c.student_email = %s",
        (ts, notes, alert_id, student_email.strip().lower()),
    )
    if cur.rowcount != 1:
        conn.rollback()
        conn.close()
        return False
    cur.execute("SELECT level FROM alerts WHERE id = %s", (alert_id,))
    row = cur.fetchone()
    cur.execute(
        "INSERT INTO alert_history (alert_id, event, level, note, timestamp) VALUES (%s, 'resolved', %s, %s, %s)",
        (alert_id, row["level"], notes, ts),
    )
    conn.commit()
    conn.close()
    return True


def get_complaint_private(complaint_id):
    """Full complaint record INCLUDING student email — only ever call this
    from the password-gated admin panel, and only mask_email() the result before display."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM complaints WHERE id = %s", (complaint_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


# ---------- Inspections ----------

def insert_inspection(mess_id, inspector_name, responses_json, score):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO inspections (mess_id, inspector_name, responses, score, created_at) VALUES (%s, %s, %s, %s, %s)",
        (mess_id, inspector_name, responses_json, score, now_iso()),
    )
    conn.commit()
    inspection_id = cur.lastrowid
    conn.close()
    return inspection_id


# ---------- Alerts ----------

def insert_alert(mess_id, source, source_id, level, reason, fssai_reference, pattern_key=None):
    ts = now_iso()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO alerts (mess_id, source, source_id, level, reason, fssai_reference, pattern_key, created_at, last_escalated_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (mess_id, source, source_id, level, reason, fssai_reference, pattern_key, ts, ts),
    )
    conn.commit()
    alert_id = cur.lastrowid
    cur.execute(
        "INSERT INTO alert_history (alert_id, event, level, note, timestamp) VALUES (%s, 'created', %s, %s, %s)",
        (alert_id, level, reason, ts),
    )
    conn.commit()
    conn.close()
    return alert_id


def get_alerts(college_id=None, mess_id=None, level=None, resolved=None, start_date=None, end_date=None):
    query = """
        SELECT alerts.*, mess_halls.name as mess_name, mess_halls.college_id as college_id
        FROM alerts JOIN mess_halls ON alerts.mess_id = mess_halls.id
        WHERE 1=1
    """
    params = []
    if college_id:
        query += " AND mess_halls.college_id = %s"
        params.append(college_id)
    if mess_id:
        query += " AND alerts.mess_id = %s"
        params.append(mess_id)
    if level:
        query += " AND alerts.level = %s"
        params.append(level)
    if resolved is not None:
        query += " AND alerts.resolved = %s"
        params.append(1 if resolved else 0)
    if start_date:
        query += " AND DATE(alerts.created_at) >= %s"
        params.append(start_date)
    if end_date:
        query += " AND DATE(alerts.created_at) <= %s"
        params.append(end_date)
    query += " ORDER BY alerts.created_at DESC"

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return list(rows)


def get_alerts_with_details(college_id=None, start_date=None, end_date=None):
    """Same as get_alerts but also joins in the complaint category (null for
    inspection-sourced alerts) — used for category-level trend breakdowns."""
    query = """
        SELECT alerts.*, mess_halls.name as mess_name, mess_halls.college_id as college_id,
               complaints.category as complaint_category
        FROM alerts
        JOIN mess_halls ON alerts.mess_id = mess_halls.id
        LEFT JOIN complaints ON alerts.source IN ('complaint', 'complaint_pattern') AND alerts.source_id = complaints.id
        WHERE 1=1
    """
    params = []
    if college_id:
        query += " AND mess_halls.college_id = %s"
        params.append(college_id)
    if start_date:
        query += " AND DATE(alerts.created_at) >= %s"
        params.append(start_date)
    if end_date:
        query += " AND DATE(alerts.created_at) <= %s"
        params.append(end_date)
    query += " ORDER BY alerts.created_at DESC"

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return list(rows)


def get_unresolved_stale_alerts(days=7):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM alerts WHERE resolved = 0 AND level != %s "
        "AND last_escalated_at <= (NOW() - INTERVAL %s DAY)",
        (LEVELS[-1], days),
    )
    rows = cur.fetchall()
    conn.close()
    return list(rows)


def escalate_alert(alert_id, new_level):
    from fssai_rules import get_authority
    ts = now_iso()
    note = f"Auto-escalated: unresolved for 7+ days — now handled by {get_authority(new_level)}"
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE alerts SET level = %s, last_escalated_at = %s WHERE id = %s",
        (new_level, ts, alert_id),
    )
    cur.execute(
        "INSERT INTO alert_history (alert_id, event, level, note, timestamp) VALUES (%s, 'escalated', %s, %s, %s)",
        (alert_id, new_level, note, ts),
    )
    conn.commit()
    conn.close()


def resolve_alert(alert_id, notes=""):
    ts = now_iso()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE alerts SET resolved = 1, resolved_at = %s, resolution_notes = %s WHERE id = %s",
        (ts, notes, alert_id),
    )
    cur.execute("SELECT level FROM alerts WHERE id = %s", (alert_id,))
    row = cur.fetchone()
    cur.execute(
        "INSERT INTO alert_history (alert_id, event, level, note, timestamp) VALUES (%s, 'resolved', %s, %s, %s)",
        (alert_id, row["level"], notes, ts),
    )
    conn.commit()
    conn.close()
