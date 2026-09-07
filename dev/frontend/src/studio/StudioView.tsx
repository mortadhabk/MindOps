import "@xyflow/react/dist/style.css";

import { ReactFlowProvider } from "@xyflow/react";
import { KeyRound } from "lucide-react";
import { useState } from "react";

import { useConnectorInstances } from "../hooks/useConnectorInstances";
import { useConnectorTypes } from "../hooks/useConnectorTypes";
import type { ConnectorType } from "../lib/api";
import { ConnectorConfigModal } from "./ConnectorConfigModal";
import { ConnectorCredentialsModal } from "./ConnectorCredentialsModal";
import { ConnectorPalette } from "./ConnectorPalette";
import { StudioCanvas } from "./StudioCanvas";

interface PendingDrop {
  type: ConnectorType;
  x: number;
  y: number;
}

export function StudioView() {
  const { types, loading, error, refresh } = useConnectorTypes();
  const { instances, create, move, remove, sync } = useConnectorInstances();
  const [pendingDrop, setPendingDrop] = useState<PendingDrop | null>(null);
  const [credentialsOpen, setCredentialsOpen] = useState(false);

  return (
    <ReactFlowProvider>
      <div className="mb-3 flex items-center justify-end">
        <button
          type="button"
          onClick={() => setCredentialsOpen(true)}
          className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs font-medium text-slate-300 transition hover:bg-white/10 hover:text-white"
        >
          <KeyRound className="h-3.5 w-3.5" />
          Identifiants des connecteurs
        </button>
      </div>

      <div className="flex h-[70vh] min-h-[480px] gap-4">
        <ConnectorPalette types={types} loading={loading} error={error} onRetry={refresh} />
        <StudioCanvas
          instances={instances}
          onDropType={(type, position) => setPendingDrop({ type, x: position.x, y: position.y })}
          onMoveInstance={move}
          onSyncInstance={sync}
          onDeleteInstance={remove}
        />
      </div>

      {credentialsOpen && (
        <ConnectorCredentialsModal onClose={() => setCredentialsOpen(false)} />
      )}

      {pendingDrop && (
        <ConnectorConfigModal
          connectorType={pendingDrop.type}
          onCancel={() => setPendingDrop(null)}
          onSubmit={async (displayName, config) => {
            await create({
              connectorType: pendingDrop.type.name,
              displayName,
              config,
              positionX: pendingDrop.x,
              positionY: pendingDrop.y,
            });
            setPendingDrop(null);
          }}
        />
      )}
    </ReactFlowProvider>
  );
}
