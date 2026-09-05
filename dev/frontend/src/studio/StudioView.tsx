import "@xyflow/react/dist/style.css";

import { ReactFlowProvider } from "@xyflow/react";
import { useState } from "react";

import { useConnectorInstances } from "../hooks/useConnectorInstances";
import { useConnectorTypes } from "../hooks/useConnectorTypes";
import type { ConnectorType } from "../lib/api";
import { ConnectorConfigModal } from "./ConnectorConfigModal";
import { ConnectorPalette } from "./ConnectorPalette";
import { StudioCanvas } from "./StudioCanvas";

interface PendingDrop {
  type: ConnectorType;
  x: number;
  y: number;
}

export function StudioView() {
  const { types } = useConnectorTypes();
  const { instances, create, move, remove, sync } = useConnectorInstances();
  const [pendingDrop, setPendingDrop] = useState<PendingDrop | null>(null);

  return (
    <ReactFlowProvider>
      <div className="flex h-[70vh] min-h-[480px] gap-4">
        <ConnectorPalette types={types} />
        <StudioCanvas
          instances={instances}
          onDropType={(type, position) => setPendingDrop({ type, x: position.x, y: position.y })}
          onMoveInstance={move}
          onSyncInstance={sync}
          onDeleteInstance={remove}
        />
      </div>

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
