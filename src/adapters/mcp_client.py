"""MCP stdio subprocess client with a synchronous facade for the REPL."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import threading
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import get_default_environment, stdio_client

from adapters.config import AppConfig

logger = logging.getLogger(__name__)

_SRC_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SRC_DIR.parent


def call_tool_result_to_text(result: types.CallToolResult) -> str:
    """Serialize MCP tool result for the LLM observation."""
    if result.structuredContent is not None:
        return json.dumps(result.structuredContent, ensure_ascii=False)
    parts: list[str] = []
    for block in result.content:
        if isinstance(block, types.TextContent):
            parts.append(block.text)
    return "\n".join(parts) if parts else "{}"


class BankingMcpClient:
    """Long-lived MCP session over stdio, driven from sync REPL code."""

    def __init__(self, config: AppConfig) -> None:
        """Store config; connection starts in connect()."""
        self._config = config
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._session: ClientSession | None = None
        self._tools: list[types.Tool] = []
        self._ready = threading.Event()
        self._stopped = threading.Event()
        self._stop_async: asyncio.Event | None = None

    def connect(self) -> None:
        """Start MCP server subprocess and initialize the session."""
        self._thread = threading.Thread(target=self._thread_main, name="mcp-client", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=30):
            msg = "MCP server failed to start within 30s"
            raise TimeoutError(msg)

    def close(self) -> None:
        """Shut down MCP session and subprocess."""
        if self._loop is None or self._stop_async is None:
            return
        self._loop.call_soon_threadsafe(self._stop_async.set)
        self._stopped.wait(timeout=30)
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._loop = None
        self._thread = None
        self._session = None

    def list_tools(self) -> list[types.Tool]:
        """Return cached tools from the last connect."""
        return list(self._tools)

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        """Invoke a tool and return JSON/text for the agent observation."""
        if self._loop is None or self._session is None:
            msg = "MCP client is not connected"
            raise RuntimeError(msg)

        async def _call() -> types.CallToolResult:
            assert self._session is not None
            return await self._session.call_tool(name, arguments or {})

        result = asyncio.run_coroutine_threadsafe(_call(), self._loop).result(timeout=60)
        return call_tool_result_to_text(result)

    def _thread_main(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        pythonpath = os.pathsep.join(
            [str(_SRC_DIR), os.environ.get("PYTHONPATH", "")],
        ).strip(os.pathsep)
        try:
            self._loop.run_until_complete(self._run_session(pythonpath))
        finally:
            self._loop.close()
            self._stopped.set()

    async def _run_session(self, pythonpath: str) -> None:
        """Own connect/disconnect in one task to satisfy anyio cancel scopes."""
        self._stop_async = asyncio.Event()
        server_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", self._config.mcp_server_module],
            cwd=str(_PROJECT_ROOT),
            env={
                **get_default_environment(),
                "PYTHONPATH": pythonpath,
                "DATABASE_PATH": self._config.database_path,
            },
        )
        async with AsyncExitStack() as stack:
            transport = stdio_client(server_params)
            read_stream, write_stream = await stack.enter_async_context(transport)
            session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
            self._session = session
            await session.initialize()
            listed = await session.list_tools()
            self._tools = list(listed.tools)
            self._ready.set()
            await self._stop_async.wait()
