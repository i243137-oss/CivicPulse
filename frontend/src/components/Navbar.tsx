/**
 * Navigation bar with tab-based routing.
 */

export type AppView = "dashboard" | "complaints" | "submit" | "detail";

interface NavbarProps {
  current: AppView;
  onNavigate: (view: AppView) => void;
}

export function Navbar({ current, onNavigate }: NavbarProps) {
  const tabs: { view: AppView; label: string; icon: string }[] = [
    { view: "dashboard", label: "Dashboard", icon: "📊" },
    { view: "complaints", label: "Complaints", icon: "📋" },
    { view: "submit", label: "Report Issue", icon: "📝" },
  ];

  return (
    <nav className="navbar">
      <div className="navbar__brand" onClick={() => onNavigate("dashboard")}>
        🏛️ CivicPulse
      </div>
      <div className="navbar__tabs">
        {tabs.map((tab) => (
          <button
            key={tab.view}
            className={`navbar__tab ${current === tab.view ? "navbar__tab--active" : ""}`}
            onClick={() => onNavigate(tab.view)}
          >
            <span className="navbar__tab-icon">{tab.icon}</span>
            <span className="navbar__tab-label">{tab.label}</span>
          </button>
        ))}
      </div>
    </nav>
  );
}
