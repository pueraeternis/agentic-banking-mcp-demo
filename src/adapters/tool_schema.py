"""Convert MCP tool definitions to OpenAI function-calling schema."""

from __future__ import annotations

from typing import Any

from mcp import types


def mcp_tools_to_openai(tools: list[types.Tool]) -> list[dict[str, Any]]:
    """Map MCP list_tools output to OpenAI tools parameter."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.inputSchema,
            },
        }
        for tool in tools
    ]
