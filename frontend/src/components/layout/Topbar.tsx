import { api } from "@/lib/apiClient";
import { MobileMenuButton } from "@/components/layout/MobileMenuButton";

export async function Topbar() {
  const health = await api.health();
  const connected = health?.status === "ok";

  return (
    <header className="flex items-center justify-between gap-3 border-b border-border px-4 py-4 sm:px-6">
      <div className="flex min-w-0 items-center gap-3">
        <MobileMenuButton />
        <div className="flex min-w-0 items-center gap-2 text-sm text-muted">
          <span
            className={`h-2 w-2 shrink-0 rounded-full ${connected ? "bg-positive" : "bg-negative"}`}
            aria-hidden="true"
          />
          <span className="truncate">
            {connected ? "Backend connected" : "Backend not reachable — check NEXT_PUBLIC_API_URL"}
          </span>
        </div>
      </div>
      <div className="shrink-0 font-mono text-xs text-muted tabular">XAU/USD · NQ</div>
    </header>
  );
}
