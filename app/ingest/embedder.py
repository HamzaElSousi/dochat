import os
import requests


EMBED_MODEL = "openai/text-embedding-3-small"
EMBED_DIM = 1536
SUBBATCH_SIZE = 100   # max texts per OpenRouter call (conservative — rate limit undocumented)
EMBED_TIMEOUT = 30    # seconds; leaves headroom within 60s Apache CGI limit


def embed_chunks(chunk_texts: list[str]) -> list[list[float]]:
    """Embed all chunks via OpenRouter batch API. Returns list of 1536-dim float vectors.

    If len(chunk_texts) > SUBBATCH_SIZE, splits into sequential sub-batches of 100
    to avoid undocumented per-request input limits.

    Raises ValueError on empty input.
    Raises requests.HTTPError on API failure (caller handles rollback).
    """
    if not chunk_texts:
        raise ValueError("Cannot embed empty chunk list")

    api_key = os.environ.get('OPENROUTER_API_KEY', '')

    # Sub-batch into groups of SUBBATCH_SIZE
    all_embeddings: list[list[float]] = []
    for i in range(0, len(chunk_texts), SUBBATCH_SIZE):
        batch = chunk_texts[i: i + SUBBATCH_SIZE]
        response = requests.post(
            "https://openrouter.ai/api/v1/embeddings",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": EMBED_MODEL,
                "input": batch,
            },
            timeout=EMBED_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        # Sort by index to ensure ordering matches input order
        batch_embeddings = sorted(data["data"], key=lambda x: x["index"])
        all_embeddings.extend(e["embedding"] for e in batch_embeddings)

    return all_embeddings
