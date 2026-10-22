import { useState } from "react";
import { GoogleOAuthProvider } from "@react-oauth/google";
import Login from "./Login";
import SubmitComplaint from "./SubmitComplaint";
import MyReports from "./MyReports";
import PublicDashboard from "./PublicDashboard";
import HistoryTrends from "./HistoryTrends";
import InspectorEntry from "./InspectorEntry";
import AdminPanel from "./AdminPanel";

const GOOGLE_CLIENT_ID = "792887341773-el82aas0ddnbdf0us57ctq9v1i9ka1bt.apps.googleusercontent.com";

const TABS = [
  { id: "dashboard", label: "📊 Dashboard" },
  { id: "submit", label: "📝 Submit a Complaint" },
  { id: "my-reports", label: "🗂️ My Reports" },
  { id: "history", label: "📈 History & Trends" },
  { id: "inspector", label: "🔍 Inspector Entry" },
  { id: "admin", label: "🔐 Admin Panel" },
];

function AppShell() {
  const [userEmail, setUserEmail] = useState(
    localStorage.getItem("user_token") ? localStorage.getItem("user_email") : null
  );
  const [tab, setTab] = useState("dashboard");

  function handleLogout() {
    localStorage.removeItem("user_email");
    localStorage.removeItem("user_name");
    localStorage.removeItem("user_token");
    setUserEmail(null);
  }

  function renderTab() {
    switch (tab) {
      case "dashboard":
        return <PublicDashboard />;
      case "submit":
        return userEmail
          ? <SubmitComplaint userEmail={userEmail} onLogout={handleLogout} embedded />
          : <Login onLoggedIn={setUserEmail} embedded />;
      case "my-reports":
        return userEmail ? <MyReports /> : <Login onLoggedIn={setUserEmail} embedded />;
      case "history":
        return <HistoryTrends />;
      case "inspector":
        return <InspectorEntry />;
      case "admin":
        return <AdminPanel />;
      default:
        return null;
    }
  }

  return (
    <div className="page">
      <header className="topbar">
        <div className="brand-mark small">🍽️ TrayTrack</div>
        <nav className="nav-row">
          {TABS.map((t) => (
            <button
              key={t.id}
              className={`nav-btn ${tab === t.id ? "active" : ""}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
        {userEmail && (
          <div className="user-chip">
            <span>{userEmail}</span>
            <button className="link-btn" onClick={handleLogout}>Log out</button>
          </div>
        )}
      </header>

      {renderTab()}
    </div>
  );
}

export default function App() {
  return (
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
      <AppShell />
    </GoogleOAuthProvider>
  );
}
