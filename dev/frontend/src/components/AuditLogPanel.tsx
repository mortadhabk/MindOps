import clsx from "clsx";
import { ScrollText } from "lucide-react";

import { useAuditLog } from "../hooks/useAuditLog";
import { eventTypeMeta } from "../lib/eventTypes";
import { Panel } from "./Panel";
import { EmptyState, RefreshButton } from "./ui";

const FILTERS = [
  { value: "", label: "Tous" },
  { value: "agent.llm_call", label: "Appels LLM" },
  { value: "agent.action_proposed", label: "Propositions" },
  { value: "gating.decision", label: "Décisions" },
];

export function AuditLogPanel({ refreshSignal }: { refreshSignal: number }) {
  const { logs, filter, setFilter, refresh } = useAuditLog(8000, refreshSignal);

  return (
    <Panel
      title="Journal d'audit"
      icon={<ScrollText className="h-4 w-4 text-sky-400" />}
      actions={<RefreshButton onClick={refresh} />}
      className="h-[300px]"
    >
      <div className="flex h-full flex-col">
        <div className="flex flex-wrap gap-1.5 border-b border-white/10 px-4 py-2.5">
          {FILTERS.map((item) => (
            <button
              key={item.value}
              type="button"
              onClick={() => setFilter(item.value)}
              className={clsx(
                "rounded-full px-2.5 py-1 text-[11px] font-medium transition",
                filter === item.value
                  ? "bg-indigo-500/20 text-indigo-200"
                  : "text-slate-400 hover:bg-white/5 hover:text-slate-200",
              )}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="scrollbar-thin flex-1 overflow-y-auto px-4 py-3">
          {logs.length === 0 && <EmptyState label="Aucun événement" />}
          <ul className="space-y-2.5">
            {logs.slice(0, 50).map((log) => {
              const meta = eventTypeMeta(log.event_type);
              return (
                <li key={log.id} className="flex gap-2.5 text-xs">
                  <span className={clsx("mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full", meta.dot)} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium text-slate-200">{meta.label}</span>
                      <time className="shrink-0 text-[10px] text-slate-500">
                        {new Date(`${log.created_at}Z`).toLocaleTimeString("fr-FR")}
                      </time>
                    </div>
                    <pre className="mt-0.5 truncate font-mono text-[10.5px] text-slate-500">
                      {JSON.stringify(log.payload)}
                    </pre>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      </div>
    </Panel>
  );
}
