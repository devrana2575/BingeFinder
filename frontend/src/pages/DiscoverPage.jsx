import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import SeriesGrid from '../components/SeriesGrid';
import { SkeletonGrid } from '../components/Skeletons';
import ErrorState from '../components/ErrorState';
import EmptyState from '../components/EmptyState';
import { t } from '../i18n';

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
  const type = searchParams.get('type') || '';

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
  }, [debouncedQuery, q, setSearchParams]);

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
    if (type) params.content_type = type;
    api.search(params)
      .then(d => {
        setSeries(d.results || []);
        setTotal(d.total_results || 0);
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [q, genre, year, min_rating, status, type]);

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

  const activeFilters = [genre, year, min_rating, status, type].filter(Boolean).length;

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-xl font-bold text-text mb-1">{t('discover.title')}</h1>
        <p className="text-sm text-text-muted">
          {total > 0 ? t('discover.exploreCount', { count: total.toLocaleString() }) : t('discover.searchCatalog')}
        </p>
      </div>

      <div className="mb-6">
        <label htmlFor="discover-search" className="sr-only">{t('discover.searchLabel')}</label>
        <input
          id="discover-search"
          type="text"
          value={localQuery}
          onChange={e => setLocalQuery(e.target.value)}
          placeholder={t('discover.searchPlaceholder')}
          className="w-full max-w-md px-4 py-2.5 rounded-lg bg-surface border border-border text-text text-sm placeholder:text-text-muted focus:border-accent"
        />
      </div>

      {filterOptions && (
        <div className="flex flex-wrap gap-2 mb-6">
          <label htmlFor="filter-type" className="sr-only">{t('discover.filterTypeLabel')}</label>
          <select id="filter-type" value={type} onChange={e => setFilter('type', e.target.value)}
            className="px-3 py-1.5 rounded-lg bg-surface border border-border text-sm text-text-secondary focus:border-accent">
            <option value="">{t('discover.allTypes')}</option>
            <option value="tv_series">{t('discover.typeSeries')}</option>
            <option value="movie">{t('discover.typeMovies')}</option>
            <option value="anime">{t('discover.typeAnime')}</option>
          </select>

          <label htmlFor="filter-genre" className="sr-only">{t('discover.filterGenreLabel')}</label>
          <select id="filter-genre" value={genre} onChange={e => setFilter('genre', e.target.value)}
            className="px-3 py-1.5 rounded-lg bg-surface border border-border text-sm text-text-secondary focus:border-accent">
            <option value="">{t('discover.allGenres')}</option>
            {(filterOptions.genres || []).map(g => <option key={g} value={g}>{g}</option>)}
          </select>

          <label htmlFor="filter-year" className="sr-only">{t('discover.filterYearLabel')}</label>
          <select id="filter-year" value={year} onChange={e => setFilter('year', e.target.value)}
            className="px-3 py-1.5 rounded-lg bg-surface border border-border text-sm text-text-secondary focus:border-accent">
            <option value="">{t('discover.allYears')}</option>
            {(filterOptions.years || []).map(y => <option key={y} value={y}>{y}</option>)}
          </select>

          <label htmlFor="filter-rating" className="sr-only">{t('discover.filterRatingLabel')}</label>
          <select id="filter-rating" value={min_rating} onChange={e => setFilter('min_rating', e.target.value)}
            className="px-3 py-1.5 rounded-lg bg-surface border border-border text-sm text-text-secondary focus:border-accent">
            <option value="">{t('discover.anyRating')}</option>
            <option value="5">5+</option>
            <option value="6">6+</option>
            <option value="7">7+</option>
            <option value="8">8+</option>
            <option value="9">9+</option>
          </select>

          <label htmlFor="filter-status" className="sr-only">{t('discover.filterStatusLabel')}</label>
          <select id="filter-status" value={status} onChange={e => setFilter('status', e.target.value)}
            className="px-3 py-1.5 rounded-lg bg-surface border border-border text-sm text-text-secondary focus:border-accent">
            <option value="">{t('discover.allStatus')}</option>
            {(filterOptions.statuses || []).map(s => <option key={s} value={s}>{s}</option>)}
          </select>

          {activeFilters > 0 && (
            <button
              onClick={() => setSearchParams(new URLSearchParams())}
              className="px-3 py-1.5 rounded-lg text-xs text-danger hover:bg-danger/10 transition-colors"
            >
              {t('discover.clearAll')}
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
          title={t('discover.noResultsTitle')}
          message={q ? t('discover.noResultsForQuery', { q }) : t('discover.noResultsFilters')}
        />
      ) : (
        <SeriesGrid series={series} />
      )}
    </div>
  );
}
