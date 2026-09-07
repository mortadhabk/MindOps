import clsx from "clsx";
import { useCallback, useState } from "react";

import { AdminView } from "./admin/AdminView";
import { ChatPanel } from "./components/ChatPanel";
import { ConversationSidebar } from "./components/ConversationSidebar";
import { type ActiveTab, Header } from "./components/Header";
import { useChat } from "./hooks/useChat";
import { StudioView } from "./studio/StudioView";

export default function App() {
  const [activeTab, setActiveTab] = useState<ActiveTab>("assistant");
  // Incrémenté à chaque événement de chat pertinent (start / pending_approval / done) pour
  // déclencher un rafraîchissement immédiat de la sidebar de conversations, de la file de
  // gating et de l'audit, en plus de leur polling respectif.
  const [refreshSignal, setRefreshSignal] = useState(0);
  const bumpRefresh = useCallback(() => setRefreshSignal((n) => n + 1), []);
  const chat = useChat(bumpRefresh);

  return (
    <div className="relative min-h-screen bg-surface-950">
      <div className="pointer-events-none fixed inset-0 bg-grid-glow" />
      <div
        className={clsx(
          "relative mx-auto transition-[max-width]",
          activeTab === "studio" ? "max-w-[1600px]" : "max-w-6xl",
        )}
      >
        <Header activeTab={activeTab} onTabChange={setActiveTab} />
        {activeTab === "assistant" && (
          <main className="mx-auto grid max-w-5xl gap-5 px-6 pb-10 lg:grid-cols-[260px_1fr]">
            <ConversationSidebar
              activeConversationId={chat.conversationId}
              onSelect={chat.openConversation}
              onNew={chat.startNewConversation}
              refreshSignal={refreshSignal}
            />
            <ChatPanel chat={chat} />
          </main>
        )}
        {activeTab === "studio" && (
          <main className="px-6 pb-10">
            <StudioView />
          </main>
        )}
        {activeTab === "admin" && (
          <main className="px-6 pb-10">
            <AdminView refreshSignal={refreshSignal} />
          </main>
        )}
      </div>
    </div>
  );
}
