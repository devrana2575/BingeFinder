import { useState, useEffect, useCallback } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import SeriesGrid from '../components/SeriesGrid';
import EmptyState from '../components/EmptyState';
import { SkeletonGrid } from '../components/Skeletons';
import ErrorState from '../components/ErrorState';
import { t } from '../i18n';

const TYPE_OPTIONS = [
  { value: '', labelKey: 'discover.allTypes' },
  { value: 'tv_series', labelKey: 'types.series' },
  { value: 'movie', labelKey: 'types.movies' },
  { value: 'anime', labelKey: 'types.anime' },
];

export default function ForYouPage() {
  const { isAuth } = useAuth();
  const [series, setSeries] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [contentType, setContentType] = useState('');

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    api.personalizedRecs(null, contentType)
      .then(d => setSeries(d))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [contentType]);

  useEffect(load, [load]);

  if (!isAuth) return <Navigate to="/login" replace />;

  return (
    <div>
      <h1 className="text-xl font-bold text-text mb-1">{t('forYou.title')}</h1>
      <p className="text-sm text-text-muted mb-6">{t('forYou.subtitle')}</p>

      <div className="flex flex-wrap gap-2 mb-6">
        {TYPE_OPTIONS.map(opt => (
          <button
            key={opt.value}
            type="button"
            onClick={() => setContentType(opt.value)}
            className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
              contentType === opt.value
                ? 'bg-accent text-white border-accent'
                : 'bg-surface border-border text-text-secondary hover:border-accent'
            }`}
          >
            {t(opt.labelKey)}
          </button>
        ))}
      </div>

      {loading ? <SkeletonGrid /> : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : (!series || series.length === 0) ? (
        <EmptyState
          title={t('forYou.emptyRecsTitle')}
          message={t('forYou.emptyMsg')}
          action={<Link to="/" className="btn-primary">{t('cta.startBrowsing')}</Link>}
        />
      ) : (
        <SeriesGrid
          series={series}
          relevanceScores={Object.fromEntries(series.map(r => [r.series_id, r.relevance_score]))}
        />
      )}
    </div>
  );
}
