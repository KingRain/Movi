"use client";

import type { ReactNode } from "react";
import { MoviUserProvider } from "@/components/movi-user-provider";

export function Providers({ children }: { children: ReactNode }) {
  return <MoviUserProvider>{children}</MoviUserProvider>;
}
