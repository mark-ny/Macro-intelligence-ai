import { api } from "@/lib/apiClient";

export async function Topbar() {
  const health = await api.health();
  const connected = health?.status === "ok";

  return (
    <header className="flex items-center justify-between border-b border-border px-6 py-4">
      <div className="flex items-center gap-2 text-sm text-muted">
        <span
          className={`h-2 w-2 rounded-full ${connected ? "bg-positive" : "bg-negative"}`}
          aria-hidden="true"
        />
        {connected ? "Backend connected" : "Backend not reachable — check NEXT_PUBLIC_API_URL"}
      </div>
      <div className="font-mono text-xs text-muted tabular">XAU/USD · NQ</div>
    </header>
  );
}
