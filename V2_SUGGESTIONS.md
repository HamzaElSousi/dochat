# DocChat — V2+ Suggestions

**Current state:** Deployed and live on shared hosting; full RAG pipeline (ingest → sqlite-vec search → LLM with lead-capture fallback) with 107 offline tests; excellent constraint-driven README — but no CI, and the sub-20ms search claim isn't yet backed by a committed benchmark.

## Prioritized suggestions

1. **Add GitHub Actions CI** — Effort: S
   *What:* A `tests.yml` workflow: checkout → pip install → `pytest -v` on Python 3.10/3.12; add the badge to the README.
   *Why:* The tests already run offline with mocked APIs, so this is nearly free — and a green CI badge is the first credibility signal a recruiter scans for. Currently the only portfolio repo with a real deployment but no CI.

2. **Commit a reproducible latency benchmark** — Effort: S
   *What:* A `scripts/benchmark_search.py` that ingests N synthetic docs and reports p50/p95 sqlite-vec query latency; commit the script and one result table to the README.
   *Why:* "Sub-20ms on 256 MB shared hosting" is the repo's headline metric — turning it from a claim into a reproducible number is the highest-leverage 2 hours available here.

3. **Streaming responses (SSE) in the widget** — Effort: M
   *What:* Stream LLM tokens through the CGI response; render progressively in the Shadow DOM widget.
   *Why:* Perceived latency dominates chat UX. Making SSE work under Apache CGI's process model is also exactly the kind of constraint-wrangling this project is known for — great interview story.

4. **Hybrid retrieval: BM25 + vector with reciprocal-rank fusion** — Effort: M
   *What:* Add SQLite FTS5 keyword search alongside sqlite-vec, fuse rankings, keep the same threshold-gated fallback.
   *Why:* FTS5 is built into SQLite (zero new RAM cost — on-brand for this project) and hybrid retrieval is a standard interview topic; measurably better recall on exact-term questions (product names, prices).

5. **Retrieval quality eval suite** — Effort: M
   *What:* A small golden dataset (question → expected chunk/doc) with recall@k and a threshold-sweep report; ideally wired to the sibling `evalkit` project.
   *Why:* Demonstrates the RAG-specific skill recruiters actually probe: how do you know retrieval works and how did you pick 0.35 as the threshold? Cross-linking two portfolio projects doubles the payoff.

6. **Multi-tenant support (one install, many sites)** — Effort: L
   *What:* A `tenant_id` column across documents/chunks/leads/settings, per-tenant API keys, widget config selects the tenant.
   *Why:* Turns a single-site tool into a productized service — the natural "how would you scale this?" answer, and a real freelance revenue path.

7. **Docker-based one-command local demo** — Effort: S
   *What:* `docker compose up` with Ollama bundled: app + local model, zero API keys, seeded sample documents.
   *Why:* Recruiters won't configure SMTP and OpenRouter keys. A 60-second local demo path massively raises the odds anyone actually runs it.

8. **Admin analytics: unanswered-question report** — Effort: S
   *What:* Log below-threshold questions; admin page ranking the most-asked questions with no matching document.
   *Why:* Closes the product loop (tells the owner what content to add) and shows product thinking beyond the pipeline.

## Quick wins (do this weekend)

1. Add the CI workflow + badge (suggestion 1). (S)
2. Write and run `scripts/benchmark_search.py`, paste the p50/p95 table into the README. (S)
3. Seed 3 sample docs + a `make demo` / compose target for the Ollama local path already supported in `.env`. (S)
