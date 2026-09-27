/**
 * CivicPulse — top-level error boundary.
 *
 * Catches unhandled render errors anywhere in the component tree and
 * displays a user-friendly fallback UI instead of a white screen.
 *
 * React error boundaries must be class components — there is no hook
 * equivalent for componentDidCatch / getDerivedStateFromError as of
 * React 18.
 */

import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryProps {
  /** Optional custom fallback UI. Receives the error for display. */
  fallback?: (error: Error, reset: () => void) => ReactNode;
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Log to console; a real production setup would forward to an
    // observability service (e.g. Sentry). Structured logging integration
    // is deferred to Phase 8.
    console.error("[ErrorBoundary] Uncaught render error:", error, info);
  }

  private handleReset = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    const { hasError, error } = this.state;
    const { children, fallback } = this.props;

    if (hasError && error) {
      // Use custom fallback if provided, otherwise the default card.
      if (fallback) {
        return fallback(error, this.handleReset);
      }

      return (
        <div className="error-boundary">
          <div className="error-boundary__card">
            <h1>Something went wrong</h1>
            <p>
              An unexpected error occurred. You can try reloading the page or
              resetting the application state.
            </p>
            <pre>{error.message}</pre>
            <button type="button" onClick={this.handleReset}>
              Try Again
            </button>
          </div>
        </div>
      );
    }

    return children;
  }
}
