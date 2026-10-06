"use client";

import { useState } from "react";
import { clearSession, getStoredUser, login, logout, register, type AuthUser } from "@/lib/auth";

type Props = {
  user: AuthUser | null;
  onAuthChange: (user: AuthUser | null) => void;
};

export function AuthPanel({ user, onAuthChange }: Props) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result =
        mode === "login" ? await login(username, password) : await register(username, password);
      onAuthChange(result.user);
      setOpen(false);
      setUsername("");
      setPassword("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  };

  const signOut = async () => {
    await logout();
    clearSession();
    onAuthChange(null);
    setOpen(false);
  };

  if (user) {
    return (
      <div className="auth-wrap">
        <button type="button" className="pill-ghost-sm" onClick={() => setOpen((v) => !v)}>
          {user.username}
        </button>
        {open && (
          <div className="auth-popover">
            <p className="text-sm text-carbon-vellum">Signed in as {user.username}</p>
            <p className="mt-1 text-xs text-ash">Your watched & loved films sync to this device.</p>
            <button type="button" className="auth-submit mt-3" onClick={signOut}>
              Sign out
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="auth-wrap">
      <button type="button" className="pill-ghost-sm" onClick={() => setOpen((v) => !v)}>
        Account
      </button>
      {open && (
        <div className="auth-popover">
          <div className="auth-tabs">
            <button
              type="button"
              className={mode === "login" ? "is-active" : ""}
              onClick={() => setMode("login")}
            >
              Sign in
            </button>
            <button
              type="button"
              className={mode === "register" ? "is-active" : ""}
              onClick={() => setMode("register")}
            >
              Create account
            </button>
          </div>
          <form onSubmit={submit} className="mt-3 space-y-3">
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Username"
              className="auth-input"
              autoComplete="username"
              required
              minLength={3}
            />
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Password"
              className="auth-input"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              required
              minLength={6}
            />
            {error && <p className="text-xs text-iris-glow">{error}</p>}
            <button type="submit" className="auth-submit w-full" disabled={busy}>
              {busy ? "…" : mode === "login" ? "Sign in" : "Create account"}
            </button>
          </form>
        </div>
      )}
    </div>
  );
}

export function useInitialUser(): AuthUser | null {
  return getStoredUser();
}
