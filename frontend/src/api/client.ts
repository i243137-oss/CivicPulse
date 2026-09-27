/**
 * CivicPulse — centralized, typed API client.
 *
 * All backend communication flows through this module. Uses relative `/api/`
 * paths so that:
 *   - In development, Vite's proxy forwards /api → http://localhost:8000
 *   - In production, nginx proxies /api → backend service
 * This means the frontend never hard-codes localhost or any backend URL.
 *
 * No secrets or API keys are ever placed in frontend code.
 */

import type {
  Complaint,
  ComplaintCreate,
  ComplaintFilters,
  ComplaintListResponse,
  ComplaintStatsResponse,
  ComplaintStatusUpdate,
  ProviderInfoResponse,
} from "../types/complaint";

// ─── Error class ───────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    public body: unknown
  ) {
    const msg =
      typeof body === "object" && body !== null && "detail" in body
        ? JSON.stringify((body as { detail: unknown }).detail)
        : `${status} ${statusText}`;
    super(msg);
    this.name = "ApiError";
  }
}

// ─── Internal helpers ──────────────────────────────────────────

const BASE = "/api";

async function request<T>(
  path: string,
  init?: RequestInit
): Promise<{ data: T; headers: Headers }> {
  const url = `${BASE}${path}`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });

  if (!res.ok) {
    let body: unknown;
    try {
      body = await res.json();
    } catch {
      body = await res.text();
    }
    throw new ApiError(res.status, res.statusText, body);
  }

  const data: T = await res.json();
  return { data, headers: res.headers };
}

// ─── Complaints ────────────────────────────────────────────────

export async function createComplaint(
  payload: ComplaintCreate
): Promise<Complaint> {
  const { data } = await request<Complaint>("/complaints", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return data;
}

export async function getComplaint(id: string): Promise<Complaint> {
  const { data } = await request<Complaint>(`/complaints/${id}`);
  return data;
}

export async function listComplaints(
  filters: ComplaintFilters = {}
): Promise<ComplaintListResponse> {
  const params = new URLSearchParams();
  if (filters.category) params.set("category", filters.category);
  if (filters.priority) params.set("priority", filters.priority);
  if (filters.status) params.set("status", filters.status);
  if (filters.page) params.set("page", String(filters.page));
  if (filters.page_size) params.set("page_size", String(filters.page_size));

  const qs = params.toString();
  const { data } = await request<ComplaintListResponse>(
    `/complaints${qs ? `?${qs}` : ""}`
  );
  return data;
}

export async function updateComplaintStatus(
  id: string,
  payload: ComplaintStatusUpdate
): Promise<Complaint> {
  const { data } = await request<Complaint>(`/complaints/${id}/status`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  return data;
}

// ─── Stats ─────────────────────────────────────────────────────

export interface StatsResult {
  stats: ComplaintStatsResponse;
  cacheStatus: "HIT" | "MISS" | "UNKNOWN";
}

export async function getStats(): Promise<StatsResult> {
  const { data, headers } = await request<ComplaintStatsResponse>("/stats");
  const xCache = headers.get("X-Cache");
  const cacheStatus: StatsResult["cacheStatus"] =
    xCache === "HIT" ? "HIT" : xCache === "MISS" ? "MISS" : "UNKNOWN";
  return { stats: data, cacheStatus };
}

// ─── Meta / providers ──────────────────────────────────────────

export async function getProvidersMeta(): Promise<ProviderInfoResponse> {
  const { data } = await request<ProviderInfoResponse>("/meta/providers");
  return data;
}

// ─── Health ────────────────────────────────────────────────────

export async function getHealth(): Promise<{ status: string }> {
  const { data } = await request<{ status: string }>("/health".replace("/api", ""));
  // Health is at /health not /api/health — use absolute fetch
  return data;
}
