"""OpenAI-compatible client for Yandex AI Studio."""

from openai import OpenAI

from adapters.config import YANDEX_OPENAI_BASE_URL, AppConfig


def create_llm_client(config: AppConfig) -> OpenAI:
    """Create a synchronous OpenAI client configured for Yandex."""
    return OpenAI(
        base_url=YANDEX_OPENAI_BASE_URL,
        api_key=config.api_key,
        project=config.folder_id,
    )
