const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

function authHeaders() {
  const email = localStorage.getItem("user_email");
  return email ? { "X-User-Email": email } : {};
}

function adminHeaders() {
  const token = sessionStorage.getItem("admin_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function loginWithGoogle(credential) {
  const res = await fetch(`${API_BASE}/auth/google`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ credential }),
  });
  if (!res.ok) throw new Error("Google sign-in failed");
  return res.json();
}

export async function adminLogin(password) {
  const res = await fetch(`${API_BASE}/admin/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail || "Incorrect password");
  sessionStorage.setItem("admin_token", body.token);
  return body;
}

export async function getColleges() {
  const res = await fetch(`${API_BASE}/colleges`);
  return res.json();
}

export async function getMessHalls(collegeId) {
  const res = await fetch(`${API_BASE}/mess-halls?college_id=${collegeId}`);
  return res.json();
}

export async function getCategories() {
  const res = await fetch(`${API_BASE}/categories`);
  return res.json();
}

export async function getChecklist() {
  const res = await fetch(`${API_BASE}/checklist`);
  return res.json();
}

export async function submitComplaint(fields, photoFile) {
  const formData = new FormData();
  Object.entries(fields).forEach(([k, v]) => formData.append(k, v));
  if (photoFile) formData.append("photo", photoFile);

  const res = await fetch(`${API_BASE}/complaints`, {
    method: "POST",
    headers: authHeaders(),
    body: formData,
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail || "Failed to submit complaint");
  return body;
}

export async function getMyComplaints() {
  const res = await fetch(`${API_BASE}/my-complaints`, { headers: authHeaders() });
  return res.json();
}

export async function resolveMyAlert(alertId) {
  const res = await fetch(`${API_BASE}/my-complaints/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ alert_id: alertId }),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail || "Failed to resolve");
  return body;
}

export async function getDashboardStatus(collegeId) {
  const res = await fetch(`${API_BASE}/dashboard-status?college_id=${collegeId}`);
  return res.json();
}

export async function getAnalytics(collegeId) {
  const res = await fetch(`${API_BASE}/analytics?college_id=${collegeId}`);
  return res.json();
}

export async function getOpenAlerts(collegeId, messId) {
  const params = new URLSearchParams();
  if (collegeId) params.set("college_id", collegeId);
  if (messId) params.set("mess_id", messId);
  const res = await fetch(`${API_BASE}/alerts?${params}`);
  return res.json();
}

export async function getTrends(collegeId, startDate, endDate) {
  const params = new URLSearchParams();
  if (collegeId) params.set("college_id", collegeId);
  if (startDate) params.set("start_date", startDate);
  if (endDate) params.set("end_date", endDate);
  const res = await fetch(`${API_BASE}/trends?${params}`);
  return res.json();
}

export async function submitInspection(data) {
  const res = await fetch(`${API_BASE}/inspections`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...adminHeaders() },
    body: JSON.stringify(data),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail || "Failed to submit inspection");
  return body;
}

export async function adminAddCollege(data) {
  const res = await fetch(`${API_BASE}/admin/colleges`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...adminHeaders() },
    body: JSON.stringify(data),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail || "Failed");
  return body;
}

export async function adminImportColleges(file) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/admin/colleges/import`, {
    method: "POST",
    headers: adminHeaders(),
    body: form,
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail || "Import failed");
  return body;
}

export async function adminSearchCollegeDirectory({ state, search, limit = 50 }) {
  const params = new URLSearchParams();
  if (state) params.set("state", state);
  if (search) params.set("search", search);
  params.set("limit", String(limit));
  const res = await fetch(`${API_BASE}/admin/college-directory?${params}`, {
    headers: adminHeaders(),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail || "Directory search failed");
  return body;
}

export async function adminGetCollegeDirectoryStates() {
  const res = await fetch(`${API_BASE}/admin/college-directory/states`, {
    headers: adminHeaders(),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail || "Could not load directory states");
  return body;
}

export async function adminUpdateCollegeContacts(collegeId, data) {
  const res = await fetch(`${API_BASE}/admin/colleges/${collegeId}/contacts`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...adminHeaders() },
    body: JSON.stringify(data),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail || "Failed");
  return body;
}

export async function adminAddMessHall(data) {
  const res = await fetch(`${API_BASE}/admin/mess-halls`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...adminHeaders() },
    body: JSON.stringify(data),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail || "Failed");
  return body;
}

export async function adminDeleteMessHall(messId) {
  const res = await fetch(`${API_BASE}/admin/mess-halls/${messId}`, {
    method: "DELETE",
    headers: adminHeaders(),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail || "Failed to delete");
  return body;
}

export async function adminDeleteCollege(collegeId) {
  const res = await fetch(`${API_BASE}/admin/colleges/${collegeId}`, {
    method: "DELETE",
    headers: adminHeaders(),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail || "Failed to delete");
  return body;
}

export async function adminGetAlerts(resolved = false) {
  const res = await fetch(`${API_BASE}/admin/alerts?resolved=${resolved}`, { headers: adminHeaders() });
  return res.json();
}

export async function adminResolveAlert(alertId, notes) {
  const res = await fetch(`${API_BASE}/admin/alerts/${alertId}/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...adminHeaders() },
    body: JSON.stringify({ notes }),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail || "Failed");
  return body;
}

export const UPLOADS_BASE = API_BASE;
