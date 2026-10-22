import { useEffect, useState } from "react";
import {
  adminLogin, getColleges, getMessHalls, adminAddCollege, adminAddMessHall,
  adminDeleteMessHall, adminDeleteCollege, adminUpdateCollegeContacts,
  adminGetAlerts, adminResolveAlert, adminImportColleges, UPLOADS_BASE,
  adminSearchCollegeDirectory, adminGetCollegeDirectoryStates,
} from "./api";

export default function AdminPanel() {
  const [authed, setAuthed] = useState(!!sessionStorage.getItem("admin_token"));
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const [tab, setTab] = useState("colleges");

  const [colleges, setColleges] = useState([]);
  const [collegeName, setCollegeName] = useState("");
  const [collegeDomain, setCollegeDomain] = useState("");
  const [messHeadEmail, setMessHeadEmail] = useState("");
  const [principalEmail, setPrincipalEmail] = useState("");
  const [fssaiEmail, setFssaiEmail] = useState("");
  const [messCollegeId, setMessCollegeId] = useState("");
  const [messName, setMessName] = useState("");
  const [manageError, setManageError] = useState("");
  const [importFile, setImportFile] = useState(null);
  const [importStatus, setImportStatus] = useState("");
  const [directoryState, setDirectoryState] = useState("");
  const [directoryStates, setDirectoryStates] = useState([]);
  const [selectedDirectoryCollege, setSelectedDirectoryCollege] = useState("");
  const [directoryResults, setDirectoryResults] = useState([]);
  const [directoryLoading, setDirectoryLoading] = useState(false);
  const [contactDrafts, setContactDrafts] = useState({});

  const [alerts, setAlerts] = useState([]);
  const [notesById, setNotesById] = useState({});
  const [messHallsByCollege, setMessHallsByCollege] = useState({});

  async function handleLogin(e) {
    e.preventDefault();
    try {
      await adminLogin(password);
      setAuthed(true);
    } catch (err) {
      setLoginError(err.message);
    }
  }

  function loadColleges() {
    getColleges().then((cs) => {
      setColleges(cs);
      if (cs.length && !messCollegeId) setMessCollegeId(cs[0].id);
      const drafts = {};
      cs.forEach((c) => {
        drafts[c.id] = {
          mess_head_email: c.mess_head_email || "",
          principal_email: c.principal_email || "",
          fssai_contact_email: c.fssai_contact_email || "",
        };
        getMessHalls(c.id).then((halls) =>
          setMessHallsByCollege((prev) => ({ ...prev, [c.id]: halls }))
        );
      });
      setContactDrafts(drafts);
    });
  }
  function loadAlerts() {
    adminGetAlerts(false).then(setAlerts);
  }

  useEffect(() => {
    if (authed) {
      loadColleges();
      loadAlerts();
      adminGetCollegeDirectoryStates().then(setDirectoryStates).catch((err) => setManageError(err.message));
    }
  }, [authed]);

  async function handleAddCollege(e) {
    e.preventDefault();
    setManageError("");
    try {
      await adminAddCollege({
        name: collegeName, email_domain: collegeDomain,
        mess_head_email: messHeadEmail || null,
        principal_email: principalEmail || null,
        fssai_contact_email: fssaiEmail || null,
      });
      setCollegeName(""); setCollegeDomain("");
      setMessHeadEmail(""); setPrincipalEmail(""); setFssaiEmail("");
      loadColleges();
    } catch (err) { setManageError(err.message); }
  }

  async function handleImportColleges(e) {
    e.preventDefault();
    setManageError("");
    setImportStatus("");
    if (!importFile) {
      setManageError("Choose a CSV file first.");
      return;
    }
    try {
      const result = await adminImportColleges(importFile);
      setImportStatus(`Imported ${result.rows_imported} row(s).`);
      setImportFile(null);
      e.target.reset();
      loadColleges();
    } catch (err) { setManageError(err.message); }
  }

  async function loadDirectoryColleges(state) {
    setManageError("");
    setDirectoryLoading(true);
    try {
      setDirectoryResults(await adminSearchCollegeDirectory({
        state,
        search: "",
        limit: 500,
      }));
      setSelectedDirectoryCollege("");
    } catch (err) {
      setManageError(err.message);
    } finally {
      setDirectoryLoading(false);
    }
  }

  function applyDirectoryCollege(college) {
    setCollegeName(college.name);
    setCollegeDomain("");
    setMessHeadEmail("");
    setPrincipalEmail("");
    setFssaiEmail("");
    setManageError("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function selectDirectoryCollege(sourceId) {
    setSelectedDirectoryCollege(sourceId);
    const college = directoryResults.find((item) => item.source_id === sourceId);
    if (college) applyDirectoryCollege(college);
  }

  async function handleSaveContacts(collegeId) {
    try {
      await adminUpdateCollegeContacts(collegeId, contactDrafts[collegeId]);
      loadColleges();
    } catch (err) { alert(err.message); }
  }

  async function handleAddMessHall(e) {
    e.preventDefault();
    setManageError("");
    try {
      await adminAddMessHall({ college_id: Number(messCollegeId), name: messName });
      setMessName("");
      loadColleges();
    } catch (err) { setManageError(err.message); }
  }

  async function handleResolve(alertId) {
    try {
      await adminResolveAlert(alertId, notesById[alertId] || "");
      loadAlerts();
    } catch (err) { alert(err.message); }
  }

  async function handleDeleteMessHall(messId) {
    if (!confirm("Delete this mess hall? This can't be undone.")) return;
    try {
      await adminDeleteMessHall(messId);
      loadColleges();
    } catch (err) { alert(err.message); }
  }

  async function handleDeleteCollege(collegeId) {
    if (!confirm("Delete this college? This can't be undone.")) return;
    try {
      await adminDeleteCollege(collegeId);
      loadColleges();
    } catch (err) { alert(err.message); }
  }

  if (!authed) {
    return (
      <div className="content">
        <h1>🔐 Admin panel</h1>
        <form onSubmit={handleLogin} className="form-card">
          <label>
            Admin password
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </label>
          {loginError && <div className="banner error">{loginError}</div>}
          <button className="primary-btn" type="submit">Log in</button>
        </form>
      </div>
    );
  }

  return (
    <div className="content wide">
      <h1>🔐 Admin panel</h1>

      <div className="tab-row">
        <button className={`tab-btn ${tab === "colleges" ? "active" : ""}`} onClick={() => setTab("colleges")}>
          🏫 Manage colleges &amp; mess halls
        </button>
        <button className={`tab-btn ${tab === "alerts" ? "active" : ""}`} onClick={() => setTab("alerts")}>
          🚨 Open alerts
        </button>
      </div>

      {tab === "colleges" && (
        <>
          <h2>Add a college</h2>
          <form onSubmit={handleAddCollege} className="form-card">
            <label>College name<input value={collegeName} onChange={(e) => setCollegeName(e.target.value)} /></label>
            <label>Authorized email domain
              <input value={collegeDomain} onChange={(e) => setCollegeDomain(e.target.value)} placeholder="e.g. nitrkl.ac.in" />
            </label>
            <p className="hint">
              These three contacts receive real alert emails — 🟢 Low → Mess Head, 🟡 Medium → Principal, 🔴 High → FSSAI.
            </p>
            <label>Mess Head email
              <input type="email" value={messHeadEmail} onChange={(e) => setMessHeadEmail(e.target.value)} />
            </label>
            <label>Principal email
              <input type="email" value={principalEmail} onChange={(e) => setPrincipalEmail(e.target.value)} />
            </label>
            <label>FSSAI contact email
              <input type="email" value={fssaiEmail} onChange={(e) => setFssaiEmail(e.target.value)} />
            </label>
            <button className="primary-btn" type="submit">Add college</button>
          </form>

          <h2 style={{ marginTop: 28 }}>Select a college from the directory</h2>
          <div className="form-card">
            <p className="hint">
              Select a state, then select a college. The dataset fills the
              college name and directory details; verify the official domain,
              contacts, and mess hall before adding it as active.
            </p>
            <label>State
              <select
                value={directoryState}
                onChange={(e) => {
                  const state = e.target.value;
                  setDirectoryState(state);
                  if (state) loadDirectoryColleges(state);
                  else setDirectoryResults([]);
                }}
              >
                <option value="">Select a state</option>
                {directoryStates.map((state) => <option key={state} value={state}>{state}</option>)}
              </select>
            </label>
            {directoryState && (
              <label>College
                <select
                  value={selectedDirectoryCollege}
                  onChange={(e) => selectDirectoryCollege(e.target.value)}
                  disabled={directoryLoading}
                >
                  <option value="">
                    {directoryLoading ? "Loading colleges..." : "Select a college"}
                  </option>
                  {directoryResults.map((college) => (
                    <option key={college.source_id} value={college.source_id}>
                      {college.name}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {selectedDirectoryCollege && (
              <p className="hint">
                The selected college name has been copied into the Add a college
                form above. Directory data does not contain verified contact
                emails or student email domains.
              </p>
            )}
          </div>

          <h2 style={{ marginTop: 28 }}>Bulk import colleges</h2>
          <form onSubmit={handleImportColleges} className="form-card">
            <p className="hint">
              Upload a UTF-8 CSV. Use one row per mess hall; repeat the college
              details when a college has multiple mess halls.
            </p>
            <code>college_name,email_domain,mess_head_email,principal_email,fssai_contact_email,mess_hall_name</code>
            <input type="file" accept=".csv,text/csv" onChange={(e) => setImportFile(e.target.files[0] || null)} />
            <button className="primary-btn" type="submit">Import CSV</button>
            {importStatus && <div className="banner success">{importStatus}</div>}
          </form>

          <h2 style={{ marginTop: 28 }}>Add a mess hall</h2>
          <form onSubmit={handleAddMessHall} className="form-card">
            <label>College
              <select value={messCollegeId} onChange={(e) => setMessCollegeId(e.target.value)}>
                {colleges.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
            <label>Mess hall name<input value={messName} onChange={(e) => setMessName(e.target.value)} /></label>
            <button className="primary-btn" type="submit">Add mess hall</button>
          </form>

          {manageError && <div className="banner error">{manageError}</div>}

          <h2 style={{ marginTop: 28 }}>Current colleges &amp; mess halls</h2>
          {colleges.map((c) => (
            <div key={c.id} className="report-card">
              <div className="report-card-head">
                <strong>{c.name}</strong> — domain <code>@{c.email_domain}</code>
                <button className="link-btn" onClick={() => handleDeleteCollege(c.id)}>Delete college</button>
              </div>

              <div className="contact-grid">
                <label>Mess Head email
                  <input
                    type="email"
                    value={contactDrafts[c.id]?.mess_head_email || ""}
                    onChange={(e) => setContactDrafts({
                      ...contactDrafts,
                      [c.id]: { ...contactDrafts[c.id], mess_head_email: e.target.value },
                    })}
                  />
                </label>
                <label>Principal email
                  <input
                    type="email"
                    value={contactDrafts[c.id]?.principal_email || ""}
                    onChange={(e) => setContactDrafts({
                      ...contactDrafts,
                      [c.id]: { ...contactDrafts[c.id], principal_email: e.target.value },
                    })}
                  />
                </label>
                <label>FSSAI contact email
                  <input
                    type="email"
                    value={contactDrafts[c.id]?.fssai_contact_email || ""}
                    onChange={(e) => setContactDrafts({
                      ...contactDrafts,
                      [c.id]: { ...contactDrafts[c.id], fssai_contact_email: e.target.value },
                    })}
                  />
                </label>
              </div>
              <button className="link-btn" onClick={() => handleSaveContacts(c.id)}>Save contacts</button>

              {(messHallsByCollege[c.id] || []).length === 0 && (
                <p className="hint">(no mess halls yet)</p>
              )}
              {(messHallsByCollege[c.id] || []).map((h) => (
                <div key={h.id} className="mess-hall-row">
                  <span>{h.name}</span>
                  <button className="link-btn" onClick={() => handleDeleteMessHall(h.id)}>Delete</button>
                </div>
              ))}
            </div>
          ))}
        </>
      )}

      {tab === "alerts" && (
        <>
          <p className="hint">Even here, student emails are masked — this is the only place they're visible at all.</p>
          {alerts.length === 0 && <div className="banner info">No open alerts.</div>}
          {alerts.map((a) => (
            <div key={a.id} className="report-card">
              <div className="report-card-head">
                <strong>#{a.id} · {a.mess_name} · {a.level}</strong>
                <span className="hint">{a.created_at}</span>
              </div>
              <p><strong>Reason:</strong> {a.reason}</p>
              <p><strong>FSSAI reference:</strong> {a.fssai_reference}</p>
              <p className="hint">Source: {a.source} (record #{a.source_id})</p>

              {a.complaint && (
                <div className="hint" style={{ marginBottom: 10 }}>
                  <p><strong>Reporting student (masked):</strong> {a.complaint.masked_email}</p>
                  <p><strong>Category:</strong> {a.complaint.category}</p>
                  {a.complaint.description && <p><strong>Description:</strong> {a.complaint.description}</p>}
                  {a.complaint.photo_url && (
                    <img src={`${UPLOADS_BASE}${a.complaint.photo_url}`} alt="Attached" style={{ maxWidth: 240, borderRadius: 8 }} />
                  )}
                </div>
              )}

              <input
                placeholder="Resolution notes"
                value={notesById[a.id] || ""}
                onChange={(e) => setNotesById({ ...notesById, [a.id]: e.target.value })}
                style={{ marginBottom: 8, width: "100%" }}
              />
              <button className="primary-btn" onClick={() => handleResolve(a.id)}>Mark resolved</button>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
