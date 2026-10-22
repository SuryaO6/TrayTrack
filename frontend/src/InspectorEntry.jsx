import { useEffect, useState } from "react";
import { adminLogin, getColleges, getMessHalls, getChecklist, submitInspection } from "./api";

export default function InspectorEntry() {
  const [authed, setAuthed] = useState(!!sessionStorage.getItem("admin_token"));
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState("");

  const [colleges, setColleges] = useState([]);
  const [collegeId, setCollegeId] = useState("");
  const [messHalls, setMessHalls] = useState([]);
  const [messId, setMessId] = useState("");
  const [inspectorName, setInspectorName] = useState("");
  const [checklist, setChecklist] = useState([]);
  const [responses, setResponses] = useState({});
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  async function handleLogin(e) {
    e.preventDefault();
    try {
      await adminLogin(password);
      setAuthed(true);
    } catch (err) {
      setLoginError(err.message);
    }
  }

  useEffect(() => {
    if (!authed) return;
    getColleges().then((cs) => { setColleges(cs); if (cs.length) setCollegeId(cs[0].id); });
    getChecklist().then((items) => {
      setChecklist(items);
      const initial = {};
      items.forEach((i) => { initial[i.id] = true; });
      setResponses(initial);
    });
  }, [authed]);

  useEffect(() => {
    if (collegeId) getMessHalls(collegeId).then(setMessHalls);
  }, [collegeId]);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(""); setResult(null);
    if (!inspectorName.trim() || !messId) {
      setError("Inspector name and mess hall are required.");
      return;
    }
    try {
      const res = await submitInspection({ mess_id: Number(messId), inspector_name: inspectorName, responses });
      setResult(res);
    } catch (err) {
      setError(err.message);
    }
  }

  if (!authed) {
    return (
      <div className="content">
        <h1>Inspector entry</h1>
        <form onSubmit={handleLogin} className="form-card">
          <label>
            Inspector password
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </label>
          {loginError && <div className="banner error">{loginError}</div>}
          <button className="primary-btn" type="submit">Log in</button>
        </form>
      </div>
    );
  }

  return (
    <div className="content">
      <h1>🔍 Inspector checklist entry</h1>
      <form onSubmit={handleSubmit} className="form-card">
        <label>
          College
          <select value={collegeId} onChange={(e) => setCollegeId(Number(e.target.value))}>
            {colleges.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </label>
        <label>
          Mess hall
          <select value={messId} onChange={(e) => setMessId(e.target.value)}>
            <option value="" disabled>Select a mess hall</option>
            {messHalls.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
        </label>
        <label>
          Inspector name
          <input value={inspectorName} onChange={(e) => setInspectorName(e.target.value)} />
        </label>

        <div>
          <p className="hint">Items marked ⚠️ Critical automatically trigger a High alert if failed.</p>
          {checklist.map((item) => (
            <label key={item.id} className="checkbox-row">
              <input
                type="checkbox"
                checked={!!responses[item.id]}
                onChange={(e) => setResponses({ ...responses, [item.id]: e.target.checked })}
              />
              {item.text}{item.critical && "  ⚠️ Critical"}
            </label>
          ))}
        </div>

        {error && <div className="banner error">{error}</div>}
        <button className="primary-btn" type="submit">Submit inspection</button>
      </form>

      {result && (
        <div className="banner success">
          <strong>Inspection recorded — score {result.score}%. Severity: {result.level}</strong>
          <p>{result.reason}</p>
        </div>
      )}
    </div>
  );
}
