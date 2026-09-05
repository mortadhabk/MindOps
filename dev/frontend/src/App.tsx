import clsx from "clsx";
import { useCallback, useState } from "react";

import { AuditLogPanel } from "./components/AuditLogPanel";
import { ChatPanel } from "./components/ChatPanel";
import { GatingQueue } from "./components/GatingQueue";
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
        {activeTab === "assistant" ? (
          <main className="grid gap-5 px-6 pb-10 lg:grid-cols-[1.35fr_1fr]">
            <ChatPanel onProposal={bumpRefresh} />
            <div className="flex flex-col gap-5">
              <GatingQueue refreshSignal={refreshSignal} />
              <AuditLogPanel refreshSignal={refreshSignal} />
            </div>
          </main>
        ) : (
          <main className="px-6 pb-10">
            <StudioView />
          </main>
        )}
      </div>
    </div>
  );
}
