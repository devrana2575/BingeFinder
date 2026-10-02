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
        return api.watchProviders(d.series_id, region).catch(() => null);
      })
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

  const year = series?.premiered ? series.premiered.slice(0, 4) : null;
  const runtime = series?.runtime || series?.average_runtime || null;
  const why = Array.isArray(series?.why) ? series.why : [];
  const typeLabel = series?.content_type === 'anime' ? t('card.typeAnime') : t('card.typeSeries');

  return (
    <div>
      <div className="text-center mb-8">
        <p className="text-[11px] font-bold uppercase tracking-[0.22em] text-accent-light mb-2">✦</p>
        <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-text mb-1">{t('surprise.title')}</h1>
        <p className="text-sm text-text-muted">{t('surprise.subtitle')}</p>
      </div>

      {!series && !loading && !error && (
        <div className="text-center py-10">
          <button onClick={load} className="btn-primary px-6 py-3">
            <span aria-hidden className="mr-1.5">✦</span>{t('surprise.pick')}
          </button>
        </div>
      )}

      {loading && (
        <div className="max-w-sm mx-auto">
          <SkeletonCard />
        </div>
      )}

      {error && <ErrorState message={error} onRetry={load} />}

      {series && !loading && (
        <div className="max-w-md mx-auto">
          <div className="rounded-2xl overflow-hidden bg-surface ring-1 ring-border mb-4">
            <Link to={`/series/${series.series_id}`} className="block aspect-[2/3] bg-surface-2">
              <PosterImage src={series.image} title={series.name} />
            </Link>
            <div className="p-5">
              <Link to={`/series/${series.series_id}`}>
                <h2 className="text-lg font-bold text-text leading-snug mb-1 hover:text-accent transition-colors">
                  {series.name}
                </h2>
              </Link>
              <p className="text-xs text-text-muted mb-2">{typeLabel}{year ? ` · ${year}` : ''}</p>
              <div className="flex items-center gap-2 mb-2 flex-wrap">
                <RatingBadge rating={series.rating} />
                {runtime > 0 && <span className="text-xs text-text-muted">{runtime} min</span>}
              </div>
              <GenreTags genres={series.genres} />
              {series.summary && (
                <p className="text-sm text-text-secondary mt-3 line-clamp-4">{series.summary}</p>
              )}
            </div>
          </div>

          {why.length > 0 && (
            <div className="rounded-2xl bg-surface ring-1 ring-border p-5 mb-4">
              <h3 className="text-xs font-bold uppercase tracking-[0.14em] text-accent-light mb-3">
                {t('surprise.whyTitle')}
              </h3>
              <ul className="space-y-1.5">
                {why.map((reason, i) => (
                  <li key={i} className="text-sm text-text-secondary flex gap-2">
                    <span className="text-accent flex-shrink-0" aria-hidden>✓</span>
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

          <div className="flex gap-3 justify-center mt-4">
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