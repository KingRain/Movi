"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { getStoredUser, type AuthUser } from "@/lib/auth";

type MoviUserContextValue = {
  user: AuthUser | null;
  setUser: (user: AuthUser | null) => void;
};

const MoviUserContext = createContext<MoviUserContextValue | null>(null);

export function MoviUserProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    setUser(getStoredUser());
  }, []);

  const value = useMemo(() => ({ user, setUser }), [user]);

  return <MoviUserContext.Provider value={value}>{children}</MoviUserContext.Provider>;
}

export function useMoviUser() {
  const ctx = useContext(MoviUserContext);
  if (!ctx) throw new Error("useMoviUser must be used within MoviUserProvider");
  return ctx;
}
