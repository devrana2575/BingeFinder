import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useRegion } from '../context/RegionContext';
import { useToast } from '../context/ToastContext';
import { t } from '../i18n';
import PosterImage from '../components/PosterImage';
import RatingBadge from '../components/RatingBadge';
import GenreTags from '../components/GenreTags';
import SeriesGrid from '../components/SeriesGrid';
import ProviderSection from '../components/ProviderSection';
import { SkeletonText } from '../components/Skeletons';
import ErrorState from '../components/ErrorState';

export default function SeriesDetailPage() {
  const { id } = useParams();
  const { isAuth } = useAuth();
  const { region } = useRegion();
  const toast = useToast();
  const navigate = useNavigate();

  const [series, setSeries] = useState(null);
  const [recs, setRecs] = useState(null);
  const [providers, setProviders] = useState(null);
  const [inWatchlist, setInWatchlist] = useState(false);
  const [isLiked, setIsLiked] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    setSeries(null);
    setRecs(null);
    setProviders(null);

    const tasks = [
      api.getSeries(id),
      api.seriesRecs(id).catch(() => null),
      api.watchProviders(id, region).catch(() => null),
    ];

    Promise.all(tasks)
      .then(([s, r, p]) => {
        setSeries(s);
        setRecs(r);
        setProviders(p);
        if (s?.series_id) {
          api.recordView(s.series_id).catch(() => {});
          api.recordEvent({ series_id: s.series_id, event_type: 'view_details' }).catch(() => {});
        }
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [id, region]);

  useEffect(load, [load]);

  useEffect(() => {
    if (!isAuth || !series?.series_id) return;
    api.watchlist().then(items => {
      setInWatchlist(items.some(i => i.series_id === series.series_id));
    }).catch(() => {});
    api.likes().then(items => {
      setIsLiked(items.some(i => i.series_id === series.series_id));
    }).catch(() => {});
  }, [isAuth, series?.series_id]);

  const toggleWatchlist = async () => {
    if (!isAuth) {
      toast.info(t('action.loginRequired'));
      return navigate('/login');
    }
    const prev = inWatchlist;
    setInWatchlist(!prev);
    try {
      if (prev) {
        await api.removeWatchlist(series.series_id);
        api.recordEvent({ series_id: series.series_id, event_type: 'watchlist_remove' }).catch(() => {});
        toast.info(t('action.removedFromWatchlist'));
      } else {
        await api.addWatchlist(series.series_id);
        api.recordEvent({ series_id: series.series_id, event_type: 'watchlist_add' }).catch(() => {});
        toast.success(t('action.addedToWatchlist'));
      }
    } catch {
      setInWatchlist(prev);
      toast.error(t('action.genericError'));
    }
  };

  const toggleLike = async () => {
    if (!isAuth) {
      toast.info(t('action.loginRequired'));
      return navigate('/login');
    }
    const prev = isLiked;
    setIsLiked(!prev);
    try {
      if (prev) {
        await api.unlike(series.series_id);
        api.recordEvent({ series_id: series.series_id, event_type: 'unlike' }).catch(() => {});
        toast.info(t('action.unliked'));
      } else {
        await api.like(series.series_id);
        api.recordEvent({ series_id: series.series_id, event_type: 'like' }).catch(() => {});
        toast.success(t('action.liked'));
      }
    } catch {
      setIsLiked(prev);
      toast.error(t('action.genericError'));
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col sm:flex-row gap-6">
        <div className="w-48 sm:w-56 flex-shrink-0">
          <div className="aspect-[2/3] skeleton rounded-xl" />
        </div>
        <div className="flex-1 space-y-4">
          <div className="h-8 w-3/4 skeleton" />
          <div className="h-4 w-1/2 skeleton" />
          <SkeletonText lines={4} />
        </div>
      </div>
    );
  }

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!series) return <ErrorState message={t('detail.seriesNotFound')} />;

  return (
    <div>
      <div className="flex flex-col sm:flex-row gap-6 mb-8">
        <div className="w-48 sm:w-56 flex-shrink-0">
          <div className="aspect-[2/3] rounded-xl overflow-hidden border border-border">
            <PosterImage src={series.image} title={series.name} />
          </div>
        </div>

        <div className="flex-1 min-w-0">
          <h1 className="text-2xl sm:text-3xl font-bold text-text mb-2">{series.name}</h1>

          <div className="flex items-center gap-2 flex-wrap mb-3">
            <RatingBadge rating={series.rating} />
            {series.premiered && <span className="text-sm text-text-muted">{series.premiered.slice(0, 4)}</span>}
            {series.language && <span className="text-sm text-text-muted">{series.language}</span>}
            {series.status && (
              <span className="text-xs px-2 py-0.5 rounded bg-surface-2 text-text-muted">{series.status}</span>
            )}
            {series.network && (
              <span className="text-xs text-text-muted">{series.network}</span>
            )}
          </div>

          <div className="mb-3">
            <GenreTags genres={series.genres} limit={10} />
          </div>

          {series.summary && (
            <div
              className="text-sm text-text-secondary leading-relaxed mb-4 max-w-2xl"
              dangerouslySetInnerHTML={{ __html: series.summary }}
            />
          )}

          <div className="flex gap-2">
            <button
              onClick={toggleWatchlist}
              className={`btn-ghost ${inWatchlist ? '!border-accent !text-accent !bg-accent/10' : ''}`}
              aria-pressed={inWatchlist}
            >
              {inWatchlist ? t('detail.inWatchlist') : t('detail.addWatchlist')}
            </button>
            <button
              onClick={toggleLike}
              className={`btn-ghost ${isLiked ? '!border-success !text-success !bg-success/10' : ''}`}
              aria-pressed={isLiked}
            >
              {isLiked ? t('detail.liked') : t('detail.like')}
            </button>
          </div>
        </div>
      </div>

      {recs?.why_recommended?.length > 0 && (
        <section className="mb-8 rounded-xl border border-border bg-surface p-5">
          <h2 className="text-base font-semibold text-text mb-2">{t('detail.whyRecommendedTitle')}</h2>
          <ul className="space-y-1">
            {recs.why_recommended.map((reason, i) => (
              <li key={i} className="text-sm text-text-secondary flex items-start gap-2">
                <span className="text-accent mt-0.5">&#8226;</span>
                {reason}
              </li>
            ))}
          </ul>
        </section>
      )}

      <ProviderSection providers={providers?.providers} justwatchUrl={providers?.justwatch_url} watchNowUrl={providers?.watch_now_url} region={providers?.region} seriesId={series?.series_id} status={providers?.status} />

      {recs?.recommendations?.length > 0 && (
        <section className="mb-8">
          <h2 className="text-base font-semibold text-text mb-3">{t('detail.alsoLike')}</h2>
          <SeriesGrid
            series={recs.recommendations}
            relevanceScores={Object.fromEntries(recs.recommendations.map(r => [r.series_id, r.relevance_score]))}
          />
        </section>
      )}
    </div>
  );
}