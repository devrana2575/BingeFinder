import { useState, useEffect, useCallback } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import SeriesGrid from '../components/SeriesGrid';
import EmptyState from '../components/EmptyState';
import { SkeletonGrid } from '../components/Skeletons';
import ErrorState from '../components/ErrorState';

export default function ForYouPage() {
  const { isAuth } = useAuth();
  const [series, setSeries] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    api.personalizedRecs()
      .then(d => setSeries(d))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);

  if (!isAuth) return <Navigate to="/login" replace />;

  return (
    <div>
      <h1 className="text-xl font-bold text-text mb-1">For You</h1>
      <p className="text-sm text-text-muted mb-6">Personalized recommendations based on your taste</p>
      {loading ? <SkeletonGrid /> : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : (!series || series.length === 0) ? (
        <EmptyState
          title="No recommendations yet"
          message="Keep exploring and we'll learn what you like."
          action={<Link to="/" className="btn-primary">Start Browsing</Link>}
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
