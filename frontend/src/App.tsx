/**
 * CivicPulse frontend — root application component.
 *
 * Implements lightweight hash/state-based routing across:
 * - Dashboard (metrics, triage telemetry, cache stats)
 * - Complaints (filterable, paginated listing with workflow transitions)
 * - Complaint Detail (single issue inspection with AI summary)
 * - Submit (reporting intake form with client validation)
 */

import { useState } from "react";
import "./App.css";
import { Navbar, type AppView } from "./components/Navbar";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { DashboardPage } from "./pages/DashboardPage";
import { ComplaintsPage } from "./pages/ComplaintsPage";
import { ComplaintDetailPage } from "./pages/ComplaintDetailPage";
import { SubmitPage } from "./pages/SubmitPage";

function App() {
  const [currentView, setCurrentView] = useState<AppView>("dashboard");
  const [selectedComplaintId, setSelectedComplaintId] = useState<string | null>(
    null,
  );

  const handleNavigate = (view: AppView) => {
    setCurrentView(view);
    if (view !== "detail") {
      setSelectedComplaintId(null);
    }
  };

  const handleViewDetail = (id: string) => {
    setSelectedComplaintId(id);
    setCurrentView("detail");
  };

  const handleSubmitted = (id: string) => {
    setSelectedComplaintId(id);
    setCurrentView("detail");
  };

  return (
    <ErrorBoundary>
      <div className="app">
        <header className="app-header">
          <div className="app-header__inner">
            <Navbar current={currentView} onNavigate={handleNavigate} />
          </div>
        </header>

        <main className="app-main">
          {currentView === "dashboard" && <DashboardPage />}

          {currentView === "complaints" && (
            <ComplaintsPage onViewDetail={handleViewDetail} />
          )}

          {currentView === "submit" && (
            <SubmitPage onSubmitted={handleSubmitted} />
          )}

          {currentView === "detail" && selectedComplaintId && (
            <ComplaintDetailPage
              complaintId={selectedComplaintId}
              onBack={() => handleNavigate("complaints")}
            />
          )}
        </main>

        <footer className="app-footer">
          <p>
            &copy; {new Date().getFullYear()} CivicPulse &mdash; CS4032 Software
            Construction and Design
          </p>
        </footer>
      </div>
    </ErrorBoundary>
  );
}

export default App;
