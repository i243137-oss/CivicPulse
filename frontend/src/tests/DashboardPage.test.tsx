import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DashboardPage } from "../pages/DashboardPage";
import * as apiClient from "../api/client";

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const mockStatsResult: apiClient.StatsResult = {
    stats: {
      total: 42,
      by_status: { open: 12, in_progress: 10, resolved: 18, rejected: 2 },
      by_category: { water: 15, electricity: 12, sanitation: 8, roads: 4, streetlights: 2, other: 1 },
      by_priority: { high: 14, normal: 20, low: 8 },
    },
    cacheStatus: "HIT",
  };

  const mockProviderInfo = {
    active_provider: "llm:groq:llama-3.3-70b-versatile",
    cache_metrics: {
      hits: 35,
      misses: 10,
      total_requests: 45,
      hit_rate: 0.778,
    },
    recent_outcomes: [
      { provider: "llm:groq:llama-3.3-70b-versatile", latency_ms: 450, fallback: false },
    ],
  };

  it("renders aggregate totals and X-Cache status header properly", async () => {
    vi.spyOn(apiClient, "getStats").mockResolvedValue(mockStatsResult);
    vi.spyOn(apiClient, "getProvidersMeta").mockResolvedValue(mockProviderInfo);

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("42")).toBeInTheDocument();
      expect(screen.getByText("Total Complaints")).toBeInTheDocument();
      expect(screen.getByText("X-Cache: HIT")).toBeInTheDocument();
      expect(screen.getAllByText(/llm:groq:llama-3.3-70b-versatile/i).length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText(/77.8%/i)).toBeInTheDocument();
    });
  });

  it("handles server failure and provides retry action", async () => {
    const getStatsSpy = vi.spyOn(apiClient, "getStats").mockRejectedValue(
      new apiClient.ApiError(500, "Internal Server Error", { detail: "Database unavailable" })
    );
    vi.spyOn(apiClient, "getProvidersMeta").mockResolvedValue(mockProviderInfo);

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/Database unavailable/i)).toBeInTheDocument();
    });

    // When clicking retry, getStats is re-triggered
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /retry/i }));

    expect(getStatsSpy).toHaveBeenCalledTimes(2);
  });
});
