# Architecture

## Goal
Build a Procurement RAG assistant that answers natural-language questions by retrieving from four heterogeneous data sources — SQLite, PDF catalog, JSON specs, scanned invoice — and citing every claim back to its source.

## High-level flow

```
┌────────────┐   POST /chat (SSE)   ┌─────────────────────────────────────────┐
│  Next.js   │ ───────────────────▶ │  FastAPI                                │
│  shadcn/ui │ ◀── token stream ─── │  ├── QueryRouter (function calling)     │
└────────────┘                      │  ├── HybridRetriever (BM25 + semantic)  │
                                    │  ├── SQLConnector (whitelist SELECT)    │
                                    │  └── LLMProvider (OpenAI / Groq)        │
                                    └─────────────────────────────────────────┘
                                                │
                                                ▼
                                ┌──────────────────────────────────┐
                                │  Indexed at startup:             │
                                │  ├── ChromaDB (semantic)         │
                                │  └── BM25Okapi (keyword)         │
                                │       both built from 132 chunks │
                                └──────────────────────────────────┘
                                                │
                                                ▼
                                ┌──────────────────────────────────┐
                                │  Connectors → Chunk[]            │
                                │  ├── SQLConnector  (103 chunks)  │
                                │  ├── PDFProcessor  (9 chunks)    │
                                │  ├── JSONLoader    (18 chunks)   │
                                │  └── ImageOCR      (2 chunks)    │
                                └──────────────────────────────────┘
```

## Per-query lifecycle

1. **Frontend** posts `{message}` to `/chat`.
2. **Router** (LLM with `route_query` tool) emits `RouteDecision`:
   - `sources`: subset of `{sql_semantic, sql_query, pdf, json, image}`
   - `sql_query`: optional safe SELECT for aggregates / joins
   - `reasoning`: 1-line rationale
3. **Retrieval** runs in parallel over the chosen sources:
   - If `sql_query` set → `SQLConnector.execute()` with whitelist, results wrapped as a synthetic chunk.
   - For each source tag → `HybridRetriever.retrieve(query, k=5, source_filter=[...])`.
4. **Hybrid fusion** = BM25 + ChromaDB semantic, merged via Reciprocal Rank Fusion (`score = Σ 1/(60+rank)`).
5. **Context assembly**: top chunks formatted as `[source_id]\n<truncated content>` blocks, capped at 12 chunks × 800 chars.
6. **Generation**: LLM called with strict system prompt — must cite via `[source_id]` markers and emit the canned "I don't have this information…" line when context is empty.
7. **SSE stream**: events `route` → `citations` → `token`* → `done`.

## Key design decisions

### 1. Router uses function calling, not classify-by-prompt
Function calling forces a JSON shape (`sources[]`, `sql_query?`, `reasoning`) which is parseable, deterministic, and retry-safe. Classification by free-form prompt routinely produces broken JSON or hallucinated sources.

### 2. Two SQL paths: `sql_query` and `sql_semantic`
- `sql_query`: LLM generates an explicit SELECT (whitelisted: SELECT-only, no semicolons, no DDL/DML). Best for aggregates (`SUM`, `COUNT`), joins, exact lookups by primary key.
- `sql_semantic`: embedding search over per-row "semantic descriptions". Best for vague questions where exact keys aren't known.

The router picks one or both. `SQLConnector.execute()` enforces safety regardless of caller.

### 3. Hybrid retrieval (BM25 + semantic)
Catalog questions hinge on exact SKU tokens (`SKU-LED-100`) — pure semantic search misses these. BM25 handles keyword precision, semantic handles intent ("low stock items"). RRF fuses by rank, not raw score, so we don't need cross-source normalisation.

### 3a. Retrieval modes
The pipeline supports three deployment shapes via `EMBEDDING_PROVIDER`:

| Mode | env value | RAM | Image | Used by |
|---|---|---|---|---|
| Full hybrid (OpenAI) | `openai` | ~150 MB | ~700 MB | local dev with paid key |
| Full hybrid (free) | `fastembed` or `sentence-transformers` | ~150–500 MB | 1.3–3.1 GB | local dev or beefy hosts |
| **BM25-only** | `none` | ~100 MB | ~1 GB | **Render free 512 MB** (what's deployed) |

Render free tier's 512 MB cap couldn't load any embedding stack without OOM (verified empirically — even fastembed ONNX hit `Killed`). The engine constructor accepts `vector_store=None`; `HybridRetriever` then short-circuits to BM25 alone. Because the router (an LLM call, not a retrieval) selects sources and most questions resolve via `sql_query`, end-to-end answer quality is unchanged on the 13 evaluation questions.

### 4. Chunk schema is uniform across sources
Every connector emits `Chunk(chunk_id, content, source_id, source_type, metadata)`. The retrieval layer is source-agnostic; new connectors plug in without changes downstream. `source_id` doubles as the citation token surfaced inline.

### 5. Provider abstraction (Bonus 1)
`LLMProvider` and `EmbeddingProvider` are ABCs with two implementations each:
- LLM: `OpenAIProvider` (gpt-4o-mini), `GroqProvider` (llama-3.3-70b — OpenAI-compatible API)
- Embeddings: `OpenAIEmbeddingProvider` (text-embedding-3-small, 1536d), `SentenceTransformerProvider` (all-MiniLM-L6-v2, 384d, local CPU)

Toggle with env (`LLM_PROVIDER`, `EMBEDDING_PROVIDER`). ChromaDB collections are dimension-suffixed (`procurement_openai`, `procurement_sentence_transformers`) so swapping providers doesn't collide.

### 6. Anti-hallucination ("I don't know" gate)
Three layers:
- Router can return `sources=[]` for unanswerable questions → engine bypasses LLM and returns canned IDK text.
- After retrieval, if `chunks=[]` → same canned response.
- System prompt: "If context insufficient, reply exactly: 'I don't have this information in the available data sources.' Never invent data."

This is what allows the system to handle Q10 ("shipping tracking number") truthfully.

### 7. Streaming with citations-first
SSE event order is `route → citations → token → done`. The frontend renders citation badges *before* the answer text streams in, so the user sees the sources up front. Citations are clickable popovers showing the chunk preview.

### 8. OCR robustness via PSM 6 + qty fallback
Tesseract default (PSM 3) drops the invoice's PO Number / Date header on this scan. PSM 6 ("uniform block") preserves it. Tesseract still occasionally truncates `PO-2847` → `PO-284`; the line-item regex therefore makes the qty column optional and derives `qty = round(line_total / unit_price)` from the prices Tesseract reads reliably. The RAG layer cross-validates against the SQL DB (PO-2847 has matching total $3,285).

## File map

```
backend/app/
  main.py                 # FastAPI + CORS + lifespan
  lifespan.py             # builds engine once at startup
  settings.py             # pydantic-settings (env)
  rag_engine.py           # orchestration
  query_router.py         # function-calling router
  data_sources/
    chunk_schema.py       # Chunk, ScoredChunk pydantic
    sql_connector.py      # SQLite + whitelist + index_all
    pdf_processor.py      # pdfplumber + SKU regex
    json_loader.py        # flatten product specs
    image_ocr.py          # tesseract PSM 6 + invoice regex
  retrieval/
    vector_store.py       # ChromaDB persistent wrapper
    bm25_index.py         # rank_bm25
    hybrid_search.py      # RRF fusion
  providers/
    llm_provider.py       # OpenAI + Groq impls
    embedding_provider.py # OpenAI + sentence-transformers
    factory.py            # build from settings
  routes/
    chat.py               # /chat SSE + /chat/sync
    upload.py             # /upload PDF/JSON/image
    health.py             # /health, /sources
  streaming/sse_formatter.py
  models/route_decision.py # RouteDecision, RAGResponse, Citation
  scripts/build_index.py   # CLI: build the index from data_dir
frontend/
  app/
    page.tsx              # renders ChatInterface
    components/
      chat-interface.tsx  # state machine, SSE driver
      message-list.tsx    # auto-scroll
      message-bubble.tsx  # parses [source_id] inline
      source-citation-badge.tsx  # clickable popover
      status-indicator.tsx       # routing/retrieving/streaming
      chat-input.tsx
      file-upload.tsx
  lib/
    api-client.ts         # SSE consumer
    citation-parser.ts    # regex-splits text+citations
    types.ts
```

## Trade-offs

| Choice | Why | Cost |
|---|---|---|
| ChromaDB persistent (local file) | Simple, no cloud auth, fast cold start | Won't scale past ~10k chunks |
| BM25 in-memory only | No persistence overhead | Re-tokenise each startup (cheap for 132 chunks) |
| Tesseract over OpenAI Vision | $0 cost, runs offline | Lower OCR fidelity (lost final digit of PO) |
| sentence-transformers for free path | $0, local | +500 MB image, +3 GB Render disk |
| LLM-generated SQL + whitelist | Lets LLM aggregate exactly | Whitelist must be airtight (SELECT-only, no `;`) |
| Function-calling router | Deterministic JSON | Adds 1 LLM round-trip (~300 ms) |

## Security

- `.env` is gitignored, permissions 600.
- API keys live only in environment variables (Render dashboard for prod).
- SQL whitelist rejects DDL/DML; `;` blocks chained statements.
- File upload validates extension + size (10 MB cap).
- LLM output is React-escaped on render — no `dangerouslySetInnerHTML`.

## Performance budget

| Step | Local | Render free tier |
|---|---|---|
| Index build (132 chunks, OpenAI embed) | ~5s | ~10s |
| Index build (sentence-transformers) | ~6s | ~30s (CPU bound) |
| Router round-trip | 200-500 ms | 500-1500 ms |
| Hybrid retrieval | < 50 ms | < 100 ms |
| LLM generation (gpt-4o-mini, ~150 tokens) | 1-2 s | 1-3 s |
| Cold start (Docker boot) | 8 s | 30-60 s |
