import { useState, useEffect, useCallback } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import SeriesGrid from '../components/SeriesGrid';
import ConfirmDialog from '../components/ConfirmDialog';
import EmptyState from '../components/EmptyState';
import { SkeletonGrid } from '../components/Skeletons';
import ErrorState from '../components/ErrorState';
import { t } from '../i18n';

export default function WatchlistPage() {
  const { isAuth } = useAuth();
  const toast = useToast();
  const [series, setSeries] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [pendingRemove, setPendingRemove] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    api.watchlist()
      .then(d => setSeries(d))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);

  const confirmRemove = async () => {
    if (!pendingRemove) return;
    const target = pendingRemove;
    setPendingRemove(null);
    try {
      await api.removeWatchlist(target.series_id);
      api.recordEvent({ series_id: target.series_id, event_type: 'watchlist_remove' }).catch(() => {});
      setSeries(prev => (prev || []).filter(s => s.series_id !== target.series_id));
      toast.info(t('action.removedFromWatchlist'));
    } catch {
      toast.error(t('action.genericError'));
    }
  };

  if (!isAuth) return <Navigate to="/login" replace />;

  return (
    <div>
      <h1 className="text-xl font-bold text-text mb-6">{t('watchlist.title')}</h1>
      {loading ? <SkeletonGrid /> : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : (!series || series.length === 0) ? (
        <EmptyState
          title={t('watchlist.emptyTitle')}
          message={t('watchlist.emptyMsg')}
          action={<Link to="/discover" className="btn-primary">{t('cta.discoverSeries')}</Link>}
        />
      ) : (
        <SeriesGrid
          series={series}
          onRemove={item => setPendingRemove(item)}
          removeLabel={t('action.remove')}
        />
      )}

      <ConfirmDialog
        open={Boolean(pendingRemove)}
        title={t('confirm.removeTitle')}
        message={t('confirm.removeWatchlistMsg')}
        confirmLabel={t('action.remove')}
        cancelLabel={t('action.cancel')}
        onConfirm={confirmRemove}
        onClose={() => setPendingRemove(null)}
      />
    </div>
  );
}