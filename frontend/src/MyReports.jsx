import { useEffect, useState } from "react";
import { getMyComplaints, resolveMyAlert } from "./api";

const LEVEL_COLOR = { Low: "🟢", Medium: "🟡", High: "🔴" };

function hoursUntilEligible(lastEscalatedAt) {
  const then = new Date(lastEscalatedAt.replace(" ", "T") + "Z");
  const eligibleAt = new Date(then.getTime() + 2 * 24 * 60 * 60 * 1000);
  const now = new Date();
  return Math.max(Math.ceil((eligibleAt - now) / (1000 * 60 * 60)), 0);
}

export default function MyReports() {
  const [complaints, setComplaints] = useState(null);
  const [error, setError] = useState("");

  function load() {
    getMyComplaints().then(setComplaints).catch(() => setError("Couldn't load your reports."));
  }

  useEffect(load, []);

  async function handleResolve(alertId) {
    try {
      await resolveMyAlert(alertId);
      load();
    } catch (err) {
      alert(err.message);
    }
  }

  if (error) return <div className="content"><div className="banner error">{error}</div></div>;
  if (!complaints) return <div className="content">Loading…</div>;

  return (
    <div className="content">
      <h1>My reports</h1>
      <p className="subtitle">Your own complaint history — visible only to you.</p>

      {complaints.length === 0 && (
        <div className="banner info">You haven't submitted any reports yet.</div>
      )}

      {complaints.map((c) => (
        <div key={c.id} className="report-card">
          <div className="report-card-head">
            <strong>{c.mess_name}</strong>
            <span className="hint">{c.created_at}</span>
          </div>
          <div className="hint">{c.category}</div>
          {c.description && <p>{c.description}</p>}

          {!c.alert && (
            <div className="banner info" style={{ marginTop: 12 }}>
              Recorded — not yet part of a confirmed pattern.
            </div>
          )}

          {c.alert && !c.alert.resolved && (
            <div className="banner info" style={{ marginTop: 12 }}>
              <strong>{LEVEL_COLOR[c.alert.level]} Active alert ({c.alert.level})</strong>
              <p>{c.alert.reason}</p>
              {hoursUntilEligible(c.alert.last_escalated_at) === 0 ? (
                <button className="primary-btn" style={{ marginTop: 10 }} onClick={() => handleResolve(c.alert.id)}>
                  ✅ Mark as Resolved
                </button>
              ) : (
                <p className="hint">
                  You can mark this resolved in about {hoursUntilEligible(c.alert.last_escalated_at)} hour(s).
                </p>
              )}
            </div>
          )}

          {c.alert && c.alert.resolved && (
            <div className="banner success" style={{ marginTop: 12 }}>
              Resolved on {c.alert.resolved_at}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
