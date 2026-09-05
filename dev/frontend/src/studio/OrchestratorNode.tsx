import { Handle, Position } from "@xyflow/react";
import { Cpu } from "lucide-react";

export function OrchestratorNode() {
  return (
    <div className="flex w-48 flex-col items-center gap-1 rounded-2xl border border-indigo-400/30 bg-gradient-to-br from-indigo-500/20 to-sky-400/10 px-4 py-5 text-center shadow-glow backdrop-blur-xl">
      <Cpu className="h-5 w-5 text-indigo-300" />
      <div className="text-sm font-semibold text-white">Orchestrateur</div>
      <div className="text-[10px] text-indigo-200/70">agent + RAG</div>
      <Handle type="target" position={Position.Left} className="!bg-indigo-400" />
    </div>
  );
}
