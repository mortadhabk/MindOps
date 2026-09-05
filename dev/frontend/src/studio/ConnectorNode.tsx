import { Handle, type Node, type NodeProps, Position } from "@xyflow/react";
import clsx from "clsx";
import { Loader2, RefreshCw, Trash2 } from "lucide-react";

import type { ConnectorInstance, ConnectorInstanceStatus } from "../lib/api";

export type ConnectorNodeData = {
  instance: ConnectorInstance;
  onSync: (id: number) => void;
  onDelete: (id: number) => void;
};

const STATUS_META: Record<ConnectorInstanceStatus, { label: string; dot: string }> = {
  idle: { label: "Jamais synchronisé", dot: "bg-slate-500" },
  syncing: { label: "Synchronisation…", dot: "bg-amber-400 animate-pulse" },
  success: { label: "Synchronisé", dot: "bg-emerald-400" },
  error: { label: "Erreur", dot: "bg-rose-500" },
};

export function ConnectorNode({ data }: NodeProps<Node<ConnectorNodeData>>) {
  const { instance, onSync, onDelete } = data;
  const meta = STATUS_META[instance.status];
  const isSyncing = instance.status === "syncing";

  return (
    <div className="w-56 rounded-2xl border border-white/10 bg-white/[0.04] p-3 shadow-lg backdrop-blur-xl">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-slate-100">
            {instance.display_name}
          </div>
          <div className="text-[10px] uppercase tracking-wide text-slate-500">
            {instance.connector_type}
          </div>
        </div>
        <button
          type="button"
          onClick={() => onDelete(instance.id)}
          className="rounded-lg p-1 text-slate-500 transition hover:bg-rose-500/10 hover:text-rose-300"
          aria-label="Supprimer cette source"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="mt-2 flex items-center gap-1.5 text-[11px] text-slate-400">
        <span className={clsx("h-1.5 w-1.5 rounded-full", meta.dot)} />
        {meta.label}
        {instance.last_result && instance.status !== "syncing" && (
          <span className="text-slate-600">
            · {instance.last_result.synced} doc{instance.last_result.synced > 1 ? "s" : ""}
          </span>
        )}
      </div>

      {instance.status === "error" && instance.last_result?.errors[0] && (
        <p className="mt-1 line-clamp-2 text-[10px] text-rose-400/80">
          {instance.last_result.errors[0]}
        </p>
      )}

      <button
        type="button"
        onClick={() => onSync(instance.id)}
        disabled={isSyncing}
        className="mt-2.5 flex w-full items-center justify-center gap-1.5 rounded-lg bg-white/5 py-1.5 text-[11px] font-medium text-slate-200 transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {isSyncing ? (
          <Loader2 className="h-3 w-3 animate-spin" />
        ) : (
          <RefreshCw className="h-3 w-3" />
        )}
        Synchroniser
      </button>

      <Handle type="source" position={Position.Right} className="!bg-slate-400" />
    </div>
  );
}
