import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ComplaintDetailPage } from "../pages/ComplaintDetailPage";
import * as apiClient from "../api/client";
import { Category, Priority, Status, type Complaint } from "../types/complaint";

describe("ComplaintDetailPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const mockComplaint: Complaint = {
    id: "f83a00-1122",
    text: "Broken water main leaking clean water into baseline intersection",
    location: "Sector I-8/2, Main Market",
    reporter_contact: "0300-1234567",
    category: Category.WATER,
    priority: Priority.HIGH,
    status: Status.IN_PROGRESS,
    ai_summary: "Major clean water distribution leak",
    triaged_by: "llm:gemini-2.5-flash",
    triage_latency_ms: 1100,
    created_at: "2026-09-27T08:00:00Z",
    updated_at: "2026-09-27T08:30:00Z",
  };

  it("renders full issue detail, reporter information, and AI triage telemetry", async () => {
    vi.spyOn(apiClient, "getComplaint").mockResolvedValue(mockComplaint);
    const onBack = vi.fn();

    render(<ComplaintDetailPage complaintId="f83a00-1122" onBack={onBack} />);

    await waitFor(() => {
      expect(screen.getByText(/Issue #f83a00-1122/i)).toBeInTheDocument();
      expect(screen.getByText(/Broken water main leaking/i)).toBeInTheDocument();
      expect(screen.getByText(/Major clean water distribution leak/i)).toBeInTheDocument();
      expect(screen.getByText(/llm:gemini-2.5-flash/i)).toBeInTheDocument();
      expect(screen.getByText(/1100 ms/i)).toBeInTheDocument();
      expect(screen.getByText(/0300-1234567/i)).toBeInTheDocument();
    });
  });

  it("advances workflow status and shows success banner", async () => {
    const user = userEvent.setup();
    vi.spyOn(apiClient, "getComplaint").mockResolvedValue(mockComplaint);
    const updateSpy = vi.spyOn(apiClient, "updateComplaintStatus").mockResolvedValue({
      ...mockComplaint,
      status: Status.RESOLVED,
    });

    render(<ComplaintDetailPage complaintId="f83a00-1122" onBack={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /mark as resolved/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /mark as resolved/i }));

    await waitFor(() => {
      expect(updateSpy).toHaveBeenCalledWith("f83a00-1122", { status: Status.RESOLVED });
      expect(screen.getByText(/Status transitioned to Resolved/i)).toBeInTheDocument();
    });
  });

  it("renders terminal state notice when issue is resolved", async () => {
    vi.spyOn(apiClient, "getComplaint").mockResolvedValue({
      ...mockComplaint,
      status: Status.RESOLVED,
    });

    render(<ComplaintDetailPage complaintId="f83a00-1122" onBack={vi.fn()} />);

    await waitFor(() => {
      expect(
        screen.getByText(/Terminal status \(Resolved\)\. No further status changes permitted\./i)
      ).toBeInTheDocument();
    });
  });
});
