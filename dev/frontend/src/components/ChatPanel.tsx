import { type FormEvent, type KeyboardEvent, useEffect, useRef, useState } from "react";
import { MessageSquare, Send } from "lucide-react";

import { useChat } from "../hooks/useChat";
import { MessageBubble } from "./MessageBubble";
import { Panel } from "./Panel";

export function ChatPanel({ onProposal }: { onProposal: () => void }) {
  const { messages, send, isStreaming, conversationId } = useChat(onProposal);
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const submit = async () => {
    const text = draft.trim();
    if (!text || isStreaming) return;
    setDraft("");
    await send(text);
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    void submit();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submit();
    }
  };

  return (
    <Panel
      title="Discuter avec l'agent"
      icon={<MessageSquare className="h-4 w-4 text-indigo-400" />}
      actions={
        <span className="rounded-full bg-white/5 px-2.5 py-1 font-mono text-[11px] text-slate-400">
          {conversationId ? conversationId.slice(0, 8) : "nouvelle conversation"}
        </span>
      }
      className="h-[560px]"
    >
      <div className="flex h-full flex-col">
        <div ref={scrollRef} className="scrollbar-thin flex-1 space-y-3 overflow-y-auto px-5 py-4">
          {messages.length === 0 && (
            <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-sm text-slate-500">
              <p>Pose une question à l'agent pour démarrer.</p>
              <p className="text-xs text-slate-600">
                Exemple : « Pourquoi le paiement a-t-il échoué le 28 août ? »
              </p>
            </div>
          )}
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
        </div>
        <form onSubmit={handleSubmit} className="flex gap-2 border-t border-white/10 p-4">
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            placeholder="Écris ton message…"
            className="flex-1 resize-none rounded-xl border border-white/10 bg-white/[0.03] px-3.5 py-2.5 text-sm text-slate-100 placeholder:text-slate-500 focus:border-indigo-400/50 focus:outline-none focus:ring-2 focus:ring-indigo-400/20"
          />
          <button
            type="submit"
            disabled={isStreaming || !draft.trim()}
            className="flex items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-sky-400 px-4 text-white transition disabled:cursor-not-allowed disabled:opacity-40 enabled:hover:brightness-110 enabled:active:scale-95"
          >
            <Send className="h-4 w-4" />
          </button>
        </form>
      </div>
    </Panel>
  );
}
