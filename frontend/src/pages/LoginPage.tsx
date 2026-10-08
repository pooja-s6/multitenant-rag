import { type FormEvent, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { ApiError, login, readToken, storeToken } from "../api/client";

export function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (readToken()) {
    return <Navigate to="/chat" replace />;
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setMessage(null);
    try {
      const result = await login(email, password);
      storeToken(result.access_token);
      navigate("/chat", { replace: true });
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : "The API did not respond.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="mx-auto max-w-md px-5 py-16">
      <h2 className="text-2xl font-semibold">Sign in</h2>
      <p className="mt-2 text-sm leading-6 text-ink/70">
        Your token stays in this browser tab. Questions and documents stay inside your tenant.
      </p>
      <form onSubmit={onSubmit} className="mt-6 space-y-4 rounded-lg border border-line bg-card p-5">
        <label className="block text-sm">
          Email
          <input
            type="email"
            required
            autoComplete="username"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="mt-1 w-full rounded-md border border-line bg-white px-3 py-2"
          />
        </label>
        <label className="block text-sm">
          Password
          <input
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="mt-1 w-full rounded-md border border-line bg-white px-3 py-2"
          />
        </label>
        <button
          type="submit"
          disabled={submitting}
          className="rounded-md bg-pine px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
        >
          {submitting ? "Signing in…" : "Sign in"}
        </button>
        {message ? <p className="text-sm text-red-800">{message}</p> : null}
      </form>
    </section>
  );
}
