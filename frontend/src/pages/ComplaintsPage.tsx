/**
 * Complaints listing page — paginated, filterable, with backend-governed status transitions.
 */
import { useEffect, useState } from "react";
import { listComplaints, updateComplaintStatus, ApiError } from "../api/client";
import type { Complaint, ComplaintFilters } from "../types/complaint";
import {
  Category,
  Priority,
  Status,
  CATEGORY_LABELS,
  PRIORITY_LABELS,
  STATUS_LABELS,
} from "../types/complaint";
import { Badge } from "../components/Badge";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { EmptyState } from "../components/EmptyState";
import { Pagination } from "../components/Pagination";

interface Props {
  onViewDetail: (id: string) => void;
}

export function ComplaintsPage({ onViewDetail }: Props) {
  const [items, setItems] = useState<Complaint[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [filters, setFilters] = useState<ComplaintFilters>({
    page: 1,
    page_size: 10,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionErr, setActionErr] = useState<string | null>(null);
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [reloadTrigger, setReloadTrigger] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    listComplaints(filters, controller.signal)
      .then((res) => {
        setItems(res.items);
        setTotal(res.total);
        setTotalPages(res.total_pages);
        setLoading(false);
      })
      .catch((e) => {
        if (e instanceof Error && e.name === "AbortError") {
          return; // Ignore stale aborted requests
        }
        setError(
          e instanceof ApiError ? e.message : "Failed to load complaints.",
        );
        setLoading(false);
      });

    return () => {
      controller.abort();
    };
  }, [filters, reloadTrigger]);

  const handleTransition = async (id: string, target: Status) => {
    setActionErr(null);
    setUpdatingId(id);
    try {
      const updated = await updateComplaintStatus(id, { status: target });
      setItems((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
    } catch (e) {
      if (e instanceof ApiError) setActionErr(e.message);
      else setActionErr("Status update failed.");
    } finally {
      setUpdatingId(null);
    }
  };

  const updateFilter = (key: keyof ComplaintFilters, val: string) => {
    setFilters((f) => ({ ...f, [key]: val || null, page: 1 }));
  };

  return (
    <div className="complaints-page">
      <h2>📋 Complaints ({total})</h2>
      {actionErr && (
        <div className="error-banner">
          <span>{actionErr}</span>
          <button type="button" onClick={() => setActionErr(null)}>
            ×
          </button>
        </div>
      )}
      <div className="filters">
        <select
          value={filters.category ?? ""}
          onChange={(e) => updateFilter("category", e.target.value)}
        >
          <option value="">All Categories</option>
          {Object.values(Category).map((c) => (
            <option key={c} value={c}>
              {CATEGORY_LABELS[c]}
            </option>
          ))}
        </select>
        <select
          value={filters.priority ?? ""}
          onChange={(e) => updateFilter("priority", e.target.value)}
        >
          <option value="">All Priorities</option>
          {Object.values(Priority).map((p) => (
            <option key={p} value={p}>
              {PRIORITY_LABELS[p]}
            </option>
          ))}
        </select>
        <select
          value={filters.status ?? ""}
          onChange={(e) => updateFilter("status", e.target.value)}
        >
          <option value="">All Statuses</option>
          {Object.values(Status).map((s) => (
            <option key={s} value={s}>
              {STATUS_LABELS[s]}
            </option>
          ))}
        </select>
      </div>

      {loading ? (
        <LoadingSpinner />
      ) : error ? (
        <div className="error-card">
          <p>{error}</p>
          <button
            type="button"
            className="btn btn--primary"
            onClick={() => setReloadTrigger((r) => r + 1)}
          >
            Retry
          </button>
        </div>
      ) : items.length === 0 ? (
        <EmptyState message="No complaints match your filters." />
      ) : (
        <>
          <div className="complaint-list">
            {items.map((c) => (
              <ComplaintRow
                key={c.id}
                complaint={c}
                isUpdating={updatingId === c.id}
                onView={onViewDetail}
                onTransition={handleTransition}
              />
            ))}
          </div>
          <Pagination
            page={filters.page ?? 1}
            totalPages={totalPages}
            onPageChange={(p) => setFilters((f) => ({ ...f, page: p }))}
          />
        </>
      )}
    </div>
  );
}

interface ComplaintRowProps {
  complaint: Complaint;
  isUpdating: boolean;
  onView: (id: string) => void;
  onTransition: (id: string, target: Status) => void;
}

function ComplaintRow({
  complaint,
  isUpdating,
  onView,
  onTransition,
}: ComplaintRowProps) {
  // Allowed transitions are provided directly by the backend response
  const allowed = complaint.allowed_transitions || [];

  return (
    <div className="complaint-card">
      <div className="complaint-card__header">
        <span
          className="complaint-card__id"
          onClick={() => onView(complaint.id)}
        >
          #{complaint.id.slice(0, 8)}
        </span>
        <div className="complaint-card__badges">
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

      <p className="complaint-card__text">{complaint.text}</p>

      {complaint.ai_summary && (
        <div className="complaint-card__summary">
          <strong>AI Summary:</strong> {complaint.ai_summary}
        </div>
      )}

      <div className="complaint-card__footer">
        <span className="complaint-card__location">
          📍 {complaint.location}
        </span>
        <span className="complaint-card__date">
          {new Date(complaint.created_at).toLocaleDateString()}
        </span>
      </div>

      <div className="complaint-card__actions">
        <button
          type="button"
          className="btn btn--sm btn--outline"
          onClick={() => onView(complaint.id)}
        >
          View Details
        </button>

        {allowed.map((target) => (
          <button
            key={target}
            type="button"
            className={`btn btn--sm btn--transition btn--transition-${target}`}
            disabled={isUpdating}
            onClick={() => onTransition(complaint.id, target)}
          >
            {isUpdating ? "Updating…" : `Mark ${STATUS_LABELS[target]}`}
          </button>
        ))}
      </div>
    </div>
  );
}
