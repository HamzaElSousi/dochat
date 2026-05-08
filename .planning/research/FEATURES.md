# Feature Landscape: RAG Chatbot for Software Consulting Website

**Domain:** Embeddable document Q&A chatbot (single-tenant, admin-managed knowledge base)
**Business context:** social-automate.com — software consulting agency fielding client inquiries
**Researched:** 2026-05-07
**Overall confidence:** HIGH (verified across Context7, official docs, production practitioner sources)

---

## Table Stakes

Features users expect by default. Missing any of these causes immediate abandonment or erosion of trust.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Accurate, grounded answers | RAG's entire value prop — users left static FAQ pages for a reason | Med | Retrieval quality is the whole game; see RAG Quality section |
| Graceful "I don't know" fallback | Users distrust a bot that fabricates; a confident wrong answer is worse than a polite refusal | Low | System prompt: "If context doesn't answer the question, say so explicitly. Do not speculate." |
| Source citations with every answer | Perplexity and Google AI Search have normalized this. Without it, users can't verify and won't trust | Med | Show document name (and page/section when available). Not clickable links in v1 — just attribution text |
| Session-based chat history | Users expect to refer back to earlier answers in a conversation | Low | In-memory per session; no persistence needed in v1 |
| Typing indicator / loading state | 47% abandonment when responses feel frozen; users need to know the bot is thinking | Low | CSS animation on the widget side; fires immediately on send |
| Response within 5s | Users tolerate up to ~5 seconds before assuming the bot is broken; 3s is comfortable | Med | Shared hosting latency + LLM API = budget carefully. k=3–5 chunks keeps prompt small |
| Responsive widget on mobile | >50% of web traffic is mobile; a widget that breaks on phones looks amateurish | Low | Standard CSS max-width + viewport units. Not a native app, just responsive HTML |
| Branded appearance (colors, logo) | A grey generic widget on a branded consulting site signals "off-the-shelf demo" | Low | CSS custom properties controlled by config object passed to the script tag |
| Widget discoverable but not intrusive | Fixed bottom-right FAB is the universal convention; users know to look there | Low | Standard placement; no pop-up-on-load nags in v1 |
| Admin password protection | Exposing document upload to the internet without auth is a security incident waiting to happen | Low | Single hardcoded credential (env var) is sufficient for single-admin v1 |

---

## Differentiators

Features that are not table stakes but meaningfully increase trust, answer quality, or perception of polish. These separate a credible business tool from a demo.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Document-name + section citation | "According to our Services Overview (Pricing section)" is far more trustworthy than a bare answer | Med | Store doc name and chunk position as metadata at index time. Surface in response template |
| Graceful partial-answer framing | "Based on what I found in your docs, here's what I know — for the rest, contact us" converts uncertainty into a lead handoff | Low | Prompt engineering only; no code complexity |
| Suggested follow-up questions | 2–3 clickable question chips after each answer reduce user effort and keep engagement going | Low | LLM generates these as part of the response JSON; widget renders as buttons |
| Out-of-scope redirect with CTA | When the bot can't answer, don't dead-end — "This is outside what I can answer from our docs. Want to book a call?" | Low | Prompt + static CTA link config. Zero backend work |
| Document upload status feedback | Admin needs to know when a doc has finished processing (chunked, embedded, indexed) vs is still pending | Low | Processing status field in DB; polling or simple page refresh |
| Indexed document list with delete | Admin must be able to see what's in the knowledge base and remove outdated docs cleanly | Low | Simple table: filename, upload date, chunk count, delete button |
| Chunk overlap for continuity | Prevents answers that are cut off mid-sentence because a relevant passage straddles a chunk boundary | Low | Set overlap=100 tokens on top of recursive chunking. One config value |
| Widget open/close animation | Smooth expand/collapse (200ms ease-in) vs instant pop makes the experience feel production-grade | Low | Pure CSS transition |
| Error message that doesn't expose internals | "Something went wrong — please try again" instead of a raw 500 stack trace | Low | Frontend catch-all; never surface Python errors to visitors |

---

## Admin Features: Minimum Viable Document Management

The admin UI needs to do exactly five things and nothing more in v1.

| Feature | Why Needed | Complexity | Notes |
|---------|------------|------------|-------|
| File upload (PDF, DOCX, TXT, MD) | Core requirement — admin feeds the knowledge base | Med | Multipart form POST; backend handles parsing and indexing pipeline |
| URL crawl + index | Some content lives on web pages, not files | Med | Use `trafilatura` or `newspaper3k` to extract article text; same indexing pipeline afterward |
| Indexed document list | Admin must see what's in the system to manage it | Low | Table: name, type, upload date, status, chunk count |
| Delete document | Admin removes a doc and its vectors disappear from the store | Med | Must delete all chunks associated with a doc ID from the vector store — not just the file |
| Login / logout | Protect the admin interface | Low | Single credential from env var; session cookie |

**What to skip in v1:**
- Document preview / viewer
- Bulk upload
- Tagging / categorizing documents
- Search within admin document list
- Usage stats per document

---

## Widget UX Patterns: Polished vs Janky

### Polished patterns

- **Fixed bottom-right FAB** — universal convention; users find it without thinking. Do not invent a novel placement.
- **Immediate user message render** — show the user's own message instantly before the API call returns; prevents the "did my message send?" anxiety.
- **Typing indicator on bot side** — animated three-dot ellipsis while waiting for response. Fires the moment the user hits Send.
- **Visual distinction between user and bot** — user messages right-aligned in brand color; bot messages left-aligned with bot avatar icon. Never ambiguous about who said what.
- **Bot avatar / name** — "DocBot" or the business name with a simple icon. Not a fake human face.
- **Short welcome message on open** — "Hi, I can answer questions about our services. What would you like to know?" Orients the user immediately.
- **Quick-reply chips** — 2–3 suggested questions pre-loaded or generated after answers. Huge UX win for users who don't know how to start.
- **Shadow DOM isolation** — prevents host page CSS from breaking the widget on any site (WordPress themes are especially aggressive).
- **Source line below answer** — subtle grey text: "Source: Services Overview" below the answer. Not a footnote — inline, below the response bubble.

### Janky patterns to avoid

- **Pop-up on page load** — forces the chatbot into the user's face before they've read a single sentence. Universally hated.
- **Generic greeting: "Hello! How can I help you?"** — tells the user nothing about what the bot knows. Wastes their time.
- **Full-page chat on mobile** — widget should open as an overlay, not navigate away. Users want to keep reading the page.
- **Monospace or serif font in chat** — chatbots should use a clean sans-serif (system font stack or Inter). Anything else reads as a terminal, not a chat.
- **Exposing raw model output formatting** — if the LLM returns markdown, render it. Don't show `**bold**` as literal asterisks.
- **Static spinner instead of typing indicator** — a spinning wheel feels like a page load, not a conversation.
- **Sending on Enter by default without warning** — mobile users hit Enter accidentally. Use a Send button; Enter adds a newline.

---

## Anti-Features: Do Not Build in v1

Explicit decisions to defer. Each one is a plausible thing to build and a trap that will consume weeks without validating the core.

| Anti-Feature | Why Avoid in v1 | What to Do Instead |
|--------------|-----------------|-------------------|
| Streaming responses (SSE/WebSockets) | Adds infra complexity, breaks on Passenger WSGI without careful config, hard to debug | Standard request/response is fine at <100 queries/day. Add streaming in v2 |
| Analytics dashboard (query volume, top questions) | Zero users to analyze yet. You'll build the wrong metrics | Log queries to a plain text file; read it manually until patterns emerge |
| Confidence score display | Cosine similarity scores are not user-legible; a 0.73 score means nothing to a client | Use retrieval score internally to gate the "I don't know" fallback — never surface the number |
| Multi-tenant / per-user libraries | One consulting business, one knowledge base, one admin. Multi-tenancy is an architecture change, not a feature add | Single shared library; visitor identity is irrelevant |
| Conversation persistence (cross-session) | Requires user identity. You have no user accounts | In-memory session only. Users can paste and share if needed |
| Human handoff / escalation workflow | CRM integration, ticket creation, agent routing — all of this is a product by itself | Replace with a static CTA: "Book a call" link when bot can't answer |
| Feedback buttons (thumbs up/down) | Useful only when you have enough data to act on. With 10 queries a day, you'll stare at 3 thumbs downs | Defer. Add in v2 alongside a real analytics view |
| Document version history | Adds DB schema complexity; admin can delete and re-upload | Explicit requirement already out of scope |
| Semantic re-ranking (cross-encoder) | Real quality gain but requires running a second model pass on every query. Memory-intensive on shared hosting | Start with vector search + recursive chunking. Add re-ranking if quality becomes the explicit complaint |
| Query expansion / HyDE | Generates hypothetical document embeddings to improve retrieval — sophisticated technique | Not needed when corpus is small and well-structured. Revisit at v2 if retrieval quality is the bottleneck |
| Hybrid search (BM25 + vector) | Genuine improvement for large or vocabulary-mismatched corpora. But on a small, domain-coherent corpus (your own docs), dense-only retrieval performs nearly as well | Start pure vector. Add BM25 hybrid if you observe that exact keyword queries (error codes, product names) fail |
| Real-time URL monitoring / re-crawl | Automatically detecting when a crawled page changes and re-indexing it | Admin manually deletes and re-crawls. Simple. |
| Voice input | Out of scope; adds browser permissions, audio processing, transcription API cost | Text-only in v1 |
| Multilingual support | Not the consulting site's audience; adds prompt and embedding complexity | English only |

---

## RAG Quality Features: What Actually Matters for This Use Case

Ranked by impact-to-complexity ratio for a small-corpus, domain-specific consulting doc Q&A system.

### Tier 1 — Build these in v1 (high impact, low complexity)

**Recursive chunking with overlap**
- Use `RecursiveCharacterTextSplitter` (LangChain) or equivalent: 512 tokens, 100-token overlap
- Why: Preserves sentence and paragraph boundaries. Overlap prevents answers straddling chunk edges
- Do not use fixed-size chunking — it splits sentences mid-thought
- Do not use semantic chunking in v1 — it requires embedding-based similarity computation per split, slow and RAM-intensive on shared hosting

**Metadata on every chunk**
- Store: `doc_id`, `doc_name`, `chunk_index`, `source_type` (file vs URL), `url` or `filename`
- Why: Enables source citation in answers and clean deletion when a doc is removed
- Complexity: Zero cost if done at index time; expensive to retrofit later

**Top-k retrieval tuning (k=3–5)**
- Retrieve 3–5 chunks per query, not 10–20
- Why: More chunks = bigger prompt = slower response + "lost in the middle" degradation. At 3–5 chunks (~1,500–2,500 tokens of context), the LLM sees everything and it's all near the edges of attention
- The "lost in the middle" problem is real: LLMs perform worst on information in the middle of long contexts, even with long-context models

**Hard "answer from context only" system prompt**
- Prompt engineering to prevent hallucination: instruct the model to use only the retrieved context and explicitly say when it lacks an answer
- Why: The biggest single quality improvement available, costs nothing
- Template: "You are an assistant for [business name]. Answer questions ONLY using the context provided below. If the context does not contain enough information to answer, say: 'I don't have that information in my current documents. Please contact us directly.' Do not use your general knowledge."

**Similarity threshold for fallback**
- If the best retrieved chunk has cosine similarity below 0.35 (tune empirically), skip retrieval entirely and return the fallback message
- Why: A low-similarity retrieval stuffed into the prompt makes the LLM hallucinate or produce an off-topic answer. Better to admit ignorance
- Do not surface the score to users

### Tier 2 — Evaluate after v1 (add if quality metrics justify it)

**Hybrid search (BM25 + vector)**
- When to add: If users complain about exact-keyword queries failing (e.g., searching for a specific service name that embeddings don't surface)
- ChromaDB v0.4+ supports hybrid search via its built-in BM25 implementation

**Cross-encoder re-ranking**
- When to add: If top-k retrieved chunks are semantically relevant but not the best match for the query
- Adds a second model pass per query — memory budget needs validation on shared hosting first

**Semantic chunking**
- When to add: If documents have irregular structure and recursive chunking produces poor boundary splits
- Requires embedding-based sentence similarity at index time; compute cost at ingestion, not query time

**Query rewriting**
- When to add: If short/ambiguous queries consistently fail to retrieve good chunks
- Simple prompt: "Rewrite the following question as a detailed search query: [question]"

### Tier 3 — Not for this project at this scale

- HyDE (Hypothetical Document Embeddings)
- Graph RAG / knowledge graphs
- Agentic multi-step retrieval
- Fine-tuned embedding models
- Evaluation harnesses (RAGAS, TruLens) — valuable, but set up after v1 ships

---

## MVP Recommendation

The v1 feature set that ships a credible, trustworthy chatbot for a consulting site:

**Must ship:**
1. Widget: FAB, chat window, typing indicator, source citation display, markdown rendering
2. Chat: session history, graceful fallback message, out-of-scope CTA ("book a call")
3. Retrieval: recursive chunking (512t/100t overlap), vector search (k=4), similarity threshold gate, "answer from context only" prompt
4. Admin: login, file upload (PDF/DOCX/TXT/MD), URL crawl, document list, delete
5. Metadata: doc name + chunk index stored, surfaced in citation line

**Defer explicitly:**
- Streaming, analytics, feedback buttons, re-ranking, hybrid search, conversation persistence

---

## Sources

- [Chunking Strategies for RAG — Weaviate](https://weaviate.io/blog/chunking-strategies-for-rag)
- [Production RAG Strategies That Actually Work — Towards AI](https://towardsai.net/p/machine-learning/production-rag-the-chunking-retrieval-and-evaluation-strategies-that-actually-work)
- [Chatbot UI Design Best Practices 2026 — Widget Chat](https://widget-chat.com/blog/chatbot-ui-design-best-practices/)
- [RAG Citations and Sources — Ailog RAG](https://app.ailog.fr/en/blog/guides/citation-sourcing-rag)
- [Citation-Aware RAG — Tensorlake](https://www.tensorlake.ai/blog/rag-citations)
- [Hybrid Search for RAG — Prem AI Blog](https://blog.premai.io/hybrid-search-for-rag-bm25-splade-and-vector-search-combined/)
- [BM25 vs Hybrid Search in RAG — Medium](https://medium.com/@dewasheesh.rana/bm25-vs-sparse-vs-hybrid-search-in-rag-from-layman-to-pro-e34ff21c4ada)
- [Context Window Management — Agenta](https://agenta.ai/blog/top-6-techniques-to-manage-context-length-in-llms)
- [5 Hidden Prompt Mistakes Ruining RAG Systems — Ragdoll AI](https://www.ragdollai.io/blog/5-hidden-prompt-mistakes-that-are-ruining-your-rag-system)
- [Shadow DOM for Embeddable Widgets — GitHub/surya304](https://github.com/surya304/Embeddable-JS-Widget)
- [5 Must-Have Features for Lead Gen Chatbots — Agentive AIQ](https://agentiveaiq.com/listicles/5-must-have-features-of-a-lead-generation-chatbot-for-consulting-firms)
- [AI Chatbot Statistics 2026 — Hyperleap AI](https://hyperleap.ai/blog/ai-chatbot-statistics-2026)
