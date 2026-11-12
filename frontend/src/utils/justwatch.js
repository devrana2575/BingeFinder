/**
 * Build a region-scoped JustWatch search URL for a title.
 *
 * This is the frontend fallback used so every title always has a real "find
 * it free" link, even if the watch-provider request fails or is still loading.
 * It points at JustWatch's search results, which always resolves to a page.
 */
export function getJustwatchSearchUrl(title, region) {
  const name = (title || '').trim();
  if (!name) return null;
  const country = (region || 'US').toLowerCase();
  return `https://www.justwatch.com/${country}/search?q=${encodeURIComponent(name)}`;
}
