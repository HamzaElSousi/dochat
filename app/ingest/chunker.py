from langchain_text_splitters import RecursiveCharacterTextSplitter

# cl100k_base is the encoding used by text-embedding-3-small (same as GPT-4 / ada-002).
# from_tiktoken_encoder counts TOKENS not characters — plain chunk_size=512 counts chars (wrong).
ENCODING_NAME = "cl100k_base"
CHUNK_SIZE = 511     # tokens (511 ensures encoded output never exceeds 512 due to LangChain off-by-one)
CHUNK_OVERLAP = 100  # tokens


def chunk_text(text: str) -> list[str]:
    """Split text into chunks of at most 512 tokens with 100-token overlap.

    Returns list of non-empty chunk strings. Raises ValueError if text is empty
    or produces zero chunks.
    """
    if not text.strip():
        raise ValueError("Cannot chunk empty text")

    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name=ENCODING_NAME,
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunks = splitter.split_text(text)
    chunks = [c for c in chunks if c.strip()]

    if not chunks:
        raise ValueError("Document produced no chunks after splitting")

    return chunks
