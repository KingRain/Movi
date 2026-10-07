"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

type Props = {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
};

export function MovieRow({ eyebrow, title, subtitle, action, children }: Props) {
  const trackRef = useRef<HTMLDivElement | null>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const syncArrows = useCallback(() => {
    const el = trackRef.current;
    if (!el) return;
    const maxScroll = el.scrollWidth - el.clientWidth;
    setCanScrollLeft(el.scrollLeft > 4);
    setCanScrollRight(maxScroll > 4 && el.scrollLeft < maxScroll - 4);
  }, []);

  useEffect(() => {
    syncArrows();
    const el = trackRef.current;
    if (!el) return undefined;
    el.addEventListener("scroll", syncArrows, { passive: true });
    const observer = new ResizeObserver(syncArrows);
    observer.observe(el);
    return () => {
      el.removeEventListener("scroll", syncArrows);
      observer.disconnect();
    };
  }, [children, syncArrows]);

  const scroll = (direction: -1 | 1) => {
    const el = trackRef.current;
    if (!el) return;
    const step = Math.max(280, Math.round(el.clientWidth * 0.72));
    el.scrollBy({ left: direction * step, behavior: "smooth" });
  };

  return (
    <section className="swimlane">
      <div className="swimlane-head">
        <div>
          {eyebrow ? <p className="swimlane-eyebrow">{eyebrow}</p> : null}
          <h2 className="swimlane-title">{title}</h2>
          {subtitle ? <p className="swimlane-sub">{subtitle}</p> : null}
        </div>
        {action}
      </div>
      <div className="swimlane-row-wrap">
        <button
          type="button"
          className="swimlane-arrow swimlane-arrow-left"
          aria-label="Scroll row left"
          disabled={!canScrollLeft}
          onClick={() => scroll(-1)}
        >
          ‹
        </button>
        <div className="swimlane-track" ref={trackRef}>
          {children}
        </div>
        <button
          type="button"
          className="swimlane-arrow swimlane-arrow-right"
          aria-label="Scroll row right"
          disabled={!canScrollRight}
          onClick={() => scroll(1)}
        >
          ›
        </button>
      </div>
    </section>
  );
}
