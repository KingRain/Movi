# Movi — Knowledge-graph recommendations

Movi improves movie picks by combining **explicit taste** (films you mark as watched) with **implicit behavior** (how long you hover, whether you start or finish a trailer) on top of a **movie knowledge graph (KG)**. The goal is richer signals than stars-or-clicks alone, and explanations that follow graph paths—not only “people also watched.”

## Knowledge graph implementation

We maintain two complementary graph layers:

1. **TMDB domain graph** (`backend/kg/tmdb_graph.py`, `backend/kg_builder.py`)  
   Movies link to directors, cast, genres, collections, and keywords. Triples use a unified relation registry (`directed_by`, `starred_by`, `has_genre`, `belongs_to_collection`, `has_keyword`, etc.) and can be exported to `backend/data/kg_expanded.txt` for training or offline analysis.

2. **Behavior-augmented relations** (same registry + `backend/telemetry.py`)  
   User interactions are mapped to dedicated KG edges with tiered weights:
   - `r_watched` — explicit watched / My List
   - `r_trailer_complete` — trailer viewed ~≥50% (or complete event)
   - `r_trailer_start` — meaningful trailer engagement (~1s+ with sufficient progress)
   - `r_hover_deep` — long hover (≥3s) on a title card  

   Raw UI events are stored in SQLite (`user_interactions`), aggregated per movie, and fed into recommendation seeds and explain paths.

3. **KFGAN-style path reasoning** (`backend/engine.py`, vendored `backend/kfgan/`)  
   When a trained checkpoint is present, we score candidates with **Knowledge-aware Fine-grained Attention Networks (KFGAN)** over ripple-style user/item paths on the KG. For production `/recommend/for-you`, we blend **TMDB similar-movie expansion** from all seeds (watched + implicit) with vote-weighted ranking (`backend/guest.py`).

**Why predictions improve:**  
- **Watched** titles anchor taste.  
- **Hover** and **trailer** events add *intent* before a user commits to marking watched—especially useful for cold start and guest sessions (`X-Guest-Token`).  
- **Implicit seeds** (`intent_seed_tmdb_ids`) merge into the same pool as watched IDs, so one “Recommendations” row reflects both explicit and behavioral taste.  
- **Graph edges** (cast, genre, behavior tiers) support multi-hop explanations in `engine.explain()` (domain edges + behavior paths + KFGAN triples when available).

## What we track (frontend → API)

| Client event | Stored interaction (examples) | Used for |
|--------------|-------------------------------|----------|
| Hover ≥1.5s | `hover` / `hover_deep` | Weak–strong interest signal |
| Trailer starts | `trailer_progress` → `trailer_start` | Strong intent |
| Trailer progress / exit | `trailer_progress` / `trailer_complete` | Engagement depth |
| Mark watched (+) | `watched` via account/guest taste | Primary seed |

Events batch to `POST /telemetry/interactions` and flush on a timer; successful flush can refresh `/recommend/for-you` so the row updates as you browse.

## Research references

- **KFGAN (primary neural KG recommender baseline in-repo):**  
  Wang W, Shen X, Yi B, et al. *Knowledge-aware fine-grained attention networks with refined knowledge graph embedding for personalized recommendation.* Expert Systems with Applications, 2024.  
  Implementation: [weiwang1992/KFGAN](https://github.com/weiwang1992/KFGAN) (see also `backend/kfgan/README.md`).

- **RippleNet (path-propagating preferences on a KG — cited by the KFGAN codebase):**  
  Wang H, Zhang F, Xiang A, et al. *RippleNet: Propagating User Preferences on the Knowledge Graph for Recommender Systems.* CIKM 2018.

Movi’s **live** visitor path emphasizes TMDB graph expansion + telemetry-weighted seeds; full retraining on `kg_expanded.txt` extends the KFGAN data loader with merged behavior items (`merge_behavior_items` in `backend/kfgan/src/data_loader.py`) for offline KG-enhanced training.
