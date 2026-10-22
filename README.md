# TrayTrack

A mess/canteen food safety monitoring system, aligned to FSSAI-style hygiene
requirements, with a 3-level alert system, an authority escalation chain, and
a public dashboard. Built to start with one college and scale to many.

**Stack:** React (frontend) + FastAPI (backend) + MySQL (database) +
Google Sign-In (student identity verification).

## Features

- **Multi-college ready** — each college has an authorized email domain
  (e.g. `nitrkl.ac.in`). Any student whose email matches that domain is
  automatically recognized — no manual roster to maintain. Mess halls
  belong to a specific college, so complaints/inspections are always
  correctly scoped.
- **Google Sign-In** — students sign in with their real college Google
  account (works because college emails are Google Workspace accounts).
  Their verified email is used directly for submitting complaints and
  viewing their own report history — no separate password, no retyping.
- **Student complaints** — tied to the signed-in student's verified email,
  with an optional photo upload as evidence (max 4MB, JPEG/PNG/WEBP only,
  validated both client- and server-side). Categories: food poisoning,
  insect in food, foreign object, undercooked, stale/spoiled, hygiene issue,
  too oily, overcooked/burnt, too spicy, other.
- **Pattern-verified alerts** — every complaint is recorded immediately as
  evidence, but an alert only fires once a pattern is confirmed:
  - **20+ complaints in the same category** at a mess hall (all-time), or
  - **45+ complaints of any category combined** at a mess hall (all-time).
  This avoids a single (possibly mistaken or malicious) complaint
  triggering escalation on its own. Once a pattern triggers an alert, later
  complaints keep being recorded but won't create duplicate alerts.
- **My Reports** — students can see their own complaint history and, once
  an alert has been escalating for **2+ days**, mark it resolved themselves
  if the issue is actually fixed.
- **Inspector checklist entry** — password-protected. FSSAI-aligned hygiene
  checklist, auto-scored. Failing any *critical* item (temperature control,
  cross-contamination, potable water, pest control, expiry checks) triggers
  a **High** alert regardless of overall score.
- **3-level alerts mapped to an authority chain**:
  - 🟢 Low → **Mess Head**
  - 🟡 Medium → **Principal**
  - 🔴 High → **FSSAI**
- **Auto-escalation** — any alert unresolved for **7 days** automatically
  moves up the chain.
- **Admin Panel** — password-protected. Add/remove colleges and mess halls,
  resolve alerts, view attached photos. The real password is sent only once
  at login — the backend issues a signed, expiring token (8 hours) that the
  frontend uses for all further admin/inspector requests instead of
  resending the password. 5 failed login attempts locks that IP out for
  6 hours.
- **Privacy** — student email is stored only in the private `complaints`
  table and is never shown on the public dashboard. Even the password-gated
  Admin Panel only shows a **masked** email
  (`john.doe@college.edu` → `jo******@college.edu`). Complaint photos are
  also only visible in the Admin Panel, never publicly.

## Project structure

```
traytrack/
├── backend/                       FastAPI + MySQL
│   ├── main.py                    All API endpoints
│   ├── database.py                MySQL schema + queries
│   ├── alert_engine.py            Alert creation + pattern thresholds + escalation
│   ├── fssai_rules.py             Checklist + severity + authority mapping
│   ├── auth.py                    Email masking + admin password check
│   ├── uploads/complaints/        Complaint photo storage
│   ├── requirements.txt
│   └── .env.example               DB credentials + Google Client ID template
└── frontend/                      React (Vite)
    └── src/
        ├── App.jsx                Top nav + tab routing
        ├── api.js                 All backend API calls
        ├── Login.jsx              Google Sign-In screen
        ├── SubmitComplaint.jsx    Complaint form (+ photo upload)
        ├── MyReports.jsx          Student's own history + resolve button
        ├── PublicDashboard.jsx    Public: status per mess hall + open alerts
        ├── HistoryTrends.jsx      Public: aggregate trends over time
        ├── InspectorEntry.jsx     Password-gated: hygiene checklist entry
        ├── AdminPanel.jsx         Password-gated: manage colleges/mess halls, resolve alerts
        └── index.css              Styling
```

## Setup

### 1. Database
```sql
CREATE DATABASE mess_monitor;
```
Tables are created automatically the first time the backend starts.

### 2. Backend
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # then fill in your real MySQL password
uvicorn main:app --reload
```
Runs at `http://localhost:8000`.

### 3. Frontend
```bash
cd frontend
npm install
npm run dev
```
Runs at `http://localhost:5173`.

### 4. Google Sign-In setup (one-time, in Google Cloud Console)
1. Create a project → **APIs & Services → Google Auth Platform** → set up
   the consent screen (External, add your app name + support email).
2. **APIs & Services → Credentials → Create Credentials → OAuth Client ID**
   → Application type: **Web application**.
3. Add an **Authorized JavaScript origin**: `http://localhost:5173`
4. Copy the **Client ID** and **Client Secret** into:
   - `backend/.env` → `GOOGLE_CLIENT_ID`
   - `frontend/src/App.jsx` → `GOOGLE_CLIENT_ID` constant

**Note:** while the app is in "Testing" mode in Google Cloud Console, only
the test users you've explicitly added can sign in. Publish the app
(Google Auth Platform → Audience → Publish) to let any student sign in —
this is free and doesn't require verification for basic email sign-in.

## Adding your real college(s)

Go to **Admin Panel** (password set via `MESS_ADMIN_PASSWORD` env var,
default `changeme123`) → **Manage colleges & mess halls** tab:
1. Add your college with its real student email domain.
2. Add each mess hall under that college.
3. Repeat for additional colleges whenever you're ready to expand.

Students then just sign in with their real college Google account — no
separate registration step needed.

## Before real deployment

- **Change the admin password and token secret** — set `MESS_ADMIN_PASSWORD`
  and `ADMIN_TOKEN_SECRET` via environment variables to real, random values
  instead of the defaults.
- **Publish the Google OAuth consent screen** (see above) so real students
  (not just test users) can sign in.
- **Host MySQL somewhere reachable from your deployed backend** — not just
  `localhost` — if you deploy the backend to a server (e.g. PlanetScale,
  Railway MySQL, AWS RDS).
- Consider running the 7-day escalation check via a scheduled job rather
  than only when a page loads, if the app might go untouched for stretches
  of time.
