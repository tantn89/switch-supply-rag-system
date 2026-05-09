# Setup

## Prerequisites
- Docker + Docker Compose (recommended for backend)
- Node 18+ (for frontend)
- A free **Groq API key** — https://console.groq.com/keys

## 1. Backend (Docker — recommended)

The default stack is **free** (Bonus 1: Groq LLM + fastembed embeddings + Tesseract OCR). Backend runs Python 3.11 with Tesseract pre-installed in the container — no host-level Python or Tesseract setup needed.

```bash
cd backend
cp .env.example .env
chmod 600 .env
# Edit .env: set GROQ_API_KEY=gsk-your-key (the only required value)
cd ..
docker compose up --build
```

First build is ~5 minutes. Subsequent builds use the layer cache and finish in seconds.

API at http://localhost:8000 (OpenAPI docs at `/docs`, health at `/health`).

### Provider switching (optional)
Defaults in `backend/.env.example` already use the free stack. To benchmark against OpenAI:
```
LLM_PROVIDER=openai            # default: groq
EMBEDDING_PROVIDER=openai      # default: fastembed
OPENAI_API_KEY=sk-your-key
```
See `docs/COST_ANALYSIS.md` for the cost / performance comparison.

## 2. Backend (without Docker — advanced)

Requires Python 3.11 (NOT 3.13/3.14 — chromadb 0.5.x compatibility) and Tesseract OS package:

```bash
sudo apt install -y tesseract-ocr build-essential
cd backend
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # edit keys
DATA_DIR=../data uvicorn app.main:app --reload
```

## 3. Frontend

```bash
cd frontend
cp .env.example .env.local
# .env.local sets NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev
```

Open http://localhost:3000.

## 4. Run tests

```bash
docker compose run --rm \
  -v $(pwd)/backend/tests:/app/tests:ro \
  backend python -m pytest /app/tests -v
```

Without Docker:
```bash
cd backend && DATA_DIR=../data python -m pytest tests -v
```

## 5. Production deploy

### Backend → Render
1. Push to GitHub (already done if you cloned this repo).
2. Render Dashboard → New → Blueprint → connect this repo.
3. Render auto-discovers `render.yaml`.
4. In the Render dashboard, set the secret env var `GROQ_API_KEY`. Other env values come from `render.yaml`. (`OPENAI_API_KEY` is optional — only needed if you switch providers.)
5. After deploy, copy the public URL to `frontend/.env.production` (or Vercel env).

### Frontend → Vercel
1. Vercel Dashboard → Import Git Repository → pick this repo, root `frontend/`.
2. Set env: `NEXT_PUBLIC_API_URL=https://<your-render-service>.onrender.com`.
3. Deploy.

### CORS
After deploy, update `ALLOWED_ORIGINS` in Render env to include the Vercel domain. Restart service.

## 6. Troubleshooting

| Symptom | Fix |
|---|---|
| `unable to open database file` | `DATA_DIR` not pointing to `data/` containing `procurement.db`. |
| OCR returns empty | Image preprocessing fails — check Tesseract is installed (Docker handles this). |
| Cold start > 60s on Render | Free tier suspends after 15 min idle. Optional: GitHub Action cron pings `/health` every 10 min. |
| `GROQ_API_KEY required` (or OpenAI variant) | The selected provider in `LLM_PROVIDER` requires its corresponding key. Default is `groq`. |
| ChromaDB collection dimension mismatch | Switching embedding provider after building: delete `chroma_db/` and rebuild. |
