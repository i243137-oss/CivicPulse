import { useState } from "react";
import { createComplaint, ApiError } from "../api/client";
import type { ComplaintCreate } from "../types/complaint";

interface Props {
  onSubmitted: (id: string) => void;
}

export function SubmitPage({ onSubmitted }: Props) {
  const [text, setText] = useState("");
  const [location, setLocation] = useState("");
  const [reporterContact, setReporterContact] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);
    setApiError(null);
    const trimmedText = text.trim();
    const trimmedLoc = location.trim();
    const trimmedContact = reporterContact.trim();

    if (trimmedText.length < 10 || trimmedText.length > 2000) {
      setValidationError("Description must be between 10 and 2000 characters.");
      return;
    }
    if (trimmedLoc.length < 3 || trimmedLoc.length > 200) {
      setValidationError("Location must be between 3 and 200 characters.");
      return;
    }
    if (trimmedContact.length > 255) {
      setValidationError("Contact must not exceed 255 characters.");
      return;
    }

    const payload: ComplaintCreate = {
      text: trimmedText,
      location: trimmedLoc,
      reporter_contact: trimmedContact || undefined,
    };

    setSubmitting(true);
    try {
      const created = await createComplaint(payload);
      onSubmitted(created.id);
    } catch (err) {
      setApiError(
        err instanceof ApiError
          ? err.message
          : "Network error: failed to submit complaint.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="submit-page">
      <h2>📝 Report a Civic Issue</h2>
      <p className="submit-page__subtitle">
        Submit municipal concerns. Automated AI triage will prioritize and
        categorize.
      </p>
      {validationError && (
        <div className="error-banner">
          <span>{validationError}</span>
          <button type="button" onClick={() => setValidationError(null)}>
            ×
          </button>
        </div>
      )}
      {apiError && (
        <div className="error-banner">
          <span>{apiError}</span>
          <button type="button" onClick={() => setApiError(null)}>
            ×
          </button>
        </div>
      )}
      <form className="submit-form" onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="issue-text">
            Description <span className="required">*</span>
          </label>
          <textarea
            id="issue-text"
            rows={5}
            placeholder="Describe the issue in detail (10-2000 chars)..."
            value={text}
            onChange={(e) => setText(e.target.value)}
            required
            minLength={10}
            maxLength={2000}
          />
          <div className="char-count">{text.trim().length} / 2000 (min 10)</div>
        </div>
        <div className="form-group">
          <label htmlFor="issue-location">
            Location <span className="required">*</span>
          </label>
          <input
            id="issue-location"
            type="text"
            placeholder="e.g. Sector F-7/2, Street 12, Islamabad"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            required
            minLength={3}
            maxLength={200}
          />
          <div className="char-count">
            {location.trim().length} / 200 (min 3)
          </div>
        </div>
        <div className="form-group">
          <label htmlFor="reporter-contact">
            Reporter Contact <span className="optional">(optional)</span>
          </label>
          <input
            id="reporter-contact"
            type="text"
            placeholder="Phone number or email"
            value={reporterContact}
            onChange={(e) => setReporterContact(e.target.value)}
            maxLength={255}
          />
        </div>
        <button
          type="submit"
          className="btn btn--primary btn--submit"
          disabled={
            submitting || text.trim().length < 10 || location.trim().length < 3
          }
        >
          {submitting ? "Submitting & Triaging…" : "Submit Issue"}
        </button>
      </form>
    </div>
  );
}
