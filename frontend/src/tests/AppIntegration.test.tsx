import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";
import * as apiClient from "../api/client";
import {
  Category,
  Priority,
  Status,
  type Complaint,
  type ComplaintListResponse,
  type ComplaintStatsResponse,
} from "../types/complaint";

describe("App End-to-End Application Integration Path", () => {
  const mockCreatedComplaint: Complaint = {
    id: "app-e2e-1234",
    text: "Exposed high voltage electrical wire sagging over playground path",
    location: "Community Park, Sector F-8/2",
    reporter_contact: "0300-9876543",
    category: Category.ELECTRICITY,
    priority: Priority.HIGH,
    status: Status.OPEN,
    ai_summary: "Dangerous low-hanging live wire over public playground path",
    triaged_by: "rules",
    triage_latency_ms: 32,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    allowed_transitions: [Status.IN_PROGRESS, Status.REJECTED],
  };

  const mockComplaintsListResponse: ComplaintListResponse = {
    items: [mockCreatedComplaint],
    total: 1,
    page: 1,
    page_size: 10,
    total_pages: 1,
  };

  const mockStatsResponse: {
    stats: ComplaintStatsResponse;
    cacheStatus: "HIT" | "MISS" | "UNKNOWN";
  } = {
    stats: {
      total: 1,
      by_status: { open: 1, in_progress: 0, resolved: 0, rejected: 0 },
      by_category: {
        electricity: 1,
        roads: 0,
        water: 0,
        sanitation: 0,
        streetlights: 0,
        other: 0,
      },
      by_priority: { high: 1, normal: 0, low: 0 },
    },
    cacheStatus: "MISS",
  };

  const mockProviderInfo = {
    active_provider: "rules",
    cache_metrics: {
      hits: 0,
      misses: 1,
      total_requests: 1,
      hit_rate: 0.0,
    },
    recent_outcomes: [],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(apiClient, "getStats").mockResolvedValue(mockStatsResponse);
    vi.spyOn(apiClient, "getProvidersMeta").mockResolvedValue(mockProviderInfo);
    vi.spyOn(apiClient, "listComplaints").mockResolvedValue(mockComplaintsListResponse);
    vi.spyOn(apiClient, "getComplaint").mockResolvedValue(mockCreatedComplaint);
    vi.spyOn(apiClient, "createComplaint").mockResolvedValue(mockCreatedComplaint);
    vi.spyOn(apiClient, "updateComplaintStatus").mockResolvedValue({
      ...mockCreatedComplaint,
      status: Status.IN_PROGRESS,
      allowed_transitions: [Status.RESOLVED, Status.REJECTED],
    });
  });

  it("completes full user journey: intake -> automated triage -> detail inspection -> status transition", async () => {
    const user = userEvent.setup({ delay: null });

    render(<App />);

    // 1. Initial view: Dashboard is loaded
    await waitFor(() => {
      expect(screen.getByText(/Total Complaints/i)).toBeInTheDocument();
      expect(screen.getByText(/X-Cache: MISS/i)).toBeInTheDocument();
    });

    // 2. Navigate to Submit view via Navbar
    const reportNavBtn = screen.getByRole("button", { name: /report issue/i });
    await user.click(reportNavBtn);

    expect(screen.getByRole("heading", { name: /report a civic issue/i })).toBeInTheDocument();

    // 3. Complete intake form
    const descInput = screen.getByLabelText(/description/i);
    const locInput = screen.getByLabelText(/location/i);
    const contactInput = screen.getByLabelText(/reporter contact/i);

    await user.type(descInput, "Exposed high voltage electrical wire sagging over playground path");
    await user.type(locInput, "Community Park, Sector F-8/2");
    await user.type(contactInput, "0300-9876543");

    const submitBtn = screen.getByRole("button", { name: /submit issue/i });
    await user.click(submitBtn);

    // 4. Form automatically transitions to Complaint Detail view
    await waitFor(() => {
      expect(screen.getByText(/Issue #app-e2e-1234/i)).toBeInTheDocument();
      expect(screen.getByText(/Dangerous low-hanging live wire over public playground path/i)).toBeInTheDocument();
      expect(screen.getByText(/rules/i)).toBeInTheDocument();
      expect(screen.getByText(/32 ms/i)).toBeInTheDocument();
    });

    // 5. Operator advances state machine using server-provided allowed_transitions
    const startProgressBtn = screen.getByRole("button", {
      name: /mark as in progress/i,
    });
    expect(startProgressBtn).toBeInTheDocument();

    await user.click(startProgressBtn);

    await waitFor(() => {
      expect(screen.getByText(/Status transitioned to In Progress/i)).toBeInTheDocument();
    });

    // 6. Navigate back to Complaints list
    const backBtn = screen.getByRole("button", { name: /← back to complaints/i });
    await user.click(backBtn);

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /complaints/i }),
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          /Exposed high voltage electrical wire sagging over playground path/i,
        ),
      ).toBeInTheDocument();
    });
  });
});
