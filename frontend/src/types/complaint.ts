/**
 * CivicPulse — TypeScript types matching the FastAPI backend schemas.
 *
 * Derived from backend/app/schemas/complaint.py and backend/app/models/complaint.py.
 * These types are the single frontend source of truth for API data shapes.
 */

// ─── Enums ─────────────────────────────────────────────────────

export enum Category {
  WATER = "water",
  ELECTRICITY = "electricity",
  SANITATION = "sanitation",
  ROADS = "roads",
  STREETLIGHTS = "streetlights",
  OTHER = "other",
}

export enum Priority {
  HIGH = "high",
  NORMAL = "normal",
  LOW = "low",
}

export enum Status {
  OPEN = "open",
  IN_PROGRESS = "in_progress",
  RESOLVED = "resolved",
  REJECTED = "rejected",
}

/** Valid state transitions from the backend state machine. */
export const VALID_TRANSITIONS: Record<Status, Status[]> = {
  [Status.OPEN]: [Status.IN_PROGRESS, Status.REJECTED],
  [Status.IN_PROGRESS]: [Status.RESOLVED, Status.REJECTED],
  [Status.RESOLVED]: [],
  [Status.REJECTED]: [],
};

// ─── Request schemas ───────────────────────────────────────────

export interface ComplaintCreate {
  text: string;
  location: string;
  reporter_contact?: string | null;
  category?: Category | null;
  priority?: Priority | null;
}

export interface ComplaintStatusUpdate {
  status: Status;
}

// ─── Response schemas ──────────────────────────────────────────

export interface Complaint {
  id: string;
  text: string;
  location: string;
  reporter_contact: string | null;
  category: Category;
  priority: Priority;
  status: Status;
  ai_summary: string | null;
  triaged_by: string | null;
  triage_latency_ms: number | null;
  created_at: string;
  updated_at: string;
}

export interface ComplaintListResponse {
  items: Complaint[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ComplaintStatsResponse {
  total: number;
  by_status: Record<string, number>;
  by_category: Record<string, number>;
  by_priority: Record<string, number>;
}

// ─── Meta / provider responses ─────────────────────────────────

export interface CacheMetrics {
  hits: number;
  misses: number;
  total_requests: number;
  hit_rate: number;
}

export interface ProviderInfoResponse {
  active_provider: string;
  cache_metrics: CacheMetrics;
  recent_outcomes: TriageOutcome[];
}

export interface TriageOutcome {
  provider: string;
  latency_ms: number;
  fallback: boolean;
  [key: string]: unknown;
}

// ─── Filter parameters ─────────────────────────────────────────

export interface ComplaintFilters {
  category?: Category | null;
  priority?: Priority | null;
  status?: Status | null;
  page?: number;
  page_size?: number;
}

// ─── API error shape ───────────────────────────────────────────

export interface ApiErrorDetail {
  detail:
    | string
    | { message: string; current_status: string; target_status: string }
    | { detail: Array<{ loc: string[]; msg: string; type: string }> };
}

// ─── Enum display helpers ──────────────────────────────────────

export const CATEGORY_LABELS: Record<Category, string> = {
  [Category.WATER]: "Water",
  [Category.ELECTRICITY]: "Electricity",
  [Category.SANITATION]: "Sanitation",
  [Category.ROADS]: "Roads",
  [Category.STREETLIGHTS]: "Streetlights",
  [Category.OTHER]: "Other",
};

export const PRIORITY_LABELS: Record<Priority, string> = {
  [Priority.HIGH]: "High",
  [Priority.NORMAL]: "Normal",
  [Priority.LOW]: "Low",
};

export const STATUS_LABELS: Record<Status, string> = {
  [Status.OPEN]: "Open",
  [Status.IN_PROGRESS]: "In Progress",
  [Status.RESOLVED]: "Resolved",
  [Status.REJECTED]: "Rejected",
};
