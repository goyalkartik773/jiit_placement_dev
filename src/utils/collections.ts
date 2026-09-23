/** Array helpers for defensively shaped backend child rows. */

/**
 * Keeps the first occurrence per derived key. The API can return duplicate
 * child rows (same content, different ids) — seen in jobhiringflows and
 * jobgenders — so views dedupe before counting or rendering.
 */
export function uniqueBy<T>(items: readonly T[], keyOf: (item: T) => string): T[] {
  const seen = new Set<string>();
  const result: T[] = [];
  for (const item of items) {
    const key = keyOf(item);
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(item);
  }
  return result;
}
