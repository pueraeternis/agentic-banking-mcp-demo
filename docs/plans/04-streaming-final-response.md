# Plan 04 — Stream final assistant reply in REPL

**Goal:** Show the user-facing assistant text token-by-token in the terminal; keep router, tool rounds, and MCP steps non-streamed (blocking + rich Action/Observation as today).

**References:** `docs/DECISIONS.md` (entry 2026-06-01 streaming final response), `docs/ARCHITECTURE.md`.

**Depends on:** plan 03 committed; balance/router fixes in place.

**Background:** Long answers (e.g. bank services catalog) block on the full completion, then print at once. Yandex models use OpenAI-compatible `chat.completions` with `stream=True` for text-only turns.

---

## 0. Documentation (this session)

- [x] Append decisions to `docs/DECISIONS.md`
- [x] Create this plan; set `docs/PROGRESS.md` active plan
- [x] Update `docs/ARCHITECTURE.md`, `docs/INDEX.md`

## 1. Config and streaming helper

- [x] `.env.example` — `STREAM_FINAL_RESPONSE=true` (disable with `false` / `0`)
- [x] `src/adapters/config.py` — `stream_final_response: bool` from env (default `True`)
- [x] `src/adapters/llm_streaming.py` — `stream_chat_text(client, model, messages, temperature, on_token) -> (full_text, usage)`; text-only, no tools

## 2. Stream only user-facing completions

- [x] `src/adapters/router.py` — `run_simple_chat`: when `stream_final_response` and `on_token` provided, use `stream_chat_text`; else blocking `create()`. Return `(text, streamed: bool)`. **Router** `route_user_message` stays blocking (JSON only).
- [x] `src/adapters/agent_loop.py` — on step with **no** `tool_calls` (final text or max-steps fallback): stream if enabled; tool-call steps stay blocking `create(..., tools=...)`. `AgentLoopResult.streamed_to_user: bool`.
- [x] Do **not** stream: router, agent steps that return `tool_calls`, HITL panel (no assistant prose before prepare)

## 3. REPL (rich console)

- [x] `src/cli/repl.py` — `on_token` handler: print `[magenta]Ассистент:[/magenta] ` once, then deltas with `end=""`, newline at end; skip duplicate full-message print when `streamed_to_user`
- [x] Wire `on_token` into `run_simple_chat` and `run_agent_loop` (main loop + `_handle_hitl` after commit)
- [x] Log stream start/end at INFO in file log (optional, no token spam at INFO)

## 4. Tests

- [x] `tests/adapters/test_llm_streaming.py` — mock stream chunks → assembled text + `on_token` call count (no live API)
- [x] Manual: `simple` greeting streams; «услуги банка» streams long catalog; «баланс Иванова» — pause on tools, then stream short final line (verified 2026-06-01)

## 5. Documentation sync (post-implementation)

- [x] Update `docs/INDEX.md` — `llm_streaming.py`
- [x] Archive wave in `docs/PROGRESS.md` after commit

---

## Out of scope

- Streaming router JSON or tool-call deltas
- SSE / web UI
- Async REPL

## Manual verification

1. `STREAM_FINAL_RESPONSE=true` — visible token-by-token on final assistant line.
2. `STREAM_FINAL_RESPONSE=false` — behavior unchanged (full block after pause).
3. Router + Action/Observation unchanged; file logs still work (plan 03).
