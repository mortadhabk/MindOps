import type { DragEvent } from "react";
import { RefreshCw } from "lucide-react";

import type { ConnectorType } from "../lib/api";

export const CONNECTOR_DRAG_FORMAT = "application/x-connector-type";

interface ConnectorPaletteProps {
  types: ConnectorType[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}

export function ConnectorPalette({ types, loading, error, onRetry }: ConnectorPaletteProps) {
  const onDragStart = (event: DragEvent<HTMLDivElement>, type: ConnectorType) => {
    event.dataTransfer.setData(CONNECTOR_DRAG_FORMAT, JSON.stringify(type));
    event.dataTransfer.effectAllowed = "move";
  };

  return (
    <aside className="flex w-56 shrink-0 flex-col rounded-2xl border border-white/10 bg-white/[0.03] p-3 backdrop-blur-xl">
      <h3 className="mb-3 px-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
        Sources disponibles
      </h3>
      <div className="space-y-2">
        {types.map((type) => (
          <div
            key={type.name}
            draggable
            onDragStart={(event) => onDragStart(event, type)}
            title={type.description}
            className="cursor-grab rounded-xl border border-white/10 bg-white/[0.04] p-3 text-sm text-slate-200 transition hover:border-indigo-400/40 hover:bg-white/[0.07] active:cursor-grabbing"
          >
            <div className="font-medium">{type.display_name}</div>
            <p className="mt-0.5 line-clamp-2 text-[11px] text-slate-500">{type.description}</p>
          </div>
        ))}

        {loading && types.length === 0 && (
          <p className="px-1 text-xs text-slate-600">Chargement…</p>
        )}

        {!loading && error && (
          <div className="rounded-xl border border-rose-500/20 bg-rose-500/[0.06] p-3 text-[11px] text-rose-300">
            <p>Impossible de charger les types de connecteurs : {error}</p>
            <button
              type="button"
              onClick={onRetry}
              className="mt-2 flex items-center gap-1.5 rounded-lg bg-white/5 px-2 py-1 text-rose-200 transition hover:bg-white/10"
            >
              <RefreshCw className="h-3 w-3" />
              Réessayer
            </button>
          </div>
        )}

        {!loading && !error && types.length === 0 && (
          <p className="px-1 text-xs text-slate-600">Aucun connecteur disponible.</p>
        )}
      </div>
      <p className="mt-4 px-1 text-[11px] leading-relaxed text-slate-600">
        Glisser une source sur le canvas pour la configurer et la relier à l'Orchestrateur.
      </p>
    </aside>
  );
}
