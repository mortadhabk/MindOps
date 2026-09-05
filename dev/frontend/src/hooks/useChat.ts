import { useCallback, useRef, useState } from "react";

import { generateId } from "../lib/id";
import { streamChat } from "../lib/api";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  pending?: boolean;
}

export function useChat(onProposal: () => void) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const conversationIdRef = useRef<string | null>(null);

  const send = useCallback(
    async (text: string) => {
      const assistantId = generateId();
      setMessages((prev) => [
        ...prev,
        { id: generateId(), role: "user", text },
        { id: assistantId, role: "assistant", text: "", pending: true },
      ]);
      setIsStreaming(true);

      const patch = (updater: (message: ChatMessage) => ChatMessage) =>
        setMessages((prev) => prev.map((m) => (m.id === assistantId ? updater(m) : m)));

      try {
        await streamChat(text, conversationIdRef.current, (event) => {
          switch (event.type) {
            case "start":
              conversationIdRef.current = event.conversationId;
              setConversationId(event.conversationId);
              break;
            case "delta":
              patch((m) => ({ ...m, text: m.text + event.text }));
              break;
            case "pending_approval":
              patch((m) => ({
                ...m,
                pending: false,
                text:
                  m.text +
                  `\n\n⏸ Action en attente de validation — proposition #${event.proposalId}.`,
              }));
              onProposal();
              break;
            case "done":
              patch((m) => ({ ...m, pending: false }));
              onProposal();
              break;
          }
        });
      } catch (error) {
        patch((m) => ({ ...m, pending: false, text: `[erreur : ${(error as Error).message}]` }));
      } finally {
        setIsStreaming(false);
      }
    },
    [onProposal],
  );

  return { messages, send, isStreaming, conversationId };
}
