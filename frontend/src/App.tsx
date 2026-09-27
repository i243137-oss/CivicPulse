/**
 * CivicPulse frontend — root application component.
 *
 * Phase 1 scope only:
 *   - Renders a minimal landing layout confirming the frontend builds and runs.
 *   - Pages, routing, typed API client, and feature components are introduced
 *     in Phase 5.
 */

import "./App.css";

function App() {
  return (
    <div className="app">
      <header className="app-header">
        <h1>🏛️ CivicPulse</h1>
        <p className="app-tagline">
          AI-powered civic issue reporting platform
        </p>
      </header>

      <main className="app-main">
        <section className="app-status">
          <h2>System Status</h2>
          <p>
            Frontend is running. Backend integration, routing, and feature views
            are introduced in Phase 5.
          </p>
        </section>
      </main>

      <footer className="app-footer">
        <p>
          &copy; {new Date().getFullYear()} CivicPulse &mdash; CS4032 Software
          Construction and Design
        </p>
      </footer>
    </div>
  );
}

export default App;
