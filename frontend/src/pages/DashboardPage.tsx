/**
 * Dashboard page — aggregate statistics, cache HIT/MISS display, and provider meta.
 */

import { useCallback, useEffect, useState } from "react";
import { getStats, getProvidersMeta, type StatsResult, ApiError } from "../api/client";
import type { ProviderInfoResponse } from "../types/complaint";
import { CATEGORY_LABELS, PRIORITY_LABELS, STATUS_LABELS, Category, Priority, Status } from "../types/complaint";
import { Badge } from "../components/Badge";
import { LoadingSpinner } from "../components/LoadingSpinner";

export function DashboardPage() {
  const [statsResult, setStatsResult] = useState<StatsResult | null>(null);
  const [providerInfo, setProviderInfo] = useState<ProviderInfoResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [sr, pi] = await Promise.all([getStats(), getProvidersMeta()]);
      setStatsResult(sr);
      setProviderInfo(pi);
    } catch (err) {
      if (err instanceof ApiError) setError(`Server error: ${err.message}`);
      else if (err instanceof TypeError) setError("Network error: unable to reach the backend.");
      else setError("An unexpected error occurred.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void fetchData(); }, [fetchData]);

  if (loading) return <LoadingSpinner message="Loading dashboard…" />;
  if (error) {
    return (
      <div className="error-card">
        <h2>⚠️ Error</h2><p>{error}</p>
        <button className="btn btn--primary" onClick={() => void fetchData()}>Retry</button>
      </div>
    );
  }
  if (!statsResult || !providerInfo) return null;

  const { stats, cacheStatus } = statsResult;
  return (
    <div className="dashboard">
      <div className="dashboard__header">
        <h2>📊 Dashboard</h2>
        <div className="cache-indicator">
          <span className={`cache-badge cache-badge--${cacheStatus.toLowerCase()}`}>
            X-Cache: {cacheStatus}
          </span>
          <button className="btn btn--sm btn--outline" onClick={() => void fetchData()}>↻ Refresh</button>
        </div>
      </div>

      <div className="stats-grid">
        <div className="stat-card stat-card--total">
          <p className="stat-card__value">{stats.total}</p>
          <p className="stat-card__label">Total Complaints</p>
        </div>
        {Object.values(Status).map((s) => (
          <div key={s} className="stat-card">
            <p className="stat-card__value">{stats.by_status[s] ?? 0}</p>
            <p className="stat-card__label"><Badge label={STATUS_LABELS[s]} variant="status" value={s} /></p>
          </div>
        ))}
      </div>

      <section className="stats-section">
        <h3>By Category</h3>
        <div className="stats-bar-list">
          {Object.values(Category).map((c) => {
            const count = stats.by_category[c] ?? 0;
            const pct = stats.total > 0 ? (count / stats.total) * 100 : 0;
            return (
              <div key={c} className="stats-bar-item">
                <span className="stats-bar-item__label"><Badge label={CATEGORY_LABELS[c]} variant="category" value={c} /></span>
                <div className="stats-bar-item__track"><div className="stats-bar-item__fill" style={{ width: `${pct}%` }} /></div>
                <span className="stats-bar-item__count">{count}</span>
              </div>
            );
          })}
        </div>
      </section>

      <section className="stats-section">
        <h3>By Priority</h3>
        <div className="stats-bar-list">
          {Object.values(Priority).map((p) => {
            const count = stats.by_priority[p] ?? 0;
            const pct = stats.total > 0 ? (count / stats.total) * 100 : 0;
            return (
              <div key={p} className="stats-bar-item">
                <span className="stats-bar-item__label"><Badge label={PRIORITY_LABELS[p]} variant="priority" value={p} /></span>
                <div className="stats-bar-item__track"><div className="stats-bar-item__fill" style={{ width: `${pct}%` }} /></div>
                <span className="stats-bar-item__count">{count}</span>
              </div>
            );
          })}
        </div>
      </section>

      <section className="stats-section">
        <h3>🤖 AI Triage Provider</h3>
        <div className="provider-card">
          <p><strong>Active:</strong> {providerInfo.active_provider}</p>
          <p><strong>Cache:</strong> {providerInfo.cache_metrics.hits}/{providerInfo.cache_metrics.total_requests} ({(providerInfo.cache_metrics.hit_rate * 100).toFixed(1)}%)</p>
          {providerInfo.recent_outcomes.length > 0 && (
            <details className="provider-outcomes">
              <summary>Recent outcomes ({providerInfo.recent_outcomes.length})</summary>
              <table className="mini-table">
                <thead><tr><th>Provider</th><th>Latency</th><th>Fallback</th></tr></thead>
                <tbody>
                  {providerInfo.recent_outcomes.map((o, i) => (
                    <tr key={i}><td>{o.provider}</td><td>{o.latency_ms}ms</td><td>{o.fallback ? "Yes" : "No"}</td></tr>
                  ))}
                </tbody>
              </table>
            </details>
          )}
        </div>
      </section>
    </div>
  );
}
