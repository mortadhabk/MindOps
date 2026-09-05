import { useCallback, useEffect, useState } from "react";

import { type ActionProposal, decideProposal, fetchGatingPending } from "../lib/api";

export function useGatingQueue(pollMs = 8000, signal?: number) {
  const [proposals, setProposals] = useState<ActionProposal[]>([]);
  const [decidingId, setDecidingId] = useState<number | null>(null);

  const refresh = useCallback(async () => {
    try {
      setProposals(await fetchGatingPending());
    } catch {
      // Rafraîchissement raté : on garde la dernière liste connue plutôt que de la vider.
    }
  }, []);

  useEffect(() => {
    // `signal` change à chaque événement de chat pertinent (voir App.tsx) : un refresh immédiat
    // s'ajoute alors au polling régulier ci-dessous, sans le remplacer.
    refresh();
  }, [refresh, signal]);

  useEffect(() => {
    const interval = setInterval(refresh, pollMs);
    return () => clearInterval(interval);
  }, [refresh, pollMs]);

  const decide = useCallback(
    async (id: number, decision: "approve" | "reject") => {
      setDecidingId(id);
      try {
        await decideProposal(id, decision);
        await refresh();
      } finally {
        setDecidingId(null);
      }
    },
    [refresh],
  );

  return { proposals, decide, decidingId, refresh };
}
