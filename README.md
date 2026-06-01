# agentic-banking-mcp-demo

Демонстрационный проект для вебинара «Архитектура AI-агентов и паттерны интеграции». Практическая реализация ReAct-агента в банковском домене с использованием протокола MCP (Model Context Protocol), семантической маршрутизации (Semantic Router) и контроля безопасности (HITL).

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

## Документация

| Документ | Описание |
|----------|----------|
| [docs/INDEX.md](docs/INDEX.md) | Навигация по репозиторию |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Архитектура и потоки |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Принятые решения |
| [docs/PROGRESS.md](docs/PROGRESS.md) | Активный план и журнал волн |
| [docs/plans/03-file-logging.md](docs/plans/03-file-logging.md) | Активный план (file logging) |
| [docs/plans/01-banking-agent-mcp-demo.md](docs/plans/01-banking-agent-mcp-demo.md) | План реализации (plan 01) |

## Тесты

```bash
uv run pytest                    # unit + integration
uv run pytest -m "not integration"  # unit only (faster)
uv run ruff check .
uv run ruff format --check .
```

## Ручной smoke-сценарий (лекция)

См. чеклист в [docs/plans/01-banking-agent-mcp-demo.md](docs/plans/01-banking-agent-mcp-demo.md).
