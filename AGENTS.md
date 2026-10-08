# AGENTS.md — Movi Project Architecture & Knowledge Graph Guide

> Comprehensive context, architectural blueprint, and domain knowledge for AI agents working on **Movi**.

---

## 1. Project Overview & Tech Stack

**Movi** is a cinema recommendation platform powered by Knowledge Graph (KG) embeddings and Fine-grained Attention Networks ([KFGAN](https://github.com/weiwang1992/KFGAN)), augmented by real-time TMDB metadata and implicit user micro-behavior telemetry.

### Technology Stack
* **Backend:** Python 3.11–3.13, FastAPI, Uvicorn, SQLite, NumPy, PyTorch (optional training).
* **Frontend:** Next.js (App Router), React, TypeScript, Tailwind CSS, Lucide icons, YouTube iframe player API.
* **Metadata & Fallbacks:** The Movie Database (TMDB) API + static fallback catalog in `backend/data/fallback_movies.json`.
* **State & Persistence:** SQLite (`backend/data/movi.db`) for user accounts, taste profiles, guest sessions, and telemetry logs.

---

## 2. Knowledge Graph & KFGAN Mechanics

### The Core "3-Item Set" (Triplets)
In KG recommender systems and KFGAN, the fundamental atomic unit is the **Knowledge Graph Triplet**:
$$(h, r, t) = (\text{head entity}, \text{relation}, \text{tail entity})$$

In KFGAN (`backend/kfgan/src/data_loader.py` & `model.py`):
* **Entities ($h, t$):** Movies, directors, actors, genres, keywords, user nodes.
* **Relations ($r$):** The semantic edge connecting $h$ and $t$.
* **Ripple Sets / Triple Sets:** Hierarchical multi-hop subgraphs propagated over $L$ layers:
  1. `user_init_triple_set`: Interacted items $\to$ KG relations $\to$ neighbor entities.
  2. `item_potential_triple_set`: Collaborative items related to the candidate item $\to$ KG relations.
  3. `user_potential_triple_set`: Collaborative items clicked by similar users $\to$ KG relations.
  4. `item_origin_triple_set`: Candidate item direct KG relations.

### Knowledge Attention & Scoring
KFGAN embeds entities and relations into a continuous vector space ($\mathbb{R}^d$):
$$\text{Attn}(h, r) = \text{Softmax}\left(W_2 \cdot \sigma(W_1 [h_{\text{emb}} \parallel r_{\text{emb}}])\right)$$
$$\text{Embedding}_i = \sum \text{Attn}(h, r) \cdot t_{\text{emb}}$$
Final prediction combines aggregated representations $e_u$ and $e_i$ using inner product and sigmoid:
$$\hat{y}_{u, i} = \sigma(e_u^\top e_i)$$

---

## 3. Multi-Behavior KG Enhancement (Micro-Behavior Telemetry)

Rather than treating user-item interactions as sparse binary signals ($0$ or $1$), Movi tracks implicit micro-behaviors to model user intent before an explicit rating is provided.

### Behavioral Relations & Intent Tiers
Micro-behaviors are discretized into semantic relation types or weighted seeds:

| Relation / Tier | Trigger Condition | Weight ($w$) | Semantic Role |
| :--- | :--- | :--- | :--- |
| `r_watched` | Marked watched in UI | $1.00$ | Explicit confirmation of core taste |
| `r_trailer_complete` | Trailer played $\ge 50\%$ or $\ge 30\text{s}$ | $0.85$ | High-affinity hook & genuine interest |
| `r_trailer_start` | Trailer played $2\text{s} - 10\text{s}$ | $0.45$ | Visual curiosity / initial engagement |
| `r_hover_deep` | Card hovered $\ge 1500\text{ms}$ | $0.25$ | Cognitive consideration (reading details) |
| `hover_shallow` | Hover $< 1500\text{ms}$ | *Ignored* | Accidental cursor transit (filtered out) |

### Recency Decay
Telemetry incorporates an exponential time-decay function:
$$w_{\text{effective}} = w \cdot e^{-\lambda \Delta t}$$
* $\lambda = 0.0001 \text{ min}^{-1}$ (half-life $\approx 5$ days).
* Session interactions have high immediate weight for tonight's recommendations, while older implicit touches gradually fade relative to explicit watch history.

### Expanded Domain Knowledge Graph Relations
To provide semantic reasoning paths for why a trailer or movie caught interest, entities are linked via:
* `directed_by`: Movie $\to$ Director entity.
* `starred_by`: Movie $\to$ Top 3 billed actors.
* `has_genre`: Movie $\to$ Genre entity.
* `has_keyword`: Movie $\to$ Tropes/themes (*time travel*, *cyberpunk*, *heist*).
* `belongs_to_collection`: Movie $\to$ Franchise/Cinematic Universe.

---

## 4. Architecture & Data Flow

```
[User Browser]
   │
   ├─ 1. Hover >= 1.5s ──────► useHoverDwell ──┐
   ├─ 2. Trailer countdown ──► Video Iframe ────┤
   ├─ 3. Playback progress ──► Telemetry Hook ──┴─► Batch Queue (localStorage)
   │                                                     │
   │                                                     ▼ (Every 5s or pagehide)
[Backend: FastAPI]                                POST /telemetry/interactions
   │                                                     │
   ├─ user_interactions (SQLite) ◄───────────────────────┘
   │
   ├─ GET /recommend/for-you
   │     ├─ Reads explicit watched list
   │     ├─ Reads implicit_seeds via intent_seed_tmdb_ids()
   │     ├─ Merges seed items with boost weights: boost = max(1.0, w)
   │     └─ Calls TMDB recommendation graph / KFGAN engine
   │
   └─ Ranked Movie Recommendations with Match % & Reason
```

---

## 5. File Structure & Responsibilities

### Backend (`/backend`)
* [`main.py`](file:///c:/Users/samjo/OneDrive/Documents/ProjectFiles/Movi/backend/main.py): FastAPI application routes:
  * `/recommend/for-you`: Primary recommendation endpoint taking `watched`, `era`, `genre_id`, and `X-Guest-Token`.
  * `/telemetry/interactions`: Batch and single interaction ingestion.
  * `/movies/browse`: Curated sections (Trending, Recent, Top Rated, by Genre).
  * `/movies/{tmdb_id}/videos`: Trailer video resolution.
* [`telemetry.py`](file:///c:/Users/samjo/OneDrive/Documents/ProjectFiles/Movi/backend/telemetry.py): Interaction classifier, recency decay calculator, guest token manager, and intent seed generator (`intent_seed_tmdb_ids`).
* [`guest.py`](file:///c:/Users/samjo/OneDrive/Documents/ProjectFiles/Movi/backend/guest.py): Hybrid guest recommendation generator combining explicit watched seeds and weighted implicit seeds.
* [`metadata.py`](file:///c:/Users/samjo/OneDrive/Documents/ProjectFiles/Movi/backend/metadata.py): TMDB API caller, credits/keywords extraction, static fallback catalogue, and YouTube trailer key resolver (`tmdb_trailer_key`).
* [`db.py`](file:///c:/Users/samjo/OneDrive/Documents/ProjectFiles/Movi/backend/db.py): SQLite schema initialization (`users`, `sessions`, `user_movies`, `guest_sessions`, `user_interactions`).
* [`engine.py`](file:///c:/Users/samjo/OneDrive/Documents/ProjectFiles/Movi/backend/engine.py): KFGAN neural model loader and inference scorer (`recommend`, `explain`).
* [`kfgan/`](file:///c:/Users/samjo/OneDrive/Documents/ProjectFiles/Movi/backend/kfgan): KFGAN research codebase (`model.py`, `data_loader.py`, `train.py`).

### Frontend (`/frontend`)
* [`src/components/movi-home.tsx`](file:///c:/Users/samjo/OneDrive/Documents/ProjectFiles/Movi/frontend/src/components/movi-home.tsx): Core cinema dashboard, filter bar, browse sections, and recommendations view.
* [`src/components/movie-poster-card.tsx`](file:///c:/Users/samjo/OneDrive/Documents/ProjectFiles/Movi/frontend/src/components/movie-poster-card.tsx): Card with interactive hover timer ring, YouTube trailer playback, mute button, and watched toggle.
* [`src/lib/use-hover-dwell.ts`](file:///c:/Users/samjo/OneDrive/Documents/ProjectFiles/Movi/frontend/src/lib/use-hover-dwell.ts): Debounced hover dwell duration tracker (1500ms intentionality gate).
* [`src/lib/use-trailer-watch-telemetry.ts`](file:///c:/Users/samjo/OneDrive/Documents/ProjectFiles/Movi/frontend/src/lib/use-trailer-watch-telemetry.ts): Active video watch duration counter that dispatches `trailer_progress` and `trailer_complete` events.
* [`src/lib/auth.ts`](file:///c:/Users/samjo/OneDrive/Documents/ProjectFiles/Movi/frontend/src/lib/auth.ts): Client state for auth, guest tokens (`X-Guest-Token`), and batch telemetry queue (`flushInteractionEvents`, `sendInteractionEvent`).

---

## 6. How to Run & Test

### Backend
```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```
Verify health:
```powershell
curl http://127.0.0.1:8000/health
```

### Frontend
```powershell
cd frontend
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000).

---

## 7. Guidelines for Autonomous Agents

1. **Windows Friendly:** Always use Windows-compatible PowerShell commands. Never call Linux-specific `cd path && command` patterns; pass `Cwd` or use `;`.
2. **Intentionality Thresholds:** Never remove the $1.5\text{s}$ hover dwell gate; without it, random mouse movement pollutes the KG with false positive interest.
3. **Trailer Playback:** YouTube embeds must always begin with `mute=1` and `autoplay=1`. Users can unmute via the card's audio toggle.
4. **Resilience to TMDB Outages:** Any new metadata or trailer feature must degrade gracefully to `STATIC_TRAILERS` and `FALLBACK` movies if `TMDB_API_KEY` is unset or rate-limited.
