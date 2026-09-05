import { useCallback, useEffect, useState } from "react";

import { type AuditLogEntry, fetchAuditLogs } from "../lib/api";

export function useAuditLog(pollMs = 8000, signal?: number) {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [filter, setFilter] = useState("");

  const refresh = useCallback(async () => {
    try {
      setLogs(await fetchAuditLogs(filter || undefined));
    } catch {
      // Rafraîchissement raté : on garde la dernière liste connue plutôt que de la vider.
    }
  }, [filter]);

  useEffect(() => {
    refresh();
  }, [refresh, signal]);

  useEffect(() => {
    const interval = setInterval(refresh, pollMs);
    return () => clearInterval(interval);
  }, [refresh, pollMs]);

  return { logs, filter, setFilter, refresh };
}
