import { useEffect, useState } from "react";

import { ApiError, dashboardSummary, getReadiness, type DashboardSummary, type ReadyResponse } from "../api/client";

export function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [health, setHealth] = useState<ReadyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([dashboardSummary(), getReadiness()])
      .then(([metrics, ready]) => {
        if (!cancelled) {
          setSummary(metrics);
          setHealth(ready);
        }
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setError(caught instanceof ApiError ? caught.message : "The API did not respond.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const cards = summary
    ? [
        ["Queries", String(summary.total_queries)],
        ["Cache hit rate", `${Math.round(summary.hit_rate * 100)}%`],
        ["Average latency", `${summary.average_latency_ms} ms`],
        ["P95 latency", `${summary.p95_latency_ms} ms`],
        ["Estimated cost", `$${summary.estimated_cost.toFixed(6)}`],
        ["Cost saved", `$${summary.estimated_cost_saved.toFixed(6)}`],
        ["Input tokens", String(summary.input_tokens)],
        ["Output tokens", String(summary.output_tokens)],
      ]
    : [];

  return (
    <section className="mx-auto max-w-4xl">
      <header>
        <h2 className="text-2xl font-semibold">Dashboard</h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-ink/70">
          Totals come from your tenant&apos;s query log. An admin also sees that tenant&apos;s query count.
        </p>
      </header>
      {error ? <p className="mt-4 text-sm text-red-800">{error}</p> : null}
      {!error && !summary ? <p className="mt-4 text-sm text-ink/70">Loading metrics…</p> : null}
      {summary ? (
        <ul className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {cards.map(([label, value]) => (
            <li key={label} className="rounded-lg border border-line bg-card px-4 py-3">
              <p className="text-xs uppercase tracking-wide text-ink/60">{label}</p>
              <p className="mt-1 text-lg font-semibold">{value}</p>
            </li>
          ))}
        </ul>
      ) : null}
      {summary && summary.model_distribution.length > 0 ? (
        <div className="mt-6 rounded-lg border border-line bg-card p-5">
          <h3 className="text-sm font-semibold">Models</h3>
          <ul className="mt-3 space-y-1 text-sm">
            {summary.model_distribution.map((item) => (
              <li key={item.model}>
                {item.model}: {item.total_queries}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {summary?.queries_by_tenant ? (
        <div className="mt-6 rounded-lg border border-line bg-card p-5">
          <h3 className="text-sm font-semibold">Queries by tenant</h3>
          <ul className="mt-3 space-y-1 text-sm">
            {summary.queries_by_tenant.map((item) => (
              <li key={item.tenant_id}>
                {item.tenant_id}: {item.total_queries}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <div className="mt-6 rounded-lg border border-line bg-card p-5">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-ink/60">Service health</h3>
        {health ? (
          <ul className="mt-4 grid gap-3 sm:grid-cols-2">
            {Object.entries(health.checks).map(([name, check]) => (
              <li key={name} className="rounded-md border border-line px-4 py-3">
                <p className="text-sm font-medium capitalize">{name}</p>
                <p className={check.ok ? "text-sm text-pine" : "text-sm text-red-800"}>
                  {check.ok ? "Connected" : "Unavailable"}
                </p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-sm text-ink/70">Checking services…</p>
        )}
      </div>
    </section>
  );
}
