import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { clearToken, currentUser, type CurrentUser } from "../api/client";

const links = [
  { to: "/chat", label: "Chat" },
  { to: "/documents", label: "Documents" },
  { to: "/dashboard", label: "Dashboard" },
];

export function Layout() {
  const navigate = useNavigate();
  const [user, setUser] = useState<CurrentUser | null>(null);

  useEffect(() => {
    let cancelled = false;
    currentUser()
      .then((result) => {
        if (!cancelled) {
          setUser(result);
        }
      })
      .catch(() => {
        clearToken();
        navigate("/login", { replace: true });
      });
    return () => {
      cancelled = true;
    };
  }, [navigate]);

  function signOut() {
    clearToken();
    navigate("/login", { replace: true });
  }

  return (
    <div className="min-h-screen md:grid md:grid-cols-[240px_1fr]">
      <aside className="border-b border-line bg-ink text-paper md:min-h-screen md:border-b-0 md:border-r">
        <div className="px-5 py-6">
          <p className="text-xs uppercase tracking-[0.18em] text-paper/60">Platform</p>
          <h1 className="mt-1 text-lg font-semibold">Multi-Tenant RAG</h1>
          {user ? (
            <p className="mt-3 text-xs leading-5 text-paper/70">
              {user.email}
              <br />
              {user.role}
            </p>
          ) : null}
        </div>
        <nav className="flex gap-2 overflow-x-auto px-3 pb-4 md:block md:px-3">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) =>
                [
                  "block whitespace-nowrap rounded-md px-3 py-2 text-sm",
                  isActive ? "bg-pine text-white" : "text-paper/80 hover:bg-white/10",
                ].join(" ")
              }
            >
              {link.label}
            </NavLink>
          ))}
          <button
            type="button"
            onClick={signOut}
            className="block whitespace-nowrap rounded-md px-3 py-2 text-left text-sm text-paper/80 hover:bg-white/10"
          >
            Sign out
          </button>
        </nav>
      </aside>
      <main className="px-5 py-8 md:px-10">
        <Outlet />
      </main>
    </div>
  );
}
