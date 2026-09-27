import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ComplaintsPage } from "../pages/ComplaintsPage";
import * as apiClient from "../api/client";
import {
  Category,
  Priority,
  Status,
  type ComplaintListResponse,
} from "../types/complaint";

describe("ComplaintsPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const mockListResponse: ComplaintListResponse = {
    items: [
      {
        id: "issue-abc-123",
        text: "Transformer sparking near municipal park entrance",
        location: "F-8/3, Street 19",
        reporter_contact: null,
        category: Category.ELECTRICITY,
        priority: Priority.HIGH,
        status: Status.OPEN,
        allowed_transitions: [Status.IN_PROGRESS, Status.REJECTED],
        ai_summary: "High-voltage electrical hazard",
        triaged_by: "llm:groq:llama-3.3-70b-versatile",
        triage_latency_ms: 850,
        created_at: "2026-09-27T10:00:00Z",
        updated_at: "2026-09-27T10:00:00Z",
      },
    ],
    total: 1,
    page: 1,
    page_size: 10,
    total_pages: 1,
  };

  it("renders complaints list with triage summaries and server-provided status transitions", async () => {
    vi.spyOn(apiClient, "listComplaints").mockResolvedValue(mockListResponse);
    const onViewDetail = vi.fn();

    render(<ComplaintsPage onViewDetail={onViewDetail} />);

    await waitFor(() => {
      expect(
        screen.getByText(/Transformer sparking near municipal park entrance/i),
      ).toBeInTheDocument();
      expect(
        screen.getByText(/High-voltage electrical hazard/i),
      ).toBeInTheDocument();
      expect(screen.getAllByText(/Electricity/i).length).toBeGreaterThanOrEqual(
        1,
      );
      expect(screen.getAllByText(/Open/i).length).toBeGreaterThanOrEqual(1);
      // Valid transition buttons decided by backend
      expect(
        screen.getByRole("button", { name: /mark in progress/i }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /mark rejected/i }),
      ).toBeInTheDocument();
    });
  });

  it("surfaces server 409 conflict error verbatim matching the attempted transition", async () => {
    const user = userEvent.setup({ delay: null });
    vi.spyOn(apiClient, "listComplaints").mockResolvedValue(mockListResponse);
    vi.spyOn(apiClient, "updateComplaintStatus").mockRejectedValue(
      new apiClient.ApiError(409, "Conflict", {
        detail: {
          message: "Invalid status transition from 'open' to 'in_progress'",
          current_status: "open",
          target_status: "in_progress",
        },
      }),
    );

    render(<ComplaintsPage onViewDetail={vi.fn()} />);

    await waitFor(() => {
      expect(
        screen.getByText(/Transformer sparking near municipal park entrance/i),
      ).toBeInTheDocument();
    });

    const markBtn = screen.getByRole("button", { name: /mark in progress/i });
    await user.click(markBtn);

    await waitFor(() => {
      expect(
        screen.getByText(
          /Invalid status transition from 'open' to 'in_progress'/i,
        ),
      ).toBeInTheDocument();
    });
  });

  it("triggers filter update and re-fetches complaints list", async () => {
    const user = userEvent.setup({ delay: null });
    const listSpy = vi
      .spyOn(apiClient, "listComplaints")
      .mockResolvedValue(mockListResponse);

    render(<ComplaintsPage onViewDetail={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText(/All Categories/i)).toBeInTheDocument();
    });

    const categorySelect = screen.getByDisplayValue("All Categories");
    await user.selectOptions(categorySelect, "water");

    await waitFor(() => {
      expect(listSpy).toHaveBeenCalledWith(
        expect.objectContaining({ category: "water", page: 1 }),
        expect.any(AbortSignal),
      );
    });
  });
});
