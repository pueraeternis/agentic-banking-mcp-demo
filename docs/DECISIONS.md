# Architectural decisions

Chronological journal. New entries are appended at the end.

## [2026-06-01] Scope and user interface

**Decision:** Single entry point — interactive REPL in the terminal with `rich` for observability. No separate web UI, no standalone `chat_cli tool` for invoking MCP tools without the agent.

**Reason:** Demo targets a live lecture; a console REPL clearly shows Thought/Action/Observation-style steps (here: Action/Observation only) and keeps the stack minimal.

**Rejected:** REPL plus auxiliary debug CLI for tools; any non-terminal UI.

## [2026-06-01] Language and models

**Decision:** System prompts and agent replies in Russian. Two Yandex Cloud models via OpenAI-compatible API ([model catalog](https://aistudio.yandex.ru/docs/en/ai-studio/concepts/generation/models.html)): `MODEL_ROUTER=qwen3.5-35b-a3b-fp8` (semantic router and simple chat), `MODEL_AGENT=qwen3-235b-a22b-fp8` (ReAct with tools). URI format: `gpt://{YC_FOLDER_ID}/{model_slug}/latest`. LLM errors: one user-facing message and rich error output, no automatic retries.

**Reason:** Course audience is Russian-speaking; light/heavy split illustrates semantic routing; slugs match the organization’s AI Studio deployment.

**Rejected:** English prompts; single model for all paths; retry with backoff on 429/network.

## [2026-06-01] MCP transport and tool schemas

**Decision:** Banking logic is exposed only through a separate MCP server process (stdio). The orchestrator uses `tools/list` and `tools/call` only. OpenAI function-calling schemas are derived exclusively from MCP `list_tools` (no duplicated JSON in the agent). Five tools: `find_client`, `get_account_balance`, `prepare_transfer`, `commit_transfer`, `cancel_transfer`.

**Reason:** Lecture must show the MCP protocol on the wire; a single source of truth for tool contracts avoids drift between MCP and the LLM.

**Rejected:** In-process FastMCP calls without subprocess; hand-maintained OpenAI tool schemas parallel to MCP; extended tool set (e.g. `list_recent_transfers`) in v1.

## [2026-06-01] Semantic router

**Decision:** Light model returns strict JSON: `{ "route": "simple" | "agent" }`. Two classes only: `simple` — no tools; `agent` — heavy model with full tool set. Balance and any DB-backed facts (e.g. “how much does Ivanov have?”) always route to `agent`. On JSON parse failure, default to `agent`. One shared `messages[]` per REPL session for both routes.

**Reason:** Clear lecture narrative (cheap path vs agent path); routing balance questions to tools prevents hallucinated balances; shared memory preserves dialog context across route switches.

**Rejected:** Regex-only router; three-way routing (`chitchat` / read / write); separate message histories per route; answering balance from `simple` without tools.

## [2026-06-01] ReAct and observability

**Decision:** Agent loop uses OpenAI function calling only (same pattern as `yandex-gpt-api/examples/tools_demo.py`), no XML `<tool_call>` parsing. Maximum 8 ReAct iterations per agent invocation. Rich console shows Action and Observation only (no synthetic “Thought” lines). No LangGraph.

**Reason:** Yandex endpoint supports function calling; a plain `while` loop is easier to read on a projector than a graph framework for this demo size.

**Rejected:** Textual ReAct markers; unlimited iterations; displaying model “reasoning” as Thought; LangGraph for HITL/agent.

## [2026-06-01] Transfers and human-in-the-loop

**Decision:** Two-phase transfer in the domain: `prepare_transfer` creates `pending` without moving money; `commit_transfer` completes; `cancel_transfer` cancels `pending`. After a successful `prepare_transfer`, the CLI stops the ReAct loop and shows a rich Panel from the tool JSON (amount, from/to, `transfer_id`). On user denial, CLI calls `cancel_transfer` via MCP without LLM. On user approval (“да”), a new user message is appended and a new agent run on the heavy model calls `commit_transfer` (model invokes commit, not the CLI directly).

**Reason:** HITL is visible and deterministic on reject; commit still demonstrates tool use by the agent after explicit human consent; prepare/commit separation matches real banking staging.

**Rejected:** Single `execute_transfer` with CLI-only gate; CLI calling `commit_transfer` after approval; leaving pending rows uncancelled on reject; showing live balance re-fetch in the HITL panel (v1 uses prepare summary only).

## [2026-06-01] Data layer and session state

**Decision:** SQLite file `data/banking.db`, synchronous `sqlite3`. Amounts stored as integer `amount_cents` in RUB only. Seed clients: Ivanov, Petrov, Sidorov (2–3 accounts total). Business rules live in `src/operations/`; MCP handlers delegate only. Explicit demo exception to “stateless services”: in-memory chat session plus SQLite, no Redis.

**Reason:** Zero external dependencies for the DB; integer cents avoid float bugs; fixed personas make live demos predictable.

**Rejected:** `aiosqlite` in v1; random generated seed data; rubles as floats; Redis session store.

## [2026-06-01] Delivery and testing

**Decision:** Ship the full stack in one phase (router + agent + MCP + HITL) behind `main` / REPL. Unit tests on `operations/` only (transfer happy path, insufficient funds, cancel, invalid commit), no LLM in tests.

**Reason:** Single runnable demo for the webinar; domain tests give confidence without flaky API calls.

**Rejected:** Feature-flagged partial modes; git tags per wave as the primary delivery mechanism; skipping unit tests.

## [2026-06-01] Repository root and database paths

**Decision:** **Repository root** is the project directory that contains `pyproject.toml` and `main.py` (not `src/`, not `data/`). Any relative path from config (e.g. `DATABASE_PATH=data/banking.db`) is normalized once to an **absolute** path: `repo_root / relative_path`. MCP stdio subprocess: `cwd=repo_root`, `PYTHONPATH=repo_root/src`, env `DATABASE_PATH=<absolute>`. Fix incorrect root detection in `mcp_client` (was one level too shallow → `cwd` pointed at `src/`, so SQLite looked for `src/data/banking.db`).

**Reason:** REPL preflight used the shell’s cwd and found `data/banking.db`; MCP subprocess used a wrong working directory with the same relative string → `unable to open database file`. Integration tests passed because they pass an absolute temp DB path.

**Rejected:** Treating `src/` or `data/` as the repository root; passing relative `DATABASE_PATH` into MCP without resolving against `repo_root`; depending on the user’s terminal cwd for DB access.

## [2026-06-01] Bank services catalog (MCP resource)

**Decision:** Demo bank services live in a versioned file `data/bank_services.md` (Russian, fixed catalog for the lecture). Expose it as an MCP **resource** `banking://services` (FastMCP resource handler reads the file via `repo_root`). Router: questions about **this bank’s** services/products → `route=agent` (not `simple`). Orchestrator calls MCP `resources/read` for that URI and injects the text into the session before the heavy model answers (no invented generic “any bank” FAQ). Extend `mcp_client` with `read_resource`; observability may log **Resource** read in rich output.

**Reason:** Plan 01 `simple` path produced hallucinated generic banking lists; the lecture should show MCP resources as a first-class primitive alongside tools.

**Rejected:** Leaving “какие услуги у банка?” on `simple` without MCP; duplicating the same content only in system prompt without a resource; a parallel `list_bank_services` tool instead of resource (unless resource read proves insufficient in implementation).

## [2026-06-01] File logging and Yandex API diagnostics

**Decision:** Add **session file logging** for the REPL orchestrator: one log file per run under `logs/` (gitignored), configured centrally (e.g. `src/adapters/logging_setup.py`). **Console (rich):** unchanged for the lecture — Action/Observation/Resource, short user-facing LLM error text. **File:** full trace for root-cause analysis — each user turn, route (`simple` \| `agent`), MCP `call_tool` / `read_resource`, agent steps; on `OpenAIError` / `APIError` log **status_code**, **message**, and **response body** from Yandex plus phase (`router` \| `simple` \| `agent` step N) and model URI. Level from env `LOG_LEVEL` (default `INFO`). Do **not** log `YC_API_KEY` or `Authorization` headers; on INFO truncate large payloads (e.g. bank catalog inject: size + optional preview); full `messages[]` dump only at `DEBUG` with length cap. Optional console hint: path to the current log file after LLM errors.

**Reason:** After plan 02, a long session (catalog resource + long assistant reply) caused router LLM calls to fail while a fresh REPL with the same balance question succeeded — failures were invisible because `repl.py` caught API errors without logging Yandex’s response. File logs make production-debugging possible without noisy terminals.

**Rejected:** Logging only to stderr with default `logging.WARNING`; printing full API bodies to the rich console during the lecture; committing log files; separate MCP subprocess log file in v1 (orchestrator-side MCP client logging is enough); automatic retries on 429 (unchanged).
