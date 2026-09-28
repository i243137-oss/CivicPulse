/**
 * Complaint Detail View — displays full complaint information,
 * metadata, AI triage outcomes, and backend-governed status transition actions.
 */

import { useCallback, useEffect, useState } from "react";
import { getComplaint, updateComplaintStatus, ApiError } from "../api/client";
import type { Complaint } from "../types/complaint";
import {
  CATEGORY_LABELS,
  PRIORITY_LABELS,
  STATUS_LABELS,
  Status,
} from "../types/complaint";
import { Badge } from "../components/Badge";
import { LoadingSpinner } from "../components/LoadingSpinner";

interface Props {
  complaintId: string;
  onBack: () => void;
}

export function ComplaintDetailPage({ complaintId, onBack }: Props) {
  const [complaint, setComplaint] = useState<Complaint | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionErr, setActionErr] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [updatingStatus, setUpdatingStatus] = useState<Status | null>(null);

  const fetchDetails = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getComplaint(complaintId);
      setComplaint(data);
    } catch (err) {
      if (err instanceof ApiError)
        setError(`Failed to load issue: ${err.message}`);
      else setError("Network error: unable to load issue details.");
    } finally {
      setLoading(false);
    }
  }, [complaintId]);

  useEffect(() => {
    void fetchDetails();
  }, [fetchDetails]);

  const handleTransition = async (target: Status) => {
    if (!complaint || updatingStatus !== null) return;
    setActionErr(null);
    setActionSuccess(null);
    setUpdatingStatus(target);
    try {
      const updated = await updateComplaintStatus(complaint.id, {
        status: target,
      });
      setComplaint(updated);
      setActionSuccess(`Status transitioned to ${STATUS_LABELS[target]}.`);
    } catch (err) {
      if (err instanceof ApiError) setActionErr(err.message);
      else setActionErr("Status update failed.");
    } finally {
      setUpdatingStatus(null);
    }
  };

  if (loading) return <LoadingSpinner message="Loading complaint details…" />;

  if (error || !complaint) {
    return (
      <div className="error-card">
        <h2>⚠️ Error</h2>
        <p>{error ?? "Complaint not found."}</p>
        <button type="button" className="btn btn--outline" onClick={onBack}>
          ← Back to Complaints
        </button>
      </div>
    );
  }

  // Allowed transitions are decided strictly by backend and delivered on the complaint object
  const allowedTransitions = complaint.allowed_transitions || [];

  return (
    <div className="detail-page">
      <div className="detail-page__nav">
        <button
          type="button"
          className="btn btn--outline btn--sm"
          onClick={onBack}
        >
          ← Back to Complaints
        </button>
      </div>

      {actionErr && (
        <div className="error-banner">
          <span>{actionErr}</span>
          <button type="button" onClick={() => setActionErr(null)}>
            ×
          </button>
        </div>
      )}

      {actionSuccess && (
        <div className="success-banner">
          <span>{actionSuccess}</span>
          <button type="button" onClick={() => setActionSuccess(null)}>
            ×
          </button>
        </div>
      )}

      <div className="detail-card">
        <div className="detail-card__header">
          <div>
            <span className="detail-card__id">Issue #{complaint.id}</span>
            <div className="detail-card__badges">
              <Badge
                label={CATEGORY_LABELS[complaint.category]}
                variant="category"
                value={complaint.category}
              />
              <Badge
                label={PRIORITY_LABELS[complaint.priority]}
                variant="priority"
                value={complaint.priority}
              />
              <Badge
                label={STATUS_LABELS[complaint.status]}
                variant="status"
                value={complaint.status}
              />
            </div>
          </div>
          <div className="detail-card__timestamps">
            <p>Created: {new Date(complaint.created_at).toLocaleString()}</p>
            <p>Updated: {new Date(complaint.updated_at).toLocaleString()}</p>
          </div>
        </div>

        <section className="detail-card__section">
          <h3>Issue Description</h3>
          <p className="detail-card__description">{complaint.text}</p>
        </section>

        <section className="detail-card__section">
          <h3>Location & Reporter</h3>
          <p>
            <strong>📍 Location:</strong> {complaint.location}
          </p>
          <p>
            <strong>👤 Reporter Contact:</strong>{" "}
            {complaint.reporter_contact || "Anonymous"}
          </p>
        </section>

        {(complaint.ai_summary || complaint.triaged_by) && (
          <section className="detail-card__section detail-card__ai">
            <h3>🤖 AI Triage & Telemetry</h3>
            {complaint.ai_summary && (
              <p>
                <strong>Summary:</strong> {complaint.ai_summary}
              </p>
            )}
            <p>
              <strong>Triaged by:</strong> {complaint.triaged_by ?? "N/A"}
            </p>
            {complaint.triage_latency_ms !== null && (
              <p>
                <strong>Latency:</strong> {complaint.triage_latency_ms} ms
              </p>
            )}
          </section>
        )}

        <section className="detail-card__section detail-card__actions">
          <h3>Workflow Actions</h3>
          {allowedTransitions.length === 0 ? (
            <p className="text-muted">
              Terminal status ({STATUS_LABELS[complaint.status]}). No further
              status changes permitted.
            </p>
          ) : (
            <div className="detail-actions__buttons">
              {allowedTransitions.map((target) => (
                <button
                  key={target}
                  type="button"
                  className={`btn btn--transition btn--transition-${target}`}
                  disabled={updatingStatus !== null}
                  onClick={() => handleTransition(target)}
                >
                  {updatingStatus === target
                    ? "Updating…"
                    : `Mark as ${STATUS_LABELS[target]}`}
                </button>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
