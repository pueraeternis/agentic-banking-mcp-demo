# agentic-banking-mcp-demo

Демонстрационный проект для вебинара «Архитектура AI-агентов и паттерны интеграции». Практическая реализация ReAct-агента в банковском домене с использованием протокола MCP (Model Context Protocol), семантической маршрутизации (Semantic Router) и контроля безопасности (HITL).

## Как устроено приложение

```text
Пользователь → REPL
                 ├─ Semantic Router (лёгкая модель) → route: simple | agent
                 ├─ simple: общий разговор без tools и без каталога банка
                 └─ agent: тяжёлая модель + MCP (stdio)
                        ├─ tools: find_client, get_account_balance, prepare/commit/cancel_transfer
                        ├─ resource: banking://services → data/bank_services.md
                        └─ HITL: после prepare_transfer — панель «да/нет»; cancel без LLM
```

| Что видно в терминале | Когда |
|-----------------------|--------|
| `route=simple` / `route=agent` | После каждого сообщения пользователя |
| **Action** / **Observation** | Agent вызвал MCP-tool |
| **Resource** `banking://services` | Ответ про услуги банка (каталог из файла) |
| Панель «Подтверждение перевода» | После `prepare_transfer` (деньги ещё не списаны) |
| `Ассистент:` + текст | Финальный ответ (может стримиться по токенам) |

Демо-клиенты в SQLite (после `seed_db.py`): **Иванов** 1 000 ₽, **Петров** 500 ₽, **Сидоров** 250 ₽ (в БД — копейки). Каталог услуг — банк **«Демо-Банк»** в `data/bank_services.md`.

Подробнее: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Быстрый старт

```bash
# Зависимости
uv sync

# Секреты Yandex AI Studio
cp .env.example .env
# заполните YC_FOLDER_ID и YC_API_KEY

# База данных (балансы в копейках; после смены seed — перезапустите)
uv run python scripts/seed_db.py

# REPL
uv run python main.py
```

Сессионные логи пишутся в `logs/repl-*.log` (каталог в `.gitignore`). При ошибках Yandex API подробности — в файле; в терминале остаётся короткое сообщение. Для развёрнутого контекста LLM задайте `LOG_LEVEL=DEBUG` в `.env`.

Переменные: `STREAM_FINAL_RESPONSE` (по умолчанию `true`) — потоковый вывод финального текста ассистента; роутер и шаги с tools не стримятся.

## Расширенный операторский чек

Запустите `uv run python main.py` и проходите сценарии **по одному** — дождитесь ответа, сверьте `route=`, Action/Observation/Resource и панель HITL.

### Подготовка

- [ ] `.env` с `YC_FOLDER_ID` и `YC_API_KEY`
- [ ] `uv run python scripts/seed_db.py` (чистая БД перед демо)
- [ ] При необходимости: `LOG_LEVEL=INFO`, смотреть `logs/repl-*.log` после сессии

### A. Роутер и simple

| # | Ввод | Ожидается |
|---|------|-----------|
| A1 | `Привет! Меня зовут Виталий.` | `route=simple`, без Action/Observation |
| A2 | `Как тебе погода сегодня?` | `route=simple`, без выдуманных балансов/каталога |
| A3 | `Сколько на счёте у Иванова?` | `route=agent`, `find_client` → `get_account_balance`, **1 000 ₽ 00 коп.** |
| A4 | `Какие услуги у банка?` | `route=agent`, **Resource** `banking://services`, текст про **Демо-Банк** (вклады, карты из каталога) |
| A5 | `Баланс Петрова` | `route=agent`, **500 ₽** |

Опционально (регрессия длинного контекста): после A4 снова `Привет` → `route=simple`, без HTTP 400 от API.

### B. Agent + MCP (без перевода)

| # | Ввод | Ожидается |
|---|------|-----------|
| B1 | `Найди клиента Сидоров` | `find_client`, ФИО и телефон в ответе |
| B2 | `Сколько у Сидорова на счёте?` | **250 ₽** |

### C. HITL (переводы)

У Иванова **1 000 ₽** (100 000 коп.). Для успешного сценария используйте **50 000 коп.** (500 ₽), не 500 000 коп. (не хватит средств).

| # | Ввод | Ожидается |
|---|------|-----------|
| C1 | `Переведи 50000 копеек с Иванова Петрову` | `prepare_transfer`, жёлтая **панель**, цикл агента остановился (нет `commit` в том же прогоне) |
| C2 | `да` | `commit_transfer`, подтверждение перевода на 500 ₽ |
| C3 | `Сколько на счёте у Иванова?` | **500 ₽** (было 1 000 − 500) |
| C4 | `Переведи 10000 копеек с Иванова Петрову` | снова панель prepare |
| C5 | `нет` | `cancel_transfer` (в логе Action), «Перевод отменён», **без** нового прогона LLM на отмену |
| C6 | `Баланс Иванова` | по-прежнему **500 ₽** |

Опционально: `Переведи 500000 копеек с Иванова Петрову` → ошибка недостаточно средств в Observation.

### D. Стриминг и выход

- [ ] При `STREAM_FINAL_RESPONSE=true` финальный текст после `Ассистент:` появляется по частям (simple и короткий ответ agent); на шагах с tools — сначала Action/Observation, потом финал.
- [ ] `exit` или `quit` — выход из REPL.

### Минимум перед лекцией

**A1 → A3 → A4 → C1 → C2 → C5 → exit** (роутер, resource, tools, HITL да/нет).

### Автотесты

```bash
uv run pytest
```

## Документация

| Документ | Описание |
|----------|----------|
| [docs/INDEX.md](docs/INDEX.md) | Навигация по репозиторию |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Архитектура и потоки |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Принятые решения |
| [docs/PROGRESS.md](docs/PROGRESS.md) | Журнал волн и планов |
| [docs/plans/](docs/plans/) | Чеклисты по волнам (01–05) |

## Тесты и линтер

```bash
uv run pytest                    # unit + integration
uv run pytest -m "not integration"  # unit only (faster)
uv run ruff check .
uv run ruff format --check .
```
