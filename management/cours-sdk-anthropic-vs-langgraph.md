# SDK Anthropic vs LangGraph — comprendre la différence avant de choisir

Contexte : pour l'Epic 3 (orchestrateur agentique) de MindOps, il faut une boucle qui envoie des messages au LLM, laisse le LLM décider d'appeler un outil (`search_knowledge` pour l'instant, `send_email` plus tard derrière le gating), exécute l'outil, renvoie le résultat au LLM, jusqu'à une réponse finale. Deux façons de construire ça : écrire la boucle soi-même avec le SDK Anthropic officiel, ou la déléguer à LangGraph. Ce document explique les deux en détail pour que le choix soit informé, pas arbitraire.

---

## 1. Le SDK Anthropic — les bases

Le SDK Anthropic (`pip install anthropic`) est un client HTTP typé autour de l'**API Messages**. Il n'a aucune notion d'"agent" ou de "boucle" — il t'envoie un tableau de messages, tu reçois une réponse, un point c'est tout. Toute la logique d'orchestration est à ta charge.

### 1.1 Le concept central : les messages

Une conversation est une liste de messages, chacun avec un `role` (`user` ou `assistant`) et un `content` qui est une liste de **blocks** :

```python
messages = [
    {"role": "user", "content": [{"type": "text", "text": "Pourquoi le paiement échoue ?"}]},
]
```

### 1.2 Le function calling ("tool use")

Tu déclares tes outils comme des schémas JSON (nom, description, `input_schema`) :

```python
tools = [
    {
        "name": "search_knowledge",
        "description": "Cherche dans la base de connaissances les fragments pertinents.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    }
]

response = client.messages.create(
    model="claude-sonnet-5",
    max_tokens=1024,
    messages=messages,
    tools=tools,
)
```

La réponse a un `stop_reason` qui te dit *pourquoi* le modèle s'est arrêté :

- `"end_turn"` → réponse finale, rien à faire de plus.
- `"tool_use"` → le modèle veut appeler un outil ; `response.content` contient un block `{"type": "tool_use", "id": ..., "name": "search_knowledge", "input": {"query": "..."}}`.
- `"max_tokens"` → tronqué, à gérer comme une erreur/limite.

Si c'est `"tool_use"`, **toi** tu exécutes la fonction Python correspondante, puis tu renvoies le résultat comme un nouveau message `user` contenant un block `tool_result` référencé par `tool_use_id` :

```python
messages.append({"role": "assistant", "content": response.content})
messages.append({
    "role": "user",
    "content": [{
        "type": "tool_result",
        "tool_use_id": tool_use_block.id,
        "content": result_text,
    }],
})
# on rappelle client.messages.create(...) avec ces messages enrichis
```

### 1.3 La boucle agentique — tu l'écris toi-même

```python
def run_agent(messages, tools, max_iterations=5):
    for _ in range(max_iterations):
        response = client.messages.create(
            model=settings.llm_model, max_tokens=1024, messages=messages, tools=tools
        )
        if response.stop_reason != "tool_use":
            return response  # réponse finale
        messages.append({"role": "assistant", "content": response.content})
        for block in response.content:
            if block.type == "tool_use":
                result = execute_tool(block.name, block.input)
                messages.append({
                    "role": "user",
                    "content": [{"type": "tool_result", "tool_use_id": block.id, "content": result}],
                })
    raise RuntimeError("Nombre maximum d'itérations atteint")
```

C'est exactement ce que décrit ton backlog ("boucle : envoi au LLM → si tool_use, exécution puis renvoi → jusqu'à réponse finale, plafonné"). Rien de magique — une boucle `for`, un `if`, un dictionnaire qui grossit.

### 1.4 Le streaming

L'API Messages a un mode `stream=True` qui renvoie des événements SSE (`message_start`, `content_block_delta` avec des deltas de texte token par token, `message_stop`, etc.). Pour streamer vers ton `/agent/chat`, tu relaies ces deltas directement dans ta propre réponse SSE FastAPI. Si un `tool_use` survient en cours de stream, il faut gérer un `input_json_delta` (les arguments de l'outil arrivent aussi en streaming, à ré-assembler).

### 1.5 Avantages

- **Zéro couche d'abstraction** : ce que tu lis dans le code est exactement ce qui se passe sur le réseau. Debugger = lire un dict JSON.
- **Dépendance minimale** : une seule lib, stable, mise à jour au rythme de l'API elle-même (pas de retard d'une lib tierce sur une nouvelle fonctionnalité Anthropic).
- **Contrôle total** immédiat : le cap d'itérations, le format des erreurs, la structure de `agent/memory.py` — tout est à toi, donc rien ne te surprend.
- **Correspond 1:1** à ce que ton backlog décrit déjà (US-302 est littéralement la boucle ci-dessus).

### 1.6 Inconvénients

- **Tu codes tout toi-même** : la persistance de l'historique (`agent/memory.py`), la gestion des erreurs de tool call, un futur "interrupt" pour le gating (Epic 4) — rien n'est fourni, tu l'écris à la main.
- **Pas de primitives multi-agents** : si un jour tu veux plusieurs agents qui se coordonnent, tu repars de zéro.
- **Couplage au fournisseur** : si tu changes de LLM (ex: un jour tester un modèle OpenAI en parallèle), le format des messages/tools/streaming est spécifique à Anthropic — à réécrire.
- **Pas d'observabilité prête à l'emploi** : pas de trace visuelle de "quel nœud a fait quoi", juste tes logs.

---

## 2. LangGraph — les bases

LangGraph (`pip install langgraph`) est une librairie (du même éditeur que LangChain, mais indépendante et bas niveau) pour construire un agent comme une **machine à états** — un graphe de nœuds et d'arêtes, plutôt qu'une boucle `for` écrite à la main.

### 2.1 Le concept central : `State`, `Node`, `Edge`

**State** — une structure partagée (TypedDict ou Pydantic) qui circule entre les nœuds :

```python
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]  # "reducer" : accumule au lieu d'écraser
```

**Node** — une fonction qui reçoit le state et retourne un state partiel à fusionner :

```python
def call_model(state: AgentState) -> dict:
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response]}

def call_tools(state: AgentState) -> dict:
    last = state["messages"][-1]
    results = [execute_tool(tc) for tc in last.tool_calls]
    return {"messages": results}
```

**Edge** — relie les nœuds, éventuellement de façon conditionnelle :

```python
from langgraph.graph import StateGraph, END

graph = StateGraph(AgentState)
graph.add_node("call_model", call_model)
graph.add_node("call_tools", call_tools)
graph.set_entry_point("call_model")
graph.add_conditional_edges(
    "call_model",
    lambda state: "call_tools" if state["messages"][-1].tool_calls else END,
)
graph.add_edge("call_tools", "call_model")  # retour à la boucle

app = graph.compile()
app.invoke({"messages": [("user", "Pourquoi le paiement échoue ?")]})
```

Ce graphe compilé **est** la boucle agentique — LangGraph exécute les nœuds selon les arêtes jusqu'à atteindre `END`, avec un cap d'itérations intégré (`recursion_limit`).

### 2.2 La persistance : le Checkpointer

LangGraph a une notion native de **checkpoint** : tu attaches un `checkpointer` (en mémoire, SQLite, Postgres...) au graphe, et chaque `state` est sauvegardé automatiquement, indexé par un `thread_id`. Concrètement, ça **remplace** ton `agent/memory.py` fait main — pas besoin d'un dict Python qui grossit, LangGraph s'en charge et peut même le faire persister en base.

### 2.3 Les Interrupts — le point le plus pertinent pour toi

LangGraph permet de marquer un nœud comme **interruptible** : l'exécution du graphe s'arrête *avant* (ou après) ce nœud, renvoie le contrôle à ton code, et attend une décision externe (approuver/rejeter) avant de reprendre — via un objet `Command(resume=...)`.

C'est exactement le pattern de gating que ton Epic 4 décrit à la main (`ActionProposal`, statut `pending`, `POST /gating/{id}/decide`) : avec LangGraph, un outil "sensible" comme `send_email` pourrait être un nœud avec `interrupt_before`, et la validation humaine reprendrait le graphe pile où il s'est arrêté — sans avoir à recoder toi-même la file d'attente et la reprise d'exécution.

### 2.4 Avantages

- **Boucle explicite et visualisable** : le graphe peut être exporté en diagramme (Mermaid), utile pour expliquer le comportement de l'agent à quelqu'un qui ne lit pas le code.
- **Persistance "gratuite"** via les checkpointers — remplace `agent/memory.py`.
- **Interrupts natifs** — correspond presque exactement au besoin de gating de l'Epic 4, sans réinventer la file de validation à la main.
- **Agnostique du LLM** — le graphe orchestre des appels à un modèle abstrait (`langchain-anthropic`, `langchain-openai`, ...) ; changer de fournisseur touche une ligne, pas la boucle.
- **Écosystème** : `create_react_agent` (agent ReAct préconstruit pour aller vite), LangSmith pour tracer/débugger visuellement chaque étape du graphe.

### 2.5 Inconvénients

- **Dépendance et vocabulaire supplémentaires** : `StateGraph`, `reducers` (comme `add_messages`), `Command`, `checkpointer` — une couche de concepts à apprendre avant d'être productif.
- **Abstraction qui masque le détail** : quand quelque chose ne marche pas comme prévu, tu débugges à travers la lib, pas juste un dict JSON brut.
- **Overhead pour un cas simple** : avec un seul outil (`search_knowledge`) et pas encore de gating implémenté, le graphe se réduit à peu près à la même boucle que la version SDK — pour un coût de compréhension plus élevé.
- **Rythme de breaking changes historiquement élevé** — API qui a bougé plusieurs fois ces dernières années, à surveiller si tu fixes une version.
- **Risque de sur-ingénierie sur un POC** : construire un graphe pour un seul chemin linéaire (LLM → tool → LLM → fin) est un peu comme construire un rond-point pour une rue à sens unique.

---

## 3. Tableau comparatif

| | SDK Anthropic (boucle manuelle) | LangGraph |
|---|---|---|
| Dépendances | 1 (`anthropic`) | 2+ (`langgraph`, `langchain-anthropic`, ...) |
| Courbe d'apprentissage | Faible (juste l'API Messages) | Moyenne (State/Node/Edge/Checkpointer) |
| Contrôle sur la boucle | Total, mais tout est à écrire | Élevé, avec primitives prêtes |
| Persistance de l'historique | À coder (`agent/memory.py`) | Fournie (checkpointer) |
| Human-in-the-loop / gating | À coder entièrement (Epic 4) | Primitive native (`interrupt`) |
| Portabilité multi-LLM | Faible (couplé à l'API Anthropic) | Élevée (abstraction LangChain) |
| Observabilité | Logs maison | LangSmith, export du graphe |
| Adapté à | 1 outil, boucle linéaire, POC | Plusieurs outils/agents, gating natif, besoin de visualiser/tracer |

---

## 4. Recommandation pour MindOps, maintenant

Aujourd'hui : **un seul outil** (`search_knowledge`, en lecture seule, pas de gating), et le module `gating` n'existe pas encore (Epic 4 vient après). Dans ce contexte, LangGraph n'apporte quasiment rien de plus qu'une boucle `for` de 15 lignes avec le SDK Anthropic — mais coûte une dépendance et un vocabulaire à apprendre pour toi et n'importe qui relira le code plus tard.

Le calcul change **si/quand** tu arrives à l'Epic 4 (gating) : à ce moment-là, le mécanisme d'`interrupt` de LangGraph pourrait remplacer une bonne partie de `gating/queue_service.py` écrit à la main. Ça vaudra le coup de reposer la question à ce moment précis, avec le vrai besoin sous les yeux plutôt qu'en anticipation.

**Pour l'Epic 3 tel qu'il est écrit dans le backlog** : SDK Anthropic direct, boucle manuelle. Simple, correspond exactement aux critères d'acceptation (US-302), et rien n'empêche de migrer vers LangGraph plus tard si le besoin de gating avancé se confirme — le contrat externe (`POST /agent/chat`) ne change pas, seule l'implémentation interne de `orchestrator.py` bougerait.
