import { AnimatePresence, motion } from "framer-motion";
import { Check, ShieldAlert, X } from "lucide-react";

import { useGatingQueue } from "../hooks/useGatingQueue";
import { Panel } from "./Panel";
import { EmptyState, IconButton, RefreshButton } from "./ui";

export function GatingQueue({ refreshSignal }: { refreshSignal: number }) {
  const { proposals, decide, decidingId, refresh } = useGatingQueue(8000, refreshSignal);

  return (
    <Panel
      title="File de validation"
      icon={<ShieldAlert className="h-4 w-4 text-amber-400" />}
      actions={<RefreshButton onClick={refresh} />}
      className="h-[260px]"
    >
      <div className="scrollbar-thin h-full space-y-2 overflow-y-auto p-4">
        {proposals.length === 0 && <EmptyState label="Aucune action en attente" />}
        <AnimatePresence initial={false}>
          {proposals.map((proposal) => (
            <motion.div
              key={proposal.id}
              layout
              initial={{ opacity: 0, scale: 0.97 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.97 }}
              className="rounded-xl border border-amber-400/20 bg-amber-400/[0.06] p-3"
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-xs font-semibold text-amber-200">
                  <span className="rounded-full bg-amber-400/20 px-2 py-0.5">#{proposal.id}</span>
                  {proposal.action_type}
                </div>
                <div className="flex gap-1.5">
                  <IconButton
                    label="Approuver"
                    variant="approve"
                    disabled={decidingId === proposal.id}
                    onClick={() => decide(proposal.id, "approve")}
                    icon={<Check className="h-3.5 w-3.5" />}
                  />
                  <IconButton
                    label="Rejeter"
                    variant="reject"
                    disabled={decidingId === proposal.id}
                    onClick={() => decide(proposal.id, "reject")}
                    icon={<X className="h-3.5 w-3.5" />}
                  />
                </div>
              </div>
              <pre className="scrollbar-thin mt-2 max-h-16 overflow-auto whitespace-pre-wrap break-words font-mono text-[11px] text-amber-100/70">
                {JSON.stringify(proposal.parameters, null, 2)}
              </pre>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </Panel>
  );
}
