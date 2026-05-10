# Switch Supply Procurement RAG Assistant created by TanTran

Multi-source Retrieval-Augmented Generation system for procurement intelligence. Built for the Switch Supply AI Engineer technical exam.

**Live demo:**
- Frontend: https://switch-supply-rag.vercel.app
- Backend API: https://switch-supply-rag-backend-1wz2.onrender.com
- - API docs: `/docs` on the backend

## What it does

Answers procurement questions by routing to the right data source(s):

| Question style | Source |
|---|---|
| "What's in stock for SKU-LED-100?" | SQLite DB |
| "What's the catalog price?" | PDF |
| "What are the certifications?" | JSON |
| "Extract invoice total" | Image OCR |
| "Compare catalog vs PO price" | PDF + SQL |
| "Tracking number?" | None → "I don't know" |

## Stack

- **Backend:** Python 3.11, FastAPI, ChromaDB, BM25, OpenAI / Groq, sentence-transformers, Tesseract OCR
- **Frontend:** Next.js 14, shadcn/ui, Tailwind CSS, TypeScript
- **Retrieval:** Hybrid search — BM25 + semantic embeddings, fused via Reciprocal Rank Fusion
- **Routing:** OpenAI function calling (deterministic JSON schema)
- **Deploy:** Backend → Render (Docker), Frontend → Vercel

## Quick start

### Prereqs
- Docker + Docker Compose
- Node 18+
- OpenAI API key (or Groq key for free path)

### Backend (Docker — recommended)
```bash
cp backend/.env.example backend/.env
# edit backend/.env, set OPENAI_API_KEY
docker compose up --build
# backend at http://localhost:8000, docs at /docs
```

### Frontend
```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
# open http://localhost:3000
```

## Documentation

- [`docs/SETUP.md`](docs/SETUP.md) — Local + production setup
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — Design decisions, query flow, trade-offs
- [`docs/TEST_RESULTS.md`](docs/TEST_RESULTS.md) — Answers to all 10 evaluation questions
- [`docs/COST_ANALYSIS.md`](docs/COST_ANALYSIS.md) — OpenAI vs free-stack cost & accuracy

## Repo layout

```
backend/
  app/
    main.py                    # FastAPI app + lifespan
    rag_engine.py              # Orchestration
    query_router.py            # Function-calling source router
    data_sources/              # SQL, PDF, JSON, OCR connectors
    retrieval/                 # ChromaDB + BM25 + hybrid fusion
    providers/                 # LLM + embedding provider abstractions
    routes/                    # /chat (SSE), /upload, /health
  Dockerfile
  requirements.txt
frontend/
  app/                         # Next.js App Router
    components/                # Chat UI, citation badge, file upload
  lib/                         # SSE client, citation parser
data/                          # SQLite + PDF + JSON + image (provided)
docs/                          # Submission docs
docker-compose.yml
render.yaml                    # Render Blueprint for backend
```

## Bonuses implemented

- **Bonus 1 (15 pts):** Free-stack alternative — Groq llama-3.3-70b + sentence-transformers + Tesseract. See COST_ANALYSIS.md.
- **Bonus 2 (10 pts):** Hybrid Search (BM25 + semantic, RRF fusion).
- **Bonus 3 (5 pts):** Docker + Render Blueprint for one-click deploy.
