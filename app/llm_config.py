"""Provider resolution for the LLM and embeddings.

DocChat talks to any OpenAI-compatible endpoint. By default it uses OpenRouter
(production). Set LLM_PROVIDER=ollama / EMBED_PROVIDER=ollama to run fully offline
against a local Ollama server (no API key) for local testing and development.

Both OpenRouter and Ollama expose identical /v1/chat/completions and /v1/embeddings
shapes, so only the base URL, model name, and embedding dimension change.

NOTE: this never imports torch / transformers / sentence-transformers. Ollama runs
as a separate process reached over HTTP, so the shared-hosting RAM rule is preserved.
"""

import os

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _ollama_base() -> str:
    return os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")


def llm_provider() -> str:
    return os.environ.get("LLM_PROVIDER", "openrouter").lower()


def embed_provider() -> str:
    # Defaults to LLM_PROVIDER so a single switch flips both LLM and embeddings.
    return os.environ.get("EMBED_PROVIDER", llm_provider()).lower()


def llm_base_url() -> str:
    if llm_provider() == "ollama":
        return f"{_ollama_base()}/v1"
    return os.environ.get("OPENROUTER_BASE_URL", OPENROUTER_BASE_URL)


def embed_base_url() -> str:
    if embed_provider() == "ollama":
        return f"{_ollama_base()}/v1"
    return os.environ.get("OPENROUTER_BASE_URL", OPENROUTER_BASE_URL)


def llm_api_key() -> str:
    # Ollama ignores the key; OpenRouter requires it.
    return os.environ.get("OPENROUTER_API_KEY", "")


def requires_api_key() -> bool:
    return llm_provider() != "ollama" or embed_provider() != "ollama"


def primary_model() -> str:
    if os.environ.get("PRIMARY_MODEL"):
        return os.environ["PRIMARY_MODEL"]
    return "llama3" if llm_provider() == "ollama" else "meta-llama/llama-3.3-70b-instruct:free"


def fallback_model() -> str:
    if os.environ.get("FALLBACK_MODEL"):
        return os.environ["FALLBACK_MODEL"]
    if llm_provider() == "ollama":
        return primary_model()
    return "google/gemma-3-12b-it:free"


def embed_model() -> str:
    if os.environ.get("EMBED_MODEL"):
        return os.environ["EMBED_MODEL"]
    return "nomic-embed-text" if embed_provider() == "ollama" else "openai/text-embedding-3-small"


def embed_dim() -> int:
    if os.environ.get("EMBED_DIM"):
        return int(os.environ["EMBED_DIM"])
    return 768 if embed_provider() == "ollama" else 1536
