interface EventTypeMeta {
  label: string;
  dot: string;
}

const EVENT_TYPE_META: Record<string, EventTypeMeta> = {
  "agent.llm_call": { label: "Appel LLM", dot: "bg-sky-400" },
  "agent.action_proposed": { label: "Action proposée", dot: "bg-amber-400" },
  "gating.decision": { label: "Décision", dot: "bg-emerald-400" },
};

export function eventTypeMeta(eventType: string): EventTypeMeta {
  return EVENT_TYPE_META[eventType] ?? { label: eventType, dot: "bg-slate-400" };
}
