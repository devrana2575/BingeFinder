import { useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { useRegion } from '../context/RegionContext';
import { t } from '../i18n';
import PosterImage from '../components/PosterImage';
import RatingBadge from '../components/RatingBadge';
import GenreTags from '../components/GenreTags';
import ProviderSection from '../components/ProviderSection';
import { SkeletonCard } from '../components/Skeletons';
import ErrorState from '../components/ErrorState';

function runtimeLabel(minutes) {
  if (!minutes || minutes <= 0) return null;
  return `${minutes} min`;
}

export default function SurprisePage() {
  const { region } = useRegion();
  const [series, setSeries] = useState(null);
  const [providers, setProviders] = useState(null);
  const [providersStatus, setProvidersStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    setSeries(null);
    setProviders(null);
    setProvidersStatus(null);
    api.surprise()
      .then(d => {
        setSeries(d);
        return d.series_id;
      })
      .then(id => api.watchProviders(id, region).catch(() => null))
      .then(p => {
        if (p) {
          setProviders(p.providers);
          setProvidersStatus(p.status);
        } else {
          setProvidersStatus('error');
        }
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [region]);

  const year = series && series.premiered ? series.premiered.slice(0, 4) : null;
  const runtime = series ? runtimeLabel(series.runtime || series.average_runtime) : null;
  const why = (series && Array.isArray(series.why)) ? series.why : [];

  return (
    <div>
      <div className="text-center mb-8">
        <h1 className="text-xl font-bold text-text mb-1">{t('surprise.title')}</h1>
        <p className="text-sm text-text-muted">{t('surprise.subtitle')}</p>
      </div>

      {!series && !loading && (
        <div className="text-center py-12">
          <button onClick={load} className="btn-primary">
            {t('surprise.pick')}
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
        <div className="max-w-md mx-auto">
          <div className="bg-surface border border-border rounded-xl overflow-hidden mb-4">
            <Link to={`/series/${series.series_id}`} className="block aspect-[2/3] bg-surface-2">
              <PosterImage src={series.image} title={series.name} />
            </Link>
            <div className="p-4">
              <Link to={`/series/${series.series_id}`}>
                <h3 className="font-semibold text-base text-text mb-1 hover:text-accent transition-colors">
                  {series.name}{year ? ` (${year})` : ''}
                </h3>
              </Link>
              <div className="flex items-center gap-2 mb-2 flex-wrap">
                <RatingBadge rating={series.rating} />
                {runtime && <span className="text-xs text-text-muted">{runtime}</span>}
              </div>
              <GenreTags genres={series.genres} />
              {series.summary && (
                <p className="text-sm text-text-muted mt-3 line-clamp-4">{series.summary}</p>
              )}
            </div>
          </div>

          {why.length > 0 && (
            <div className="rounded-xl border border-border bg-surface p-4 mb-4">
              <h2 className="text-sm font-semibold text-text mb-2">{t('surprise.whyTitle')}</h2>
              <ul className="space-y-1">
                {why.map((reason, i) => (
                  <li key={i} className="text-sm text-text-secondary flex gap-2">
                    <span className="text-accent">•</span>
                    {reason}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <ProviderSection
            providers={providers}
            justwatchUrl={null}
            watchNowUrl={null}
            region={region}
            seriesId={series.series_id}
            status={providersStatus}
          />

          <div className="flex gap-3 justify-center">
            <button onClick={load} className="btn-ghost">
              {t('surprise.tryAnother')}
            </button>
            <Link to={`/series/${series.series_id}`} className="btn-primary">
              {t('card.viewDetails')}
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}