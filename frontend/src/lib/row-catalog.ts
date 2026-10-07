export type RowMovie = { tmdb_id: number };

/** Pick movies for a row, skipping anything already used in prior rows. */
export function pickUniqueRowMovies<T extends RowMovie>(
  list: T[],
  usedIds: Set<number>,
): T[] {
  const out: T[] = [];
  for (const movie of list) {
    if (usedIds.has(movie.tmdb_id)) continue;
    usedIds.add(movie.tmdb_id);
    out.push(movie);
  }
  return out;
}

export function buildCatalogRows<T extends RowMovie>(
  recommendations: T[],
  recent: T[],
  topRated: T[],
  genreSections: { genre_id: number; name: string; movies: T[] }[],
) {
  const used = new Set<number>(recommendations.map((m) => m.tmdb_id));

  const recentRow = pickUniqueRowMovies(recent, used);
  const topRatedRow = pickUniqueRowMovies(topRated, used);
  const genreRows = genreSections.map((section) => ({
    ...section,
    movies: pickUniqueRowMovies(section.movies, used),
  }));

  return { recentRow, topRatedRow, genreRows };
}
