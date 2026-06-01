# Architecture — agentic-banking-mcp-demo

Demo for the AI-Native architecture course: evolution from a simple LLM chat to an autonomous banking agent with **Semantic Router**, **ReAct + function calling**, **MCP (stdio)**, and **Human-in-the-Loop (HITL)**.

## Runtime overview

```mermaid
flowchart LR
    subgraph CLI["REPL (rich)"]
        MEM[Session memory\nmessages[]]
        RTR[Semantic Router\nqwen3.5-35b]
        AGT[Agent loop\nqwen3-235b]
        HITL[HITL gate]
    end
    subgraph MCP["MCP banking server (stdio)"]
        T1[find_client]
        T2[get_account_balance]
        T3[prepare_transfer]
        T4[commit_transfer]
        T5[cancel_transfer]
    end
  DB[(SQLite\ndata/banking.db)]

    User --> CLI
    RTR -->|simple| LLM1[Yandex OpenAI API]
    RTR -->|agent| AGT
    AGT --> LLM2[Yandex OpenAI API]
    AGT --> MCP
    HITL --> MCP
    MCP --> OPS[operations/banking.py]
    OPS --> DB
```

## Layers (onion)

| Layer | Path | Responsibility |
|-------|------|----------------|
| Domain | `src/core/` | Models, enums, `AppError` types |
| Application | `src/operations/` | Banking use cases, no HTTP/MCP/LLM imports |
| Infrastructure | `src/adapters/` | Config, OpenAI client, router, agent loop, MCP client, tool schema conversion, memory |
| MCP interface | `src/mcp_servers/` | FastMCP tool declarations → delegate to `operations/` |
| Delivery | `src/cli/`, `main.py` | REPL, routing, HITL, rich output |

**Concurrency:** Synchronous CLI and blocking OpenAI HTTP calls are intentional (see project rules). Do not block an asyncio event loop inside this app — there is no ASGI server in v1.

**State:** Demo exception — one in-memory `messages[]` per REPL session plus persistent SQLite. Not a stateless microservice.

## External systems

| System | Usage |
|--------|--------|
| [Yandex AI Studio](https://aistudio.yandex.ru/docs/en/ai-studio/concepts/generation/models.html) | `MODEL_ROUTER`, `MODEL_AGENT` via OpenAI-compatible endpoint |
| MCP stdio | Separate process; orchestrator never imports banking SQL directly |
| SQLite | `data/banking.db`, `sqlite3`, amounts in `amount_cents` (RUB) |

Environment (see `.env.example` when added):

```ini
YC_FOLDER_ID=
YC_API_KEY=
MODEL_ROUTER=qwen3.5-35b-a3b-fp8
MODEL_AGENT=qwen3-235b-a22b-fp8
DATABASE_PATH=data/banking.db
MCP_SERVER_MODULE=src.mcp_servers.banking_server
```

## Semantic router

1. Append user message to shared `messages[]`.
2. Call **router model** with a Russian system prompt: output JSON only, field `route` ∈ `simple` | `agent`.
3. **`simple`:** one completion on router model, **no** `tools`. General FAQ; must not invent balances or execute transfers.
4. **`agent`:** run **agent loop** on heavy model with `tools` built from MCP `list_tools`.
5. **Default on parse error:** `agent`.
6. **Always `agent`:** balance queries, client lookup, transfers, any fact from DB.

## Agent loop (ReAct via function calling)

- Pattern aligned with `yandex-gpt-api/examples/tools_demo.py`: `chat.completions.create(..., tools=..., tool_choice="auto")`, append assistant + `role: tool` messages, repeat.
- **Max 8** tool rounds per invocation.
- **Observability:** rich logs **Action** (tool name + args) and **Observation** (truncated tool result). No synthetic Thought lines.
- **No** LangGraph, **no** XML `<tool_call>` parsing.
- **LLM failures:** single error surface, no retry policy.

### Agent system rules (heavy model)

- Use tools for all factual banking data.
- Transfer flow: locate accounts → `prepare_transfer` → wait for human confirmation → only then `commit_transfer`.
- Never call `commit_transfer` in the same agent invocation that called `prepare_transfer`.

## HITL flow (transfers)

```mermaid
sequenceDiagram
    participant U as User
    participant CLI as REPL
    participant A as Agent 235B
    participant MCP as MCP server

    U->>CLI: Переведи X ...
    CLI->>A: agent_loop (tools)
    A->>MCP: prepare_transfer
    MCP-->>A: pending + summary
    CLI->>CLI: Stop loop — no commit in same run
    CLI->>U: rich Panel (from prepare JSON)
    alt User denies
        U->>CLI: нет
        CLI->>MCP: cancel_transfer
    else User approves
        U->>CLI: да
        CLI->>A: new user: confirm transfer {id}
        A->>MCP: commit_transfer
        MCP-->>A: completed
        A-->>U: final message
    end
```

## MCP tools

| Tool | Effect |
|------|--------|
| `find_client` | Search by name/phone |
| `get_account_balance` | Balance in kopecks for account or client |
| `prepare_transfer` | Insert `pending` transfer, validate funds |
| `commit_transfer` | Move funds, status `completed` |
| `cancel_transfer` | Status `cancelled` for `pending` |

Tool JSON schemas for the LLM are **only** produced from MCP `list_tools` (converted to OpenAI `tools` format).

## Data model (SQLite)

- **`clients`** — `id`, `full_name`, `phone`
- **`accounts`** — `id`, `client_id`, `currency` (`RUB`), `balance_cents`
- **`transfers`** — `id`, `from_account_id`, `to_account_id`, `amount_cents`, `status` (`pending` | `completed` | `cancelled`), `created_at`

Seed personas: **Иванов**, **Петров**, **Сидоров** (see `scripts/seed_db.py` in plan).

## Testing strategy

- **Unit:** `tests/operations/` — domain rules without LLM or MCP.
- **Manual:** lecture smoke script in `docs/plans/01-banking-agent-mcp-demo.md`.

## Related docs

- Decisions log: `docs/DECISIONS.md`
- Implementation checklist: `docs/plans/01-banking-agent-mcp-demo.md`
- File map: `docs/INDEX.md`
- Status: `docs/PROGRESS.md`
