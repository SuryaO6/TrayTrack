# TrayTrack Security Review

Review date: 2026-10-22

This review documents security findings identified in the application code.
The findings below were remediated in commit `SECURITY_FIX_COMMIT` after the
initial report.

## Findings

### HIGH: Default administrative credentials and signing secret

- **Location:** `backend/auth.py:15-16`
- **Confidence:** 10/10
- **Issue:** The application falls back to the known values
  `changeme123` and `dev-secret-change-me` when `MESS_ADMIN_PASSWORD` or
  `ADMIN_TOKEN_SECRET` is missing. A deployment that omits these variables can
  be taken over through the admin login.
- **Impact:** Administrative takeover, including management of colleges and
  mess halls, alert resolution, inspections, and access to complaint details.
- **Recommended remediation:** Fail closed at startup when either variable is
  missing or still equals a development default. Require strong,
  deployment-provided secrets and rotate any values already used in a
  deployment.

### HIGH: Client-controlled user identity header

- **Location:** `backend/main.py:76-103`
- **Confidence:** 10/10
- **Issue:** Protected user endpoints accept any non-empty `X-User-Email`
  header. Google sign-in verification does not result in a server-verifiable
  session, so a caller can substitute another user's email.
- **Impact:** User impersonation and unauthorized access to another student's
  complaint history.
- **Recommended remediation:** Issue a short-lived, signed server session or
  JWT after Google verification and validate it on every request. Do not treat
  a client-supplied email header or local-storage value as an identity
  assertion.

### HIGH: Missing alert ownership check

- **Location:** `backend/main.py:249-266`,
  `backend/database.py:534-553`
- **Confidence:** 9/10
- **Issue:** The student alert-resolution endpoint checks only that an alert
  exists, is unresolved, and is old enough. It does not verify that the
  authenticated student filed the complaint associated with the alert, and
  the database update is keyed only by `alert_id`.
- **Impact:** Any caller who can reach the endpoint can resolve another
  student's eligible alert.
- **Recommended remediation:** Associate alerts with their originating
  complaint/reporting student and perform an ownership check in the same
  transactional update.

### MEDIUM: Mess hall is not checked against college

- **Location:** `backend/main.py:185-219`,
  `backend/alert_engine.py:50-68`
- **Confidence:** 9/10
- **Issue:** Complaint submission validates the email against the supplied
  college but does not verify that the supplied mess hall belongs to that
  college.
- **Impact:** Cross-college complaint pollution, manipulated alert thresholds,
  and notifications sent to another institution's authorities.
- **Recommended remediation:** Resolve the mess hall server-side and reject
  the request unless its `college_id` matches. Prefer deriving the college
  from the mess hall instead of trusting both client-supplied identifiers.

## Recommended priority

1. Replace client-controlled identity with a server-verifiable session.
2. Remove default administrative credentials and signing secrets.
3. Add alert ownership enforcement.
4. Validate the college-to-mess-hall relationship during complaint creation.

## Remediation status

All four findings have been addressed:

- The backend now requires non-default admin credentials and a token secret at
  startup.
- Google login now issues a signed, expiring user token; protected user
  endpoints derive the email from that token.
- Student alert resolution is restricted to the student associated with the
  complaint that triggered the alert.
- Complaint submission rejects mess halls that do not belong to the selected
  college.
