import { type ReactNode, useState } from "react";
import { Bot, Database, Plug, ScrollText, ShieldAlert, ShieldCheck, Terminal } from "lucide-react";
import clsx from "clsx";

import { AuditLogPanel } from "../components/AuditLogPanel";
import { GatingQueue } from "../components/GatingQueue";
import { SettingsView } from "../settings/SettingsView";

type AdminSection =
  | "validation"
  | "audit"
  | "agent"
  | "rag"
  | "gating-policy"
  | "connectors"
  | "logging";

/** Une entrée = un objectif précis (jamais deux réglages sans rapport sur le même écran) —
 * chaque section de paramétrage (Epic 9) obtient sa propre page plutôt que d'être noyée dans une
 * grille unique "Paramètres" fourre-tout. "Connecteurs" regroupe les identifiants externes
 * (GitHub/SharePoint/Jira), un connecteur = une section (voir `only` ci-dessous), jamais mélangés
 * dans un même formulaire. */
const SECTIONS: { value: AdminSection; label: string; icon: ReactNode }[] = [
  { value: "validation", label: "File de validation", icon: <ShieldAlert className="h-4 w-4" /> },
  { value: "audit", label: "Journal d'audit", icon: <ScrollText className="h-4 w-4" /> },
  { value: "agent", label: "Agent (LLM)", icon: <Bot className="h-4 w-4" /> },
  { value: "rag", label: "Base de connaissances (RAG)", icon: <Database className="h-4 w-4" /> },
  { value: "gating-policy", label: "Politique de confiance", icon: <ShieldCheck className="h-4 w-4" /> },
  { value: "connectors", label: "Connecteurs", icon: <Plug className="h-4 w-4" /> },
  { value: "logging", label: "Journalisation", icon: <Terminal className="h-4 w-4" /> },
];

const CONNECTOR_SECTION_KEYS = ["github_credentials", "sharepoint_credentials", "jira_credentials"];

export function AdminView({ refreshSignal }: { refreshSignal: number }) {
  const [section, setSection] = useState<AdminSection>("validation");

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
        {section === "validation" && (
          <GatingQueue refreshSignal={refreshSignal} className="h-[calc(100vh-220px)] min-h-[420px]" />
        )}
        {section === "audit" && (
          <AuditLogPanel refreshSignal={refreshSignal} className="h-[calc(100vh-220px)] min-h-[420px]" />
        )}
        {section === "agent" && <SettingsView only={["agent"]} />}
        {section === "rag" && <SettingsView only={["rag"]} />}
        {section === "gating-policy" && <SettingsView only={["gating"]} />}
        {section === "connectors" && <SettingsView only={CONNECTOR_SECTION_KEYS} />}
        {section === "logging" && <SettingsView only={["logging"]} />}
      </div>
    </div>
  );
}
