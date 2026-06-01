"""MCP stdio subprocess client with a synchronous facade for the REPL."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import threading
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import get_default_environment, stdio_client
from pydantic import AnyUrl

from adapters.config import AppConfig
from adapters.llm_logging import truncate_for_log
from adapters.paths import get_repo_root

logger = logging.getLogger(__name__)

_REPO_ROOT = get_repo_root()
_SRC_ROOT = _REPO_ROOT / "src"


def read_resource_result_to_text(result: types.ReadResourceResult) -> str:
    """Serialize MCP resource read result to plain text."""
    parts: list[str] = []
    for block in result.contents:
        if isinstance(block, types.TextResourceContents):
            parts.append(block.text)
    return "\n".join(parts)


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
        logger.info(
            "MCP connect module=%s cwd=%s database_path=%s",
            self._config.mcp_server_module,
            _REPO_ROOT,
            self._config.database_path,
        )
        self._thread = threading.Thread(target=self._thread_main, name="mcp-client", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=30):
            msg = "MCP server failed to start within 30s"
            raise TimeoutError(msg)
        logger.info("MCP connected tools=%s", [tool.name for tool in self._tools])

    def close(self) -> None:
        """Shut down MCP session and subprocess."""
        if self._loop is None or self._stop_async is None:
            return
        logger.info("MCP close")
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

        arg_keys = sorted((arguments or {}).keys())
        logger.info("MCP call_tool name=%s arg_keys=%s", name, arg_keys)
        result = asyncio.run_coroutine_threadsafe(_call(), self._loop).result(timeout=60)
        text = call_tool_result_to_text(result)
        logger.info("MCP call_tool result=%s", truncate_for_log(text))
        return text

    def list_resources(self) -> list[types.Resource]:
        """Return resources advertised by the MCP server."""
        if self._loop is None or self._session is None:
            msg = "MCP client is not connected"
            raise RuntimeError(msg)

        async def _list() -> list[types.Resource]:
            assert self._session is not None
            listed = await self._session.list_resources()
            return list(listed.resources)

        resources = asyncio.run_coroutine_threadsafe(_list(), self._loop).result(timeout=60)
        uris = [str(resource.uri) for resource in resources]
        logger.info("MCP list_resources count=%s uris=%s", len(uris), uris)
        return resources

    def read_resource(self, uri: str) -> str:
        """Read an MCP resource by URI and return its text content."""
        if self._loop is None or self._session is None:
            msg = "MCP client is not connected"
            raise RuntimeError(msg)

        async def _read() -> types.ReadResourceResult:
            assert self._session is not None
            return await self._session.read_resource(AnyUrl(uri))

        logger.info("MCP read_resource uri=%s", uri)
        result = asyncio.run_coroutine_threadsafe(_read(), self._loop).result(timeout=60)
        text = read_resource_result_to_text(result)
        logger.info(
            "MCP read_resource uri=%s chars=%s preview=%s",
            uri,
            len(text),
            truncate_for_log(text, 120),
        )
        return text

    def _thread_main(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        pythonpath = os.pathsep.join(
            [str(_SRC_ROOT), os.environ.get("PYTHONPATH", "")],
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
            cwd=str(_REPO_ROOT),
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
