"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

type Props = {
  variant?: "overlay" | "page";
};

export function CinemaNav({ variant = "overlay" }: Props) {
  const pathname = usePathname();
  const onHome = pathname === "/";
  const onSearch = pathname === "/search";
  const onProfile = pathname === "/profile";

  const linkClass = (active: boolean) =>
    `hub-nav-item${active ? " is-active" : ""}${variant === "page" ? " hub-nav-item-page" : ""}`;

  return (
    <nav className="cinema-nav-pill" aria-label="Main">
      <Link href="/" className={linkClass(onHome)}>
        Home
      </Link>
      <Link href="/#catalog" className={linkClass(false)}>
        Movies
      </Link>
      <Link href="/search?view=tv" className={linkClass(onSearch)}>
        TV
      </Link>
      <Link href="/profile#my-list" className={linkClass(onProfile)}>
        My List
      </Link>
      <span className="cinema-nav-divider" aria-hidden />
      <Link
        href="/search"
        className={`hub-nav-item hub-nav-search${onSearch ? " is-active" : ""}`}
        aria-label="Search"
        aria-current={onSearch ? "page" : undefined}
      >
        ⌕
      </Link>
      <Link
        href="/profile"
        className={`hub-nav-item hub-nav-gear${onProfile ? " is-active" : ""}`}
        aria-label="Profile and settings"
        aria-current={onProfile ? "page" : undefined}
      >
        ⚙
      </Link>
    </nav>
  );
}
