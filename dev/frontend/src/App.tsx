import clsx from "clsx";
import { useCallback, useState } from "react";

import { AdminView } from "./admin/AdminView";
import { ChatPanel } from "./components/ChatPanel";
import { type ActiveTab, Header } from "./components/Header";
import { StudioView } from "./studio/StudioView";

export default function App() {
  const [activeTab, setActiveTab] = useState<ActiveTab>("assistant");
  // Incrémenté à chaque événement de chat pertinent (pending_approval / done) pour déclencher
  // un rafraîchissement immédiat de la file de gating et de l'audit, en plus de leur polling.
  const [refreshSignal, setRefreshSignal] = useState(0);
  const bumpRefresh = useCallback(() => setRefreshSignal((n) => n + 1), []);

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
          <main className="mx-auto max-w-3xl px-6 pb-10">
            <ChatPanel onProposal={bumpRefresh} />
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
