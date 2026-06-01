"""Application configuration from environment variables."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

YANDEX_OPENAI_BASE_URL = "https://ai.api.cloud.yandex.net/v1"


@dataclass(frozen=True)
class AppConfig:
    """Runtime settings for the banking REPL demo."""

    folder_id: str
    api_key: str
    model_router: str
    model_agent: str
    database_path: str
    mcp_server_module: str

    @classmethod
    def from_env(cls) -> AppConfig:
        """Load configuration and exit if required secrets are missing."""
        folder_id = os.getenv("YC_FOLDER_ID", "").strip()
        api_key = os.getenv("YC_API_KEY", "").strip()
        if not folder_id or not api_key:
            print("Missing YC_FOLDER_ID or YC_API_KEY. Copy .env.example to .env.", file=sys.stderr)
            sys.exit(1)

        return cls(
            folder_id=folder_id,
            api_key=api_key,
            model_router=os.getenv("MODEL_ROUTER", "qwen3.5-35b-a3b-fp8").strip(),
            model_agent=os.getenv("MODEL_AGENT", "qwen3-235b-a22b-fp8").strip(),
            database_path=os.getenv("DATABASE_PATH", "data/banking.db").strip(),
            mcp_server_module=os.getenv(
                "MCP_SERVER_MODULE",
                "mcp_servers.banking_server",
            ).strip(),
        )

    def model_uri(self, slug: str) -> str:
        """Build Yandex model URI for OpenAI-compatible API."""
        return f"gpt://{self.folder_id}/{slug}/latest"

    @property
    def router_model_uri(self) -> str:
        """URI for the semantic router / simple chat model."""
        return self.model_uri(self.model_router)

    @property
    def agent_model_uri(self) -> str:
        """URI for the tool-calling agent model."""
        return self.model_uri(self.model_agent)
