# Plan 05 — Router structured output (Yandex `response_format`)

**Goal:** Make semantic router output reliable via API-level JSON schema instead of prompt-only “ТОЛЬКО JSON”; leave agent function calling and demo-only features unchanged.

**References:**

- `docs/DECISIONS.md` (entry 2026-06-01 Yandex structured output vs function calling)
- [Structured output](https://aistudio.yandex.ru/docs/en/ai-studio/concepts/generation/structured-output)
- [Function calling](https://aistudio.yandex.ru/docs/en/ai-studio/concepts/generation/function-call) — already implemented on agent path

**Depends on:** plan 04 done; OpenAI-compatible client (`src/adapters/llm_client.py`) and `route_user_message` in `src/adapters/router.py`.

**Background:** Router today uses `ROUTER_SYSTEM` (“Ответь ТОЛЬКО JSON…”) + `json.loads` + fallback to `agent`. Yandex documents `response_format` with `json_schema` for strict fields; agent tools already use JSON Schema via MCP → OpenAI `tools`.

**API note (smoke 2026-06-01):** `chat.completions.create(..., response_format={"type":"json_schema","json_schema":{"name":"router_route","strict":true,"schema":{...}}})` works on default `MODEL_ROUTER` (`qwen3.5-35b-a3b-fp8`) via `https://ai.api.cloud.yandex.net/v1`.

---

## 0. Documentation (this session)

- [x] Append decision to `docs/DECISIONS.md`
- [x] Create this plan; set `docs/PROGRESS.md` active plan
- [x] Update `docs/ARCHITECTURE.md`, `docs/INDEX.md`

## 1. Smoke: API support on router model

- [x] Smoke: structured `response_format` on `MODEL_ROUTER` — OK
- [x] Fallback path on `APIError` — retry without `response_format` + JSON prompt suffix
- [x] Parameter shape documented above

## 2. Router schema constant + call site

- [x] `src/adapters/router.py` — `ROUTER_RESPONSE_SCHEMA`, `router_response_format()`
- [x] `route_user_message` — `response_format` on primary call; routing rules in `ROUTER_SYSTEM`
- [x] `temperature=0.0`, blocking, `log_llm_*` unchanged
- [x] Parse failure → `agent`

## 3. Tests

- [x] `tests/adapters/test_router.py` — schema, parse, structured call, API fallback, bad JSON
- [ ] Optional: env-gated live test skipped in CI

## 4. Documentation sync (post-implementation)

- [x] `docs/ARCHITECTURE.md` — router `response_format`
- [x] Archive wave in `docs/PROGRESS.md` after commit

---

## Out of scope (explicit — demo wider than Yandex examples)

- Agent loop / function calling refactor (already correct)
- `response_format` on `run_simple_chat` or agent `tools` requests
- Native Yandex SDK (`yandex_ai_studio_sdk`) or `ToolCallList` / `ToolResultList` wire format
- HITL, MCP resources, streaming policy, cancel-without-LLM
- Mandatory router structured output with no fallback

## Optional follow-up (separate plan or backlog)

- Richer MCP tool `description` / parameter descriptions in `banking_server.py` (function-calling doc quality)

## Manual verification

- [x] «Привет» → `simple` (stable JSON / route).
- [x] «Баланс Иванова» / «услуги банка» → `agent`.
- [x] Extended REPL smoke: HITL prepare → да (commit) / нет (cancel), balances (2026-06-01).
- [ ] Adversarial: model cannot wrap router output in markdown fences (or fallback still lands on `agent`).
- [ ] File log: router phase unchanged except optional `response_format` in debug if logged.
