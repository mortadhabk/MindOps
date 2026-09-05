import { useEffect, useState } from "react";
import { Sparkles } from "lucide-react";

import { fetchHealth } from "../lib/api";

export function Header() {
  const [online, setOnline] = useState<boolean | null>(null);

  useEffect(() => {
    const check = () => fetchHealth().then(setOnline);
    check();
    const interval = setInterval(check, 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="flex flex-col gap-3 px-6 pb-5 pt-8 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <div className="flex items-center gap-2.5 text-2xl font-bold tracking-tight text-white">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-sky-400 shadow-glow">
            <Sparkles className="h-5 w-5 text-white" />
          </span>
          Agent IA
        </div>
        <p className="mt-1.5 text-sm text-slate-400">
          Chat, file de validation et journal d'audit — en un seul endroit.
        </p>
      </div>
      <div className="flex items-center gap-2 self-start rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-slate-300">
        <span className="relative flex h-2 w-2">
          {online && (
            <span className="absolute inline-flex h-full w-full animate-pulse-ring rounded-full bg-emerald-400" />
          )}
          <span
            className={clsxDot(online)}
          />
        </span>
        {online === null ? "Vérification…" : online ? "API en ligne" : "API injoignable"}
      </div>
    </header>
  );
}

function clsxDot(online: boolean | null): string {
  const base = "relative inline-flex h-2 w-2 rounded-full";
  if (online === null) return `${base} bg-slate-500`;
  return online ? `${base} bg-emerald-400` : `${base} bg-rose-500`;
}
