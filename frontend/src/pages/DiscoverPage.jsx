import { useState, useEffect, useCallback, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import SeriesGrid from '../components/SeriesGrid';
import { SkeletonGrid } from '../components/Skeletons';
import ErrorState from '../components/ErrorState';
import EmptyState from '../components/EmptyState';

function useDebounce(value, delay) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

export default function DiscoverPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [series, setSeries] = useState([]);
  const [filterOptions, setFilterOptions] = useState(null);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const q = searchParams.get('q') || '';
  const genre = searchParams.get('genre') || '';
  const year = searchParams.get('year') || '';
  const min_rating = searchParams.get('min_rating') || '';
  const status = searchParams.get('status') || '';

  const [localQuery, setLocalQuery] = useState(q);
  const debouncedQuery = useDebounce(localQuery, 300);

  useEffect(() => {
    if (debouncedQuery !== q) {
      setSearchParams(prev => {
        const next = new URLSearchParams(prev);
        if (debouncedQuery) next.set('q', debouncedQuery);
        else next.delete('q');
        return next;
      });
    }
  }, [debouncedQuery]);

  useEffect(() => {
    setLocalQuery(q);
  }, [q]);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    const params = {};
    if (q) params.q = q;
    if (genre) params.genre = genre;
    if (year) params.year = year;
    if (min_rating) params.min_rating = min_rating;
    if (status) params.status = status;
    api.search(params)
      .then(d => {
        setSeries(d.results || []);
        setTotal(d.total_results || 0);
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [q, genre, year, min_rating, status]);

  useEffect(load, [load]);

  useEffect(() => {
    api.filterOptions().then(d => setFilterOptions(d)).catch(() => {});
  }, []);

  const setFilter = (key, value) => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev);
      if (value) next.set(key, value);
      else next.delete(key);
      return next;
    });
  };

  const activeFilters = [genre, year, min_rating, status].filter(Boolean).length;

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-xl font-bold text-text mb-1">Discover</h1>
        <p className="text-sm text-text-muted">
          {total > 0 ? `Explore ${total.toLocaleString()} web series` : 'Search the catalog'}
        </p>
      </div>

      <div className="mb-6">
        <label htmlFor="discover-search" className="sr-only">Search series</label>
        <input
          id="discover-search"
          type="text"
          value={localQuery}
          onChange={e => setLocalQuery(e.target.value)}
          placeholder="Search by title..."
          className="w-full max-w-md px-4 py-2.5 rounded-lg bg-surface border border-border text-text text-sm placeholder:text-text-muted focus:border-accent"
        />
      </div>

      {filterOptions && (
        <div className="flex flex-wrap gap-2 mb-6">
          <label htmlFor="filter-genre" className="sr-only">Genre</label>
          <select id="filter-genre" value={genre} onChange={e => setFilter('genre', e.target.value)}
            className="px-3 py-1.5 rounded-lg bg-surface border border-border text-sm text-text-secondary focus:border-accent">
            <option value="">All Genres</option>
            {(filterOptions.genres || []).map(g => <option key={g} value={g}>{g}</option>)}
          </select>

          <label htmlFor="filter-year" className="sr-only">Year</label>
          <select id="filter-year" value={year} onChange={e => setFilter('year', e.target.value)}
            className="px-3 py-1.5 rounded-lg bg-surface border border-border text-sm text-text-secondary focus:border-accent">
            <option value="">All Years</option>
            {(filterOptions.years || []).map(y => <option key={y} value={y}>{y}</option>)}
          </select>

          <label htmlFor="filter-rating" className="sr-only">Minimum rating</label>
          <select id="filter-rating" value={min_rating} onChange={e => setFilter('min_rating', e.target.value)}
            className="px-3 py-1.5 rounded-lg bg-surface border border-border text-sm text-text-secondary focus:border-accent">
            <option value="">Any Rating</option>
            <option value="5">5+</option>
            <option value="6">6+</option>
            <option value="7">7+</option>
            <option value="8">8+</option>
            <option value="9">9+</option>
          </select>

          <label htmlFor="filter-status" className="sr-only">Status</label>
          <select id="filter-status" value={status} onChange={e => setFilter('status', e.target.value)}
            className="px-3 py-1.5 rounded-lg bg-surface border border-border text-sm text-text-secondary focus:border-accent">
            <option value="">All Status</option>
            {(filterOptions.statuses || []).map(s => <option key={s} value={s}>{s}</option>)}
          </select>

          {activeFilters > 0 && (
            <button
              onClick={() => setSearchParams(new URLSearchParams())}
              className="px-3 py-1.5 rounded-lg text-xs text-danger hover:bg-danger/10 transition-colors"
            >
              Clear all
            </button>
          )}
        </div>
      )}

      {loading ? (
        <SkeletonGrid />
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : series.length === 0 ? (
        <EmptyState
          title="No results"
          message={q ? `No series found for "${q}". Try a different search.` : 'Try adjusting your filters.'}
        />
      ) : (
        <SeriesGrid series={series} />
      )}
    </div>
  );
}
