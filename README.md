# Movi

Movie recommendations via [KFGAN](https://github.com/weiwang1992/KFGAN).

## Setup

```bash
# Backend (API — Python 3.13 compatible)
cd backend && pip install -r requirements.txt && uvicorn main:app --reload --host 127.0.0.1 --port 8000

# Optional KFGAN training (needs torch)
pip install -r requirements-train.txt && python train_model.py

# Frontend (new terminal)
cd frontend && cp .env.local.example .env.local && npm run dev
```

Open http://localhost:3000 — picks load automatically from `/recommend/0`.

Optional: set `TMDB_API_KEY` in `backend/.env` for live TMDB metadata (built-in catalog works without it).

Train KFGAN for neural recommendations: `cd backend && python train_model.py`

Design tokens live in `DESIGN.md` and `frontend/src/app/globals.css`.

## Stack (add when needed)

- **Vectors**: Milvus/Qdrant for ANN on `e_u`, `e_i`
- **Graph**: Neo4j for ripple sets + explanation paths
- **Cache**: Redis for TMDB/OMDb responses
- **Frontend**: Next.js on Vercel + React Query + D3 graph viz
