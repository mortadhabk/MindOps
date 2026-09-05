import { useCallback, useEffect, useState } from "react";

import {
  type ConnectorInstance,
  createConnectorInstance,
  deleteConnectorInstance,
  fetchConnectorInstances,
  syncConnectorInstance,
  updateConnectorInstancePosition,
} from "../lib/api";

export function useConnectorInstances(pollMs = 4000) {
  const [instances, setInstances] = useState<ConnectorInstance[]>([]);

  const refresh = useCallback(async () => {
    try {
      setInstances(await fetchConnectorInstances());
    } catch {
      // Rafraîchissement raté : on garde la dernière liste connue plutôt que de la vider.
    }
  }, []);

  useEffect(() => {
    refresh();
    // Poll plus rapproché que gating/audit (4s) : une synchronisation en tâche de fond est
    // généralement courte (connecteurs mock/GitHub sur peu d'items) et l'utilisateur regarde le
    // nœud pendant qu'elle tourne — un retour visuel prompt compte plus ici que sur les autres
    // panneaux, consultés plus passivement.
    const interval = setInterval(refresh, pollMs);
    return () => clearInterval(interval);
  }, [refresh, pollMs]);

  const create = useCallback(
    async (input: {
      connectorType: string;
      displayName: string;
      config: Record<string, unknown>;
      positionX: number;
      positionY: number;
    }) => {
      const created = await createConnectorInstance({
        connector_type: input.connectorType,
        display_name: input.displayName,
        config: input.config,
        position_x: input.positionX,
        position_y: input.positionY,
      });
      setInstances((prev) => [...prev, created]);
      return created;
    },
    [],
  );

  const move = useCallback(async (id: number, positionX: number, positionY: number) => {
    setInstances((prev) =>
      prev.map((i) => (i.id === id ? { ...i, position_x: positionX, position_y: positionY } : i)),
    );
    await updateConnectorInstancePosition(id, positionX, positionY);
  }, []);

  const remove = useCallback(async (id: number) => {
    await deleteConnectorInstance(id);
    setInstances((prev) => prev.filter((i) => i.id !== id));
  }, []);

  const sync = useCallback(async (id: number) => {
    const updated = await syncConnectorInstance(id);
    setInstances((prev) => prev.map((i) => (i.id === id ? updated : i)));
  }, []);

  return { instances, create, move, remove, sync, refresh };
}
