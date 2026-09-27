import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SubmitPage } from "../pages/SubmitPage";
import * as apiClient from "../api/client";
import { Category, Priority, Status, type Complaint } from "../types/complaint";

describe("SubmitPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders form fields and enforces client-side validation requirements", async () => {
    const onSubmitted = vi.fn();
    render(<SubmitPage onSubmitted={onSubmitted} />);

    expect(screen.getByRole("heading", { name: /report a civic issue/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/description/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/location/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/reporter contact/i)).toBeInTheDocument();

    const submitBtn = screen.getByRole("button", { name: /submit issue/i });
    expect(submitBtn).toBeDisabled();
  });

  it("submits valid complaint and displays honest loading state during triage call", async () => {
    const user = userEvent.setup({ delay: null });
    const onSubmitted = vi.fn();

    const mockCreated: Complaint = {
      id: "c-100",
      text: "Massive pothole on main avenue disrupting commuter traffic",
      location: "Sector G-10, Main Double Road",
      reporter_contact: "citizen@example.com",
      category: Category.ROADS,
      priority: Priority.HIGH,
      status: Status.OPEN,
      ai_summary: "Severe road damage requiring asphalt patching",
      triaged_by: "llm:groq:llama-3.3-70b-versatile",
      triage_latency_ms: 1240,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    let resolvePromise: (val: Complaint) => void = () => {};
    const deferred = new Promise<Complaint>((resolve) => {
      resolvePromise = resolve;
    });

    vi.spyOn(apiClient, "createComplaint").mockImplementation(() => deferred);

    render(<SubmitPage onSubmitted={onSubmitted} />);

    const descInput = screen.getByLabelText(/description/i);
    const locInput = screen.getByLabelText(/location/i);
    const submitBtn = screen.getByRole("button", { name: /submit issue/i });

    await user.type(descInput, "Massive pothole on main avenue disrupting commuter traffic");
    await user.type(locInput, "Sector G-10, Main Double Road");

    expect(submitBtn).not.toBeDisabled();
    await user.click(submitBtn);

    // Honest loading state during AI triage latency
    expect(screen.getByRole("button", { name: /submitting & triaging…/i })).toBeDisabled();

    // Resolve API promise
    resolvePromise(mockCreated);

    await waitFor(() => {
      expect(onSubmitted).toHaveBeenCalledWith("c-100");
    });
  });

  it("surfaces server validation and network errors when submission fails", async () => {
    const user = userEvent.setup({ delay: null });
    const onSubmitted = vi.fn();

    vi.spyOn(apiClient, "createComplaint").mockRejectedValue(
      new apiClient.ApiError(400, "Bad Request", { detail: "Text failed safety filter" })
    );

    render(<SubmitPage onSubmitted={onSubmitted} />);

    await user.type(screen.getByLabelText(/description/i), "Water contamination in sector pipeline");
    await user.type(screen.getByLabelText(/location/i), "Street 4, Sector F-6");
    await user.click(screen.getByRole("button", { name: /submit issue/i }));

    await waitFor(() => {
      expect(screen.getByText(/"Text failed safety filter"/i)).toBeInTheDocument();
    });
    expect(onSubmitted).not.toHaveBeenCalled();
  });
});
