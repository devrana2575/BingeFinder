import { useState, useCallback } from 'react';
import { api } from '../api/client';
import PosterImage from '../components/PosterImage';
import RatingBadge from '../components/RatingBadge';
import GenreTags from '../components/GenreTags';
import { SkeletonCard } from '../components/Skeletons';
import ErrorState from '../components/ErrorState';
import { Link } from 'react-router-dom';

export default function SurprisePage() {
  const [series, setSeries] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    api.surprise()
      .then(d => setSeries(d))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="text-center mb-8">
        <h1 className="text-xl font-bold text-text mb-1">Surprise Me</h1>
        <p className="text-sm text-text-muted">We'll pick something great for you</p>
      </div>

      {!series && !loading && (
        <div className="text-center py-12">
          <button onClick={load} className="btn-primary">
            Pick a Series
          </button>
        </div>
      )}

      {loading && (
        <div className="max-w-xs mx-auto">
          <SkeletonCard />
        </div>
      )}

      {error && <ErrorState message={error} onRetry={load} />}

      {series && !loading && (
        <div className="max-w-xs mx-auto">
          <div className="bg-surface border border-border rounded-xl overflow-hidden mb-4">
            <Link to={`/series/${series.series_id}`} className="block aspect-[2/3] bg-surface-2">
              <PosterImage src={series.image} title={series.name} />
            </Link>
            <div className="p-3">
              <Link to={`/series/${series.series_id}`}>
                <h3 className="font-semibold text-sm text-text mb-1 hover:text-accent transition-colors">
                  {series.name}{series.premiered ? ` (${series.premiered.slice(0, 4)})` : ''}
                </h3>
              </Link>
              <div className="flex items-center gap-2 mb-2">
                <RatingBadge rating={series.rating} />
              </div>
              <GenreTags genres={series.genres} />
            </div>
          </div>
          <div className="flex gap-3 justify-center">
            <button onClick={load} className="btn-ghost">
              Roll Again
            </button>
            <Link to={`/series/${series.series_id}`} className="btn-primary">
              View Details
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
