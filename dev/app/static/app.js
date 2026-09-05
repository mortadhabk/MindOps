let conversationId = null;

const messagesEl = document.getElementById("messages");
const conversationIdEl = document.getElementById("conversation-id");
const chatForm = document.getElementById("chat-form");
const messageInput = document.getElementById("message-input");
const sendBtn = document.getElementById("send-btn");
const gatingBody = document.getElementById("gating-body");
const auditBody = document.getElementById("audit-body");
const auditFilter = document.getElementById("audit-filter");

function appendMessage(role, text) {
  const el = document.createElement("div");
  el.className = `message ${role}`;
  el.textContent = text;
  messagesEl.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return el;
}

function parseSseEvent(raw) {
  let event = "message";
  let data = "";
  for (const line of raw.split("\n")) {
    if (line.startsWith("event: ")) event = line.slice(7);
    else if (line.startsWith("data: ")) data = line.slice(6);
  }
  let payload = {};
  try {
    payload = JSON.parse(data);
  } catch {
    // ligne data absente ou vide : payload reste {}
  }
  return { event, payload };
}

async function sendMessage(text) {
  appendMessage("user", text);
  const assistantEl = appendMessage("assistant", "");

  const response = await fetch("/agent/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ conversation_id: conversationId, message: text }),
  });

  if (!response.ok || !response.body) {
    assistantEl.textContent = `[erreur : l'agent a répondu ${response.status}]`;
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop(); // dernier fragment potentiellement incomplet, conservé pour la suite
    for (const chunk of chunks) {
      if (!chunk.trim()) continue;
      const { event, payload } = parseSseEvent(chunk);
      if (event === "start") {
        conversationId = payload.conversation_id;
        conversationIdEl.textContent = conversationId;
      } else if (event === "delta") {
        assistantEl.textContent += payload.text ?? "";
        messagesEl.scrollTop = messagesEl.scrollHeight;
      } else if (event === "pending_approval") {
        assistantEl.textContent +=
          `\n\n[action en attente de validation — proposition #${payload.proposal_id}, ` +
          "voir la file de validation ci-contre]";
        refreshGating();
      } else if (event === "done") {
        refreshGating();
        refreshAudit();
      }
    }
  }
}

chatForm.addEventListener("submit", async (evt) => {
  evt.preventDefault();
  const text = messageInput.value.trim();
  if (!text) return;
  messageInput.value = "";
  sendBtn.disabled = true;
  try {
    await sendMessage(text);
  } finally {
    sendBtn.disabled = false;
    messageInput.focus();
  }
});

function renderEmptyRow(tbody, colspan, label) {
  tbody.innerHTML = `<tr><td colspan="${colspan}" class="empty">${label}</td></tr>`;
}

async function refreshGating() {
  const response = await fetch("/gating/pending");
  const items = await response.json();
  gatingBody.innerHTML = "";
  if (items.length === 0) {
    renderEmptyRow(gatingBody, 4, "Aucune action en attente");
    return;
  }
  for (const item of items) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${item.id}</td>
      <td>${item.action_type}</td>
      <td><pre>${JSON.stringify(item.parameters, null, 2)}</pre></td>
      <td class="actions">
        <button type="button" class="approve" data-id="${item.id}">Approuver</button>
        <button type="button" class="reject" data-id="${item.id}">Rejeter</button>
      </td>`;
    gatingBody.appendChild(tr);
  }
  gatingBody.querySelectorAll("button.approve").forEach((btn) =>
    btn.addEventListener("click", () => decide(btn.dataset.id, "approve"))
  );
  gatingBody.querySelectorAll("button.reject").forEach((btn) =>
    btn.addEventListener("click", () => decide(btn.dataset.id, "reject"))
  );
}

async function decide(proposalId, decision) {
  await fetch(`/gating/${proposalId}/decide`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision }),
  });
  await refreshGating();
  await refreshAudit();
}

async function refreshAudit() {
  const eventType = auditFilter.value;
  const url = eventType ? `/audit/logs?event_type=${encodeURIComponent(eventType)}` : "/audit/logs";
  const response = await fetch(url);
  const items = await response.json();
  auditBody.innerHTML = "";
  if (items.length === 0) {
    renderEmptyRow(auditBody, 4, "Aucun événement");
    return;
  }
  for (const item of items.slice(0, 50)) {
    const tr = document.createElement("tr");
    const timestamp = new Date(item.created_at + "Z").toLocaleString("fr-FR");
    tr.innerHTML = `
      <td>${timestamp}</td>
      <td>${item.event_type}</td>
      <td>${item.source}</td>
      <td><pre>${JSON.stringify(item.payload)}</pre></td>`;
    auditBody.appendChild(tr);
  }
}

document.querySelectorAll("button[data-refresh]").forEach((btn) => {
  btn.addEventListener("click", () => {
    if (btn.dataset.refresh === "gating") refreshGating();
    if (btn.dataset.refresh === "audit") refreshAudit();
  });
});
auditFilter.addEventListener("change", refreshAudit);

refreshGating();
refreshAudit();
setInterval(refreshGating, 8000);
setInterval(refreshAudit, 8000);
