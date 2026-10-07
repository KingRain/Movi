const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
const TOKEN_KEY = "movi-auth-token";
const USER_KEY = "movi-auth-user";
const GUEST_TOKEN_KEY = "movi-guest-token";
const TELEMETRY_QUEUE_KEY = "movi-telemetry-queue";
export const TASTE_STORAGE_KEY = "movi-taste";
export const MOVIE_CACHE_STORAGE_KEY = "movi-movie-cache";

export type InteractionPayload = {
  tmdb_id: number;
  event_type: "hover" | "trailer_progress" | "trailer_complete";
  duration_ms: number;
  completion_ratio?: number;
  timestamp: number;
};

let flushTimer: number | null = null;
let flushing = false;
const flushListeners = new Set<() => void>();

export function onTelemetryFlushed(listener: () => void): () => void {
  flushListeners.add(listener);
  return () => flushListeners.delete(listener);
}

function notifyFlushed() {
  for (const fn of flushListeners) fn();
}

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
  if (!token) return false;
  const res = await fetch(`${API}/account/taste`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  return res.ok;
}

export async function clearServerInteractions() {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  else headers["X-Guest-Token"] = getGuestToken();
  const res = await fetch(`${API}/telemetry/interactions`, { method: "DELETE", headers });
  return res.ok;
}

export function clearLocalMoviData() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TASTE_STORAGE_KEY);
  localStorage.removeItem(MOVIE_CACHE_STORAGE_KEY);
  localStorage.removeItem(TELEMETRY_QUEUE_KEY);
  localStorage.removeItem(GUEST_TOKEN_KEY);
}

export async function searchMovies(query: string, k = 20): Promise<TasteMovie[]> {
  const q = query.trim();
  if (q.length < 2) return [];
  const res = await fetch(`${API}/movies/search?q=${encodeURIComponent(q)}&k=${k}`);
  if (!res.ok) return [];
  const data = (await res.json()) as { movies: TasteMovie[] };
  return data.movies ?? [];
}

export function getGuestToken(): string {
  if (typeof window === "undefined") return "";
  let token = localStorage.getItem(GUEST_TOKEN_KEY);
  if (!token) {
    token = crypto.randomUUID().replace(/-/g, "");
    localStorage.setItem(GUEST_TOKEN_KEY, token);
  }
  return token;
}

function readQueue(): InteractionPayload[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(localStorage.getItem(TELEMETRY_QUEUE_KEY) ?? "[]") as InteractionPayload[];
  } catch {
    return [];
  }
}

function writeQueue(events: InteractionPayload[]) {
  localStorage.setItem(TELEMETRY_QUEUE_KEY, JSON.stringify(events));
}

function telemetryHeaders(): HeadersInit {
  const token = getToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  else headers["X-Guest-Token"] = getGuestToken();
  return headers;
}

export async function flushInteractionEvents(): Promise<void> {
  if (typeof window === "undefined" || flushing) return;
  const queue = readQueue();
  if (!queue.length) return;
  flushing = true;
  try {
    const res = await fetch(`${API}/telemetry/interactions`, {
      method: "POST",
      headers: telemetryHeaders(),
      body: JSON.stringify({ events: queue, guest_token: getGuestToken() }),
      keepalive: true,
    });
    if (res.ok) {
      const data = (await res.json()) as { guest_token?: string };
      if (data.guest_token) localStorage.setItem(GUEST_TOKEN_KEY, data.guest_token);
      writeQueue([]);
      notifyFlushed();
    }
  } catch {
    /* keep queue for retry */
  } finally {
    flushing = false;
  }
}

function scheduleFlush() {
  if (flushTimer !== null) return;
  flushTimer = window.setTimeout(() => {
    flushTimer = null;
    void flushInteractionEvents();
  }, 5000);
}

export function sendInteractionEvent(event: Omit<InteractionPayload, "timestamp">) {
  if (typeof window === "undefined") return;
  if (event.event_type === "hover" && event.duration_ms < 1500) return;

  const payload: InteractionPayload = { ...event, timestamp: Date.now() };
  writeQueue([...readQueue(), payload]);
  scheduleFlush();
}

export function installTelemetryBeacon() {
  if (typeof window === "undefined") return () => undefined;
  const onUnload = () => {
    void flushInteractionEvents();
  };
  window.addEventListener("pagehide", onUnload);
  return () => window.removeEventListener("pagehide", onUnload);
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
