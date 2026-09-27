/**
 * CivicPulse frontend — application entry point.
 *
 * Mounts the React root into the #root DOM element declared in index.html.
 * Wraps the entire application in React.StrictMode for development
 * diagnostics and the top-level ErrorBoundary for unhandled render errors.
 */

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { ErrorBoundary } from "./components/ErrorBoundary";
import "./index.css";

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error(
    'Root element not found. Ensure index.html contains <div id="root"></div>.'
  );
}

createRoot(rootElement).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>
);
