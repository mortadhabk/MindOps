import { useCallback, useEffect, useState } from "react";

import { type ConversationSummary, fetchConversations } from "../lib/api";

export function useConversations(signal?: number) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);

  const refresh = useCallback(async () => {
    try {
      setConversations(await fetchConversations());
    } catch {
      // Rafraîchissement raté : on garde la dernière liste connue plutôt que de la vider.
    }
  }, []);

  useEffect(() => {
    // `signal` change à chaque tour de chat (voir useChat.ts) : la sidebar suit sans polling.
    refresh();
  }, [refresh, signal]);

  return { conversations, refresh };
}
