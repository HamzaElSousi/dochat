import requests

from app.llm_config import embed_base_url, embed_dim, embed_model, llm_api_key

SUBBATCH_SIZE = 100   # max texts per embeddings call (conservative — rate limit undocumented)
EMBED_TIMEOUT = 30    # seconds; leaves headroom within 60s Apache CGI limit


def embed_chunks(chunk_texts: list[str]) -> list[list[float]]:
    """Embed all chunks via the configured provider's batch API.

    Uses OpenRouter (text-embedding-3-small, 1536-dim) by default, or a local
    Ollama server (nomic-embed-text, 768-dim) when EMBED_PROVIDER=ollama. Both
    expose the same OpenAI-compatible /v1/embeddings shape.

    If len(chunk_texts) > SUBBATCH_SIZE, splits into sequential sub-batches of 100
    to avoid undocumented per-request input limits.

    Raises ValueError on empty input.
    Raises requests.HTTPError on API failure (caller handles rollback).
    """
    if not chunk_texts:
        raise ValueError("Cannot embed empty chunk list")

    api_key = llm_api_key()
    model = embed_model()
    expected_dim = embed_dim()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    # Sub-batch into groups of SUBBATCH_SIZE
    all_embeddings: list[list[float]] = []
    for i in range(0, len(chunk_texts), SUBBATCH_SIZE):
        batch = chunk_texts[i: i + SUBBATCH_SIZE]
        response = requests.post(
            f"{embed_base_url()}/embeddings",
            headers=headers,
            json={
                "model": model,
                "input": batch,
            },
            timeout=EMBED_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        # Sort by index to ensure ordering matches input order
        batch_embeddings = sorted(data["data"], key=lambda x: x["index"])
        for e in batch_embeddings:
            if len(e["embedding"]) != expected_dim:
                raise ValueError(
                    f"API returned embedding dimension {len(e['embedding'])}, "
                    f"expected {expected_dim}. Check EMBED_MODEL / EMBED_DIM or the API response."
                )
            all_embeddings.append(e["embedding"])

    return all_embeddings


def embed_query(text: str) -> list[float]:
    """Embed a single visitor query string. Thin wrapper around embed_chunks().

    Returns a float vector matching the configured embedding model's dimension
    (same model as document embeddings).
    Raises ValueError on empty input; raises requests.HTTPError on API failure.
    """
    return embed_chunks([text])[0]
