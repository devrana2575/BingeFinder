import { useState, useEffect, useCallback } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import SeriesGrid from '../components/SeriesGrid';
import EmptyState from '../components/EmptyState';
import { SkeletonGrid } from '../components/Skeletons';
import ErrorState from '../components/ErrorState';

export default function LikedPage() {
  const { isAuth } = useAuth();
  const [series, setSeries] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    api.likes()
      .then(d => setSeries(d))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);

  if (!isAuth) return <Navigate to="/login" replace />;

  return (
    <div>
      <h1 className="text-xl font-bold text-text mb-6">Liked</h1>
      {loading ? <SkeletonGrid /> : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : (!series || series.length === 0) ? (
        <EmptyState
          title="No favorites yet"
          message="Like series to keep track of what you enjoy."
          action={<Link to="/discover" className="btn-primary">Discover Series</Link>}
        />
      ) : (
        <SeriesGrid series={series} />
      )}
    </div>
  );
}
