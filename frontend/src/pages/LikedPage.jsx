import { useState, useEffect, useCallback } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import SeriesGrid from '../components/SeriesGrid';
import EmptyState from '../components/EmptyState';
import { SkeletonGrid } from '../components/Skeletons';
import ErrorState from '../components/ErrorState';
import { t } from '../i18n';

export default function LikedPage() {
  const { isAuth } = useAuth();
  const [series, setSeries] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    api.reactions()
      .then(d => setSeries((d || []).filter(i => i.reaction === 'love' || i.reaction === 'like')))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);

  if (!isAuth) return <Navigate to="/login" replace />;

  return (
    <div>
      <h1 className="text-xl font-bold text-text mb-6">{t('liked.title')}</h1>
      {loading ? <SkeletonGrid /> : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : (!series || series.length === 0) ? (
        <EmptyState
          title={t('liked.emptyTitle')}
          message={t('liked.emptyMsg')}
          action={<Link to="/discover" className="btn-primary">{t('cta.discoverSeries')}</Link>}
        />
      ) : (
        <SeriesGrid series={series} />
      )}
    </div>
  );
}
