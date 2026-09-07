import { type ReactNode, useState } from "react";
import { Settings, ScrollText, ShieldAlert } from "lucide-react";
import clsx from "clsx";

import { AuditLogPanel } from "../components/AuditLogPanel";
import { GatingQueue } from "../components/GatingQueue";
import { SettingsView } from "../settings/SettingsView";

type AdminSection = "gating" | "audit" | "settings";

const SECTIONS: { value: AdminSection; label: string; icon: ReactNode }[] = [
  { value: "gating", label: "File de validation", icon: <ShieldAlert className="h-4 w-4" /> },
  { value: "audit", label: "Journal d'audit", icon: <ScrollText className="h-4 w-4" /> },
  { value: "settings", label: "Paramètres", icon: <Settings className="h-4 w-4" /> },
];

export function AdminView({ refreshSignal }: { refreshSignal: number }) {
  const [section, setSection] = useState<AdminSection>("gating");

  return (
    <div className="grid gap-5 lg:grid-cols-[220px_1fr]">
      <nav className="flex h-fit flex-col gap-1 rounded-2xl border border-white/10 bg-white/[0.03] p-2 shadow-xl shadow-black/20 backdrop-blur-xl">
        {SECTIONS.map((item) => (
          <button
            key={item.value}
            type="button"
            onClick={() => setSection(item.value)}
            className={clsx(
              "flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-left text-sm font-medium transition",
              section === item.value
                ? "bg-gradient-to-br from-indigo-500 to-sky-400 text-white shadow-sm"
                : "text-slate-400 hover:bg-white/5 hover:text-slate-200",
            )}
          >
            {item.icon}
            {item.label}
          </button>
        ))}
      </nav>
      <div>
        {section === "gating" && (
          <GatingQueue refreshSignal={refreshSignal} className="h-[calc(100vh-220px)] min-h-[420px]" />
        )}
        {section === "audit" && (
          <AuditLogPanel refreshSignal={refreshSignal} className="h-[calc(100vh-220px)] min-h-[420px]" />
        )}
        {section === "settings" && <SettingsView />}
      </div>
    </div>
  );
}
