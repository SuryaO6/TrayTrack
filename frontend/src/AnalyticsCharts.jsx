import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { getAnalytics } from "./api";

function ChartBlock({ title, chartData, complaints }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="analytics-block">
      <h3>{title}</h3>

      {chartData.length === 0 ? (
        <p className="hint">No complaints in this period.</p>
      ) : (
        <div style={{ width: "100%", height: 240 }}>
          <ResponsiveContainer>
            <BarChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#DADCD6" />
              <XAxis dataKey="category" tick={{ fontSize: 11 }} interval={0} angle={-20} textAnchor="end" height={60} />
              <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="count" fill="#3F6259" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <button className="link-btn" onClick={() => setExpanded(!expanded)} style={{ marginTop: 8 }}>
        {expanded ? "Hide" : "Show"} complaint descriptions ({complaints.length})
      </button>

      {expanded && (
        <div style={{ marginTop: 10 }}>
          {complaints.length === 0 && <p className="hint">Nothing to show.</p>}
          {complaints.map((c) => (
            <div key={c.id} className="complaint-desc-row">
              <div className="report-card-head">
                <strong>{c.mess_name} — {c.category}</strong>
                <span className="hint">{c.created_at}</span>
              </div>
              <p>{c.description || <span className="hint">(no description provided)</span>}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function AnalyticsCharts({ collegeId }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    if (!collegeId) return;
    getAnalytics(collegeId).then(setData);
    // auto-refresh every 60s so the dashboard stays live without manual upkeep
    const interval = setInterval(() => getAnalytics(collegeId).then(setData), 60000);
    return () => clearInterval(interval);
  }, [collegeId]);

  if (!data) return <p className="hint">Loading analytics…</p>;

  return (
    <div className="analytics-grid">
      <ChartBlock title="This week" chartData={data.weekly_chart} complaints={data.weekly_complaints} />
      <ChartBlock title="This month" chartData={data.monthly_chart} complaints={data.monthly_complaints} />
    </div>
  );
}
