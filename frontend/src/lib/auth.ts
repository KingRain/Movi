const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
const TOKEN_KEY = "movi-auth-token";
const USER_KEY = "movi-auth-user";

export type AuthUser = { id: number; username: string };

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? (JSON.parse(raw) as AuthUser) : null;
  } catch {
    return null;
  }
}

export function saveSession(token: string, user: AuthUser) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

function authHeaders(): HeadersInit {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}`, "Content-Type": "application/json" } : {};
}

export async function register(username: string, password: string) {
  const res = await fetch(`${API}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail ?? "Registration failed");
  saveSession(data.token, data.user);
  return data as { token: string; user: AuthUser };
}

export async function login(username: string, password: string) {
  const res = await fetch(`${API}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail ?? "Login failed");
  saveSession(data.token, data.user);
  return data as { token: string; user: AuthUser };
}

export async function logout() {
  const token = getToken();
  if (token) {
    await fetch(`${API}/auth/logout`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    }).catch(() => undefined);
  }
  clearSession();
}

export type TasteMovie = {
  tmdb_id: number;
  id: number;
  title: string;
  overview: string;
  poster_url: string | null;
  release_year?: number | null;
  genre_ids?: number[];
  watched?: boolean;
};

export type ServerTaste = {
  watched: number[];
  movies: TasteMovie[];
};

export async function fetchAccountTaste(): Promise<ServerTaste | null> {
  const token = getToken();
  if (!token) return null;
  const res = await fetch(`${API}/account/taste`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) return null;
  return (await res.json()) as ServerTaste;
}

export async function syncMovieToAccount(movie: TasteMovie & { watched: boolean }) {
  const token = getToken();
  if (!token) return;
  await fetch(`${API}/account/movies`, {
    method: "PUT",
    headers: authHeaders(),
    body: JSON.stringify({
      tmdb_id: movie.tmdb_id,
      watched: movie.watched,
      title: movie.title,
      overview: movie.overview,
      poster_url: movie.poster_url,
      release_year: movie.release_year ?? null,
      genre_ids: movie.genre_ids ?? [],
    }),
  });
}

export async function clearAccountTaste() {
  const token = getToken();
  if (!token) return;
  await fetch(`${API}/account/taste`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function fetchGenres(): Promise<{ id: number; name: string }[]> {
  try {
    const res = await fetch(`${API}/movies/genres`);
    if (!res.ok) return [];
    const data = (await res.json()) as { genres: { id: number; name: string }[] };
    return data.genres ?? [];
  } catch {
    return [];
  }
}
