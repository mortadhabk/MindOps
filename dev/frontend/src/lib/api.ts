export type ActionStatus = "pending" | "approved" | "rejected" | "executed";

export interface ActionProposal {
  id: number;
  action_type: string;
  parameters: Record<string, unknown>;
  status: ActionStatus;
  conversation_id: string;
  result: string | null;
  created_at: string;
  decided_at: string | null;
  executed_at: string | null;
}

export interface AuditLogEntry {
  id: number;
  event_type: string;
  source: string;
  payload: Record<string, unknown>;
  result: string | null;
  created_at: string;
}

export type ChatSseEvent =
  | { type: "start"; conversationId: string }
  | { type: "delta"; text: string }
  | { type: "pending_approval"; conversationId: string; proposalId: number }
  | { type: "done" };

function parseSseChunk(raw: string): ChatSseEvent {
  let event = "message";
  let data = "";
  for (const line of raw.split("\n")) {
    if (line.startsWith("event: ")) event = line.slice(7);
    else if (line.startsWith("data: ")) data = line.slice(6);
  }
  const payload = data ? JSON.parse(data) : {};

  switch (event) {
    case "start":
      return { type: "start", conversationId: payload.conversation_id };
    case "delta":
      return { type: "delta", text: payload.text ?? "" };
    case "pending_approval":
      return {
        type: "pending_approval",
        conversationId: payload.conversation_id,
        proposalId: payload.proposal_id,
      };
    default:
      return { type: "done" };
  }
}

/** Consomme le flux SSE de POST /agent/chat "à la main" : EventSource ne supporte que GET,
 * et ce flux répond à un POST — un fetch + lecture manuelle du corps couvre les deux besoins. */
export async function streamChat(
  message: string,
  conversationId: string | null,
  onEvent: (event: ChatSseEvent) => void,
): Promise<void> {
  const response = await fetch("/agent/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ conversation_id: conversationId, message }),
  });

  if (!response.ok || !response.body) {
    throw new Error(`L'agent a répondu ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";
    for (const chunk of chunks) {
      if (chunk.trim()) onEvent(parseSseChunk(chunk));
    }
  }
}

export async function fetchHealth(): Promise<boolean> {
  try {
    const response = await fetch("/health");
    return response.ok;
  } catch {
    return false;
  }
}

export async function fetchGatingPending(): Promise<ActionProposal[]> {
  const response = await fetch("/gating/pending");
  if (!response.ok) throw new Error(`GET /gating/pending -> ${response.status}`);
  return response.json();
}

export async function decideProposal(
  proposalId: number,
  decision: "approve" | "reject",
): Promise<ActionProposal> {
  const response = await fetch(`/gating/${proposalId}/decide`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision }),
  });
  if (!response.ok) throw new Error(`POST /gating/${proposalId}/decide -> ${response.status}`);
  return response.json();
}

export async function fetchAuditLogs(eventType?: string): Promise<AuditLogEntry[]> {
  const url = eventType ? `/audit/logs?event_type=${encodeURIComponent(eventType)}` : "/audit/logs";
  const response = await fetch(url);
  if (!response.ok) throw new Error(`GET /audit/logs -> ${response.status}`);
  return response.json();
}
