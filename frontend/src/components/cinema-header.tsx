"use client";

import Link from "next/link";
import { CinemaNav } from "@/components/cinema-nav";

type Props = {
  variant?: "overlay" | "page";
};

export function CinemaHeader({ variant = "overlay" }: Props) {
  return (
    <header className={variant === "page" ? "cinema-header cinema-header-page" : "cinema-header"}>
      <Link href="/" className="cinema-logo">
        Movi
      </Link>
      <CinemaNav variant={variant} />
      <div className="cinema-header-auth" aria-hidden />
    </header>
  );
}
