# Plan 03 — File logging + Yandex API diagnostics

**Goal:** Persist a per-session trace under `logs/` so LLM/MCP failures (especially Yandex `APIError` body) are diagnosable without changing the lecture UX in the terminal.

**References:** `docs/DECISIONS.md` (entry 2026-06-01 file logging), `docs/ARCHITECTURE.md` (observability section).

**Depends on:** plan 02 committed (`7728056` or later).

**Background (RCA):** Long REPL session after `banking://services` inject + long assistant reply → next turn failed at **router** (`route=` never printed). Fresh REPL with the same balance question worked. Root cause unknown without API error details; motivates this plan.

---

## 0. Documentation (this session)

- [x] Append decisions to `docs/DECISIONS.md`
- [x] Create this plan; set `docs/PROGRESS.md` active plan
- [x] Update `docs/ARCHITECTURE.md`, `docs/INDEX.md`

## 1. Log directory and setup

- [x] `.gitignore` — `logs/` (entire directory)
- [x] `src/adapters/logging_setup.py` — `setup_logging() -> Path`:
  - resolve `logs/` under `repo_root` (`get_repo_root()`)
  - create dir if missing
  - filename `repl-{timestamp}.log` (local time, safe for filesystem)
  - `logging.basicConfig` or root logger: **FileHandler** (UTF-8), format `%(asctime)s %(levelname)s %(name)s %(message)s`
  - level from `LOG_LEVEL` env (`INFO` default); invalid value → `INFO` + warning in log
  - do not add a second console handler (rich stays the UI)
- [x] `src/adapters/llm_logging.py` (or helpers in `logging_setup.py`) — `log_llm_error(exc, *, phase, model)`, `log_llm_request(phase, model, message_count, context_chars)`, `log_llm_response(phase, model, usage, content_len)`; redact secrets; truncate text helpers

## 2. Instrument orchestrator

- [x] `src/cli/repl.py` — call `setup_logging()` at start; log session start (db path, models, log file path); log each user turn; on `(OpenAIError, APIError)` call `log_llm_error` + optional dim hint with log path (keep user message short)
- [x] `src/adapters/router.py` — log before/after router and simple chat completions; log parse fallback to `agent`
- [x] `src/adapters/agent_loop.py` — log each agent step (model, tool names or final text length); log max-steps warning (already exists, ensure file receives it)
- [x] `src/adapters/mcp_client.py` — log connect/close, `call_tool`, `read_resource`, `list_resources` (uri/name, arg keys; observation truncated e.g. 500 chars on INFO)
- [x] `src/cli/repl.py` — log resource inject: uri + catalog byte/char size (not full catalog on INFO)

## 3. Config and examples

- [x] `.env.example` — `LOG_LEVEL=INFO` with one-line comment
- [x] `README.md` — short note: logs in `logs/`, gitignored, raise `LOG_LEVEL=DEBUG` for verbose LLM context

## 4. Tests

- [x] `tests/adapters/test_logging_setup.py` — `setup_logging()` creates file under tmp repo layout or tmp_path; handler attached; no API key in formatted output from `log_llm_error` fixture
- [ ] Manual smoke: force or simulate LLM error → file contains `status_code` / body snippet

## 5. Documentation sync (post-implementation)

- [x] Update `docs/INDEX.md` — `logging_setup.py`, `llm_logging.py`, `logs/`
- [x] Archive wave in `docs/PROGRESS.md` after commit

---

## Follow-ups

- [x] Router message list: `get_dialog_messages()` — fix HTTP 400 «System message must be at the beginning» (see `docs/DECISIONS.md` 2026-06-01 router LLM message list). RCA: file logs, not context-window limit.
- [ ] Router context diet (optional): trim or summarize very long assistant replies before router (catalog answer still sent as user/assistant dialog).
- [ ] Dedicated `logs/mcp-….log` for FastMCP subprocess stderr.

## Manual verification

1. `uv run python main.py` → `logs/repl-*.log` created; startup line present.
2. One `simple` + one `agent` turn → file contains `route=`, MCP tool lines.
3. Induce API error (bad key or quota) → file has Yandex `status_code` and body; terminal still shows short Russian message.
4. Regression: привет → услуги банка → баланс Иванова — router returns 200 after agent turn (no 400 on second router call).
