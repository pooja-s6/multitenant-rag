import { useEffect, useState } from "react";

import { getReadiness, type ReadyResponse } from "../api/client";

export function DashboardPage() {
  const [health, setHealth] = useState<ReadyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getReadiness()
      .then((result) => {
        if (!cancelled) {
          setHealth(result);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError("The API did not respond. Start the backend, then refresh this page.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="mx-auto max-w-4xl">
      <header>
        <h2 className="text-2xl font-semibold">Dashboard</h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-ink/70">
          Query volume, cache hit rate, latency, and estimated cost will appear here once
          analytics are recorded. This page currently checks that the API can reach Postgres
          and Redis.
        </p>
      </header>

      <div className="mt-6 rounded-lg border border-line bg-card p-5">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-ink/60">Service health</h3>
        {error ? <p className="mt-3 text-sm text-red-800">{error}</p> : null}
        {!error && !health ? <p className="mt-3 text-sm text-ink/70">Checking services…</p> : null}
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
        ) : null}
      </div>
    </section>
  );
}
