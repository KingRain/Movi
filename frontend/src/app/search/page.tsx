import { Suspense } from "react";
import { MoviSearchPage } from "@/components/movi-search-page";

export default function SearchPage() {
  return (
    <Suspense fallback={<div className="cinema-shell cinema-page min-h-screen bg-black" />}>
      <MoviSearchPage />
    </Suspense>
  );
}
