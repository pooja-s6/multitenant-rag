import { NavLink, Outlet } from "react-router-dom";

const links = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/chat", label: "Chat" },
  { to: "/documents", label: "Documents" },
  { to: "/login", label: "Sign in" },
];

export function Layout() {
  return (
    <div className="min-h-screen md:grid md:grid-cols-[240px_1fr]">
      <aside className="border-b border-line bg-ink text-paper md:min-h-screen md:border-b-0 md:border-r">
        <div className="px-5 py-6">
          <p className="text-xs uppercase tracking-[0.18em] text-paper/60">Platform</p>
          <h1 className="mt-1 text-lg font-semibold">Multi-Tenant RAG</h1>
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
        </nav>
      </aside>
      <main className="px-5 py-8 md:px-10">
        <Outlet />
      </main>
    </div>
  );
}
