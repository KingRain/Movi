from pathlib import Path
from typing import Annotated, Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).resolve().parent / ".env")

from engine import engine
from guest import movie_genres, recommend_for_watched, search_movies, trending
from metadata import movie_for_item
from recommend import recommend as cf_recommend
from users import (
    clear_taste,
    get_taste,
    login_user,
    logout_user,
    register_user,
    upsert_movie,
    user_from_token,
)

app = FastAPI(title="Movi")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip() or None
    return None


def optional_user(authorization: Annotated[str | None, Header()] = None) -> dict[str, Any] | None:
    return user_from_token(_bearer_token(authorization))


def require_user(user: Annotated[dict[str, Any] | None, Depends(optional_user)]) -> dict[str, Any]:
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


class RegisterBody(BaseModel):
    username: str
    password: str


class LoginBody(BaseModel):
    username: str
    password: str


class MovieTasteBody(BaseModel):
    tmdb_id: int
    watched: bool = False
    title: str = ""
    overview: str = ""
    poster_url: str | None = None
    release_year: int | None = None
    genre_ids: list[int] = Field(default_factory=list)


@app.get("/health")
def health():
    import os

    return {
        "ok": True,
        "model_loaded": engine.ready,
        "tmdb_configured": bool(
            os.environ.get("TMDB_API_KEY") or os.environ.get("TMDB_READ_TOKEN")
        ),
    }


@app.get("/movies/trending")
def movies_trending(k: int = 20):
    return {"movies": trending(k)}


@app.get("/movies/search")
def movies_search(q: str = Query("", min_length=0), k: int = 12):
    return {"movies": search_movies(q, k=k)}


@app.get("/movies/genres")
def movies_genres():
    return {"genres": movie_genres()}


@app.get("/recommend/for-you")
def recommend_for_you(
    watched: str = Query("", description="Comma-separated TMDB movie IDs you've watched"),
    era: str = Query("all", description="all | new | classic"),
    genre_id: int | None = Query(None),
    k: int = 8,
):
    watched_ids = [int(x) for x in watched.split(",") if x.strip().isdigit()]
    era_norm = era if era in {"all", "new", "classic"} else "all"
    return recommend_for_watched(watched_ids, k=k, era=era_norm, genre_id=genre_id)


@app.post("/auth/register")
def auth_register(body: RegisterBody):
    try:
        return register_user(body.username, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/auth/login")
def auth_login(body: LoginBody):
    try:
        return login_user(body.username, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.post("/auth/logout")
def auth_logout(authorization: Annotated[str | None, Header()] = None):
    token = _bearer_token(authorization)
    if token:
        logout_user(token)
    return {"ok": True}


@app.get("/auth/me")
def auth_me(user: Annotated[dict[str, Any] | None, Depends(optional_user)]):
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"user": user}


@app.get("/account/taste")
def account_get_taste(user: Annotated[dict[str, Any], Depends(require_user)]):
    return get_taste(user["id"])


@app.put("/account/movies")
def account_upsert_movie(body: MovieTasteBody, user: Annotated[dict[str, Any], Depends(require_user)]):
    upsert_movie(user["id"], body.model_dump())
    return get_taste(user["id"])


@app.delete("/account/taste")
def account_clear_taste(user: Annotated[dict[str, Any], Depends(require_user)]):
    clear_taste(user["id"])
    return {"watched": [], "movies": []}


# Legacy demo endpoint (KFGAN/music dataset users 0–1871)
@app.get("/recommend/{user_id}")
def recommend(user_id: int, k: int = 10):
    if engine.ready:
        recs = engine.recommend(user_id, k=k)
        movies = [movie_for_item(i, score=round(s, 3)) for i, s in recs]  # type: ignore[misc]
        mode = "kfgan"
    else:
        recs = cf_recommend(user_id, k=k)
        movies = [movie_for_item(i, score=round(s, 3)) for i, s in recs]
        mode = "cf"
    return {
        "user_id": user_id,
        "movies": movies,
        "mode": mode,
        "note": "Demo only — uses music-dataset user IDs. Use /recommend/for-you for real visitors.",
    }


@app.get("/explain/{user_id}/{movie_id}")
def explain(user_id: int, movie_id: int):
    data = engine.explain(user_id, movie_id)
    data["movie"] = movie_for_item(movie_id)
    return data


if __name__ == "__main__":
    r = recommend_for_you(likes="550,155", k=3)
    assert len(r["movies"]) >= 1
    print("ok", r["movies"][0]["title"])
