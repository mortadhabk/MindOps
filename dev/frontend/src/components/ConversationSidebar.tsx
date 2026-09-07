import { AnimatePresence, motion } from "framer-motion";
import { MessageSquarePlus, MessagesSquare } from "lucide-react";

import type { ConversationSummary } from "../lib/api";
import { useConversations } from "../hooks/useConversations";
import { Panel } from "./Panel";
import { EmptyState } from "./ui";

interface ConversationSidebarProps {
  activeConversationId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  refreshSignal: number;
}

const DAY_MS = 24 * 60 * 60 * 1000;

function groupLabel(updatedAt: string): string {
  const delta = Date.now() - new Date(updatedAt).getTime();
  if (delta < DAY_MS) return "Aujourd'hui";
  if (delta < 2 * DAY_MS) return "Hier";
  if (delta < 7 * DAY_MS) return "7 derniers jours";
  return "Plus ancien";
}

const GROUP_ORDER = ["Aujourd'hui", "Hier", "7 derniers jours", "Plus ancien"];

function groupConversations(
  conversations: ConversationSummary[],
): [string, ConversationSummary[]][] {
  const buckets = new Map<string, ConversationSummary[]>();
  for (const conv of conversations) {
    const label = groupLabel(conv.updated_at);
    if (!buckets.has(label)) buckets.set(label, []);
    buckets.get(label)!.push(conv);
  }
  return GROUP_ORDER.filter((label) => buckets.has(label)).map((label) => [
    label,
    buckets.get(label)!,
  ]);
}

export function ConversationSidebar({
  activeConversationId,
  onSelect,
  onNew,
  refreshSignal,
}: ConversationSidebarProps) {
  const { conversations } = useConversations(refreshSignal);
  const groups = groupConversations(conversations);

  return (
    <Panel
      title="Conversations"
      icon={<MessagesSquare className="h-4 w-4 text-sky-400" />}
      actions={
        <button
          type="button"
          onClick={onNew}
          title="Nouvelle conversation"
          className="flex items-center gap-1 rounded-lg bg-white/5 px-2 py-1 text-[11px] font-medium text-slate-300 transition hover:bg-white/10 hover:text-white"
        >
          <MessageSquarePlus className="h-3.5 w-3.5" />
          Nouvelle
        </button>
      }
      className="h-[70vh] min-h-[560px]"
    >
      <div className="scrollbar-thin h-full overflow-y-auto px-3 py-3">
        {conversations.length === 0 && (
          <EmptyState label="Aucune conversation pour l'instant." />
        )}
        <div className="space-y-4">
          {groups.map(([label, items]) => (
            <div key={label}>
              <p className="px-2 pb-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                {label}
              </p>
              <div className="space-y-1">
                <AnimatePresence initial={false}>
                  {items.map((conv) => {
                    const isActive = conv.id === activeConversationId;
                    return (
                      <motion.button
                        key={conv.id}
                        type="button"
                        layout
                        initial={{ opacity: 0, x: -8 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        onClick={() => onSelect(conv.id)}
                        className={`group relative w-full rounded-xl px-3 py-2 text-left transition ${
                          isActive
                            ? "bg-gradient-to-r from-indigo-500/20 to-sky-400/10 text-slate-100"
                            : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
                        }`}
                      >
                        {isActive && (
                          <motion.span
                            layoutId="conversation-active-bar"
                            className="absolute inset-y-1.5 left-0 w-[3px] rounded-full bg-gradient-to-b from-indigo-400 to-sky-400"
                          />
                        )}
                        <p className="truncate pl-1.5 text-[13px] font-medium leading-tight">
                          {conv.title}
                        </p>
                      </motion.button>
                    );
                  })}
                </AnimatePresence>
              </div>
            </div>
          ))}
        </div>
      </div>
    </Panel>
  );
}
