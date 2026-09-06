import { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../api/client';
import SeriesGrid from '../components/SeriesGrid';
import { SkeletonGrid } from '../components/Skeletons';
import ErrorState from '../components/ErrorState';
import EmptyState from '../components/EmptyState';
import { t } from '../i18n';

export default function VibesFilterPage() {
  const { key } = useParams();
  const [series, setSeries] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    api.vibeFiltered(key)
      .then(d => setSeries(Array.isArray(d) ? d : []))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [key]);

  useEffect(load, [load]);

  return (
    <div>
      <Link to="/" className="text-sm text-accent hover:underline mb-4 inline-block">{t('vibes.backHome')}</Link>
      <h1 className="text-xl font-bold text-text mb-6">{key.replace(/-/g, ' ')}</h1>
      {loading ? <SkeletonGrid /> : error ? <ErrorState message={error} onRetry={load} /> : (
        series.length === 0 ? (
          <EmptyState title={t('vibes.noResultsTitle')} message={t('vibes.noResultsMsg')} />
        ) : (
          <SeriesGrid series={series} />
        )
      )}
    </div>
  );
}
