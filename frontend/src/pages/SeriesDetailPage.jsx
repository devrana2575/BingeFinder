import { useState, useEffect, useCallback } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import PosterImage from '../components/PosterImage';
import RatingBadge from '../components/RatingBadge';
import GenreTags from '../components/GenreTags';
import SeriesGrid from '../components/SeriesGrid';
import { SkeletonText } from '../components/Skeletons';
import ErrorState from '../components/ErrorState';

function ProviderSection({ providers, justwatchUrl, watchNowUrl, region, seriesId, tmdbConfigured }) {
  const [showPaid, setShowPaid] = useState(false);

  const regionLabel = (region || 'IN').toUpperCase();

  if (tmdbConfigured === false) {
    return (
      <section className="rounded-xl border border-border bg-surface p-5 mb-8">
        <h2 className="text-base font-semibold text-text mb-3">Where to Watch</h2>
        <p className="text-sm text-text-muted">
          Watch availability is currently unavailable. Configure a TMDB API key to see streaming providers.
        </p>
        {justwatchUrl && (
          <a href={justwatchUrl} target="_blank" rel="noopener noreferrer"
             className="inline-block mt-2 text-xs text-accent hover:underline">
            Check availability on JustWatch
          </a>
        )}
      </section>
    );
  }

  if (!providers) {
    return (
      <section className="rounded-xl border border-border bg-surface p-5 mb-8">
        <h2 className="text-base font-semibold text-text mb-3">Where to Watch</h2>
        <p className="text-sm text-text-muted">Loading watch availability...</p>
      </section>
    );
  }

  const free = providers.free || [];
  const ads = providers.ads || [];
  const flatrate = providers.flatrate || [];
  const rent = providers.rent || [];
  const buy = providers.buy || [];
  const freeAll = [...free, ...ads];
  const hasPaid = flatrate.length > 0 || rent.length > 0 || buy.length > 0;
  const watchNowHref = watchNowUrl || justwatchUrl;
  const watchNowLabel = watchNowUrl ? 'WATCH NOW →' : 'VIEW AVAILABILITY →';

  const ProviderCard = ({ provider, tier }) => (
    <div className="flex items-center gap-3 p-3 rounded-lg bg-surface-2 border border-border">
      {provider.logo_path ? (
        <img
          src={`https://image.tmdb.org/t/p/w45${provider.logo_path}`}
          alt={provider.provider_name}
          className="w-8 h-8 rounded"
        />
      ) : (
        <div className="w-8 h-8 rounded bg-surface-3 flex items-center justify-center text-xs text-text-muted">
          {provider.provider_name?.charAt(0)}
        </div>
      )}
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-text truncate">{provider.provider_name}</div>
        <div className="text-xs text-text-muted">{tier}</div>
      </div>
      {watchNowHref && (
        <a
          href={watchNowHref}
          target="_blank"
          rel="noopener noreferrer"
          onClick={() => {
            if (seriesId) api.recordEvent({ series_id: seriesId, event_type: 'provider_click' }).catch(() => {});
          }}
          className="flex-shrink-0 text-xs font-semibold text-accent hover:underline whitespace-nowrap"
        >
          {watchNowLabel}
        </a>
      )}
    </div>
  );

  return (
    <section className="rounded-xl border border-border bg-surface p-5 mb-8">
      <div className="flex items-baseline justify-between mb-4">
        <h2 className="text-base font-semibold text-text">Where to Watch</h2>
        <span className="text-xs text-text-muted">{regionLabel}</span>
      </div>

      {freeAll.length > 0 ? (
        <div className="mb-4">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-xs font-bold text-free uppercase tracking-wider">Free to Watch</span>
          </div>
          <div className="space-y-2">
            {freeAll.map(p => (
              <ProviderCard
                key={p.provider_name}
                provider={p}
                tier={free.some(f => f.provider_name === p.provider_name) ? 'Free' : 'Free with Ads'}
              />
            ))}
          </div>
        </div>
      ) : (
        <p className="text-sm text-text-muted mb-4">
          No verified free streaming option currently available in India.
        </p>
      )}

      {hasPaid && (
        <div>
          <button
            onClick={() => setShowPaid(!showPaid)}
            className="text-xs text-text-secondary hover:text-accent transition-colors mb-2 flex items-center gap-1"
          >
            Other ways to watch (subscription, rent or buy)
            <span className={`text-[10px] transition-transform ${showPaid ? 'rotate-90' : ''}`}>&#9654;</span>
          </button>
          {showPaid && (
            <div className="space-y-2 mt-2">
              {flatrate.map(p => (
                <ProviderCard key={`sub-${p.provider_name}`} provider={p} tier="Subscription" />
              ))}
              {rent.map(p => (
                <ProviderCard key={`rent-${p.provider_name}`} provider={p} tier="Rent" />
              ))}
              {buy.map(p => (
                <ProviderCard key={`buy-${p.provider_name}`} provider={p} tier="Buy" />
              ))}
            </div>
          )}
        </div>
      )}

      {!freeAll.length && !hasPaid && (
        <p className="text-sm text-text-muted">
          No legal watch options found for this region.
        </p>
      )}
    </section>
  );
}

export default function SeriesDetailPage() {
  const { id } = useParams();
  const { isAuth } = useAuth();
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
      api.watchProviders(id).catch(() => null),
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
  }, [id]);

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
    if (!isAuth) return navigate('/login');
    const prev = inWatchlist;
    setInWatchlist(!prev);
    try {
      if (prev) {
        await api.removeWatchlist(series.series_id);
        api.recordEvent({ series_id: series.series_id, event_type: 'watchlist_remove' }).catch(() => {});
      } else {
        await api.addWatchlist(series.series_id);
        api.recordEvent({ series_id: series.series_id, event_type: 'watchlist_add' }).catch(() => {});
      }
    } catch (e) {
      setInWatchlist(prev);
    }
  };

  const toggleLike = async () => {
    if (!isAuth) return navigate('/login');
    const prev = isLiked;
    setIsLiked(!prev);
    try {
      if (prev) {
        await api.unlike(series.series_id);
        api.recordEvent({ series_id: series.series_id, event_type: 'unlike' }).catch(() => {});
      } else {
        await api.like(series.series_id);
        api.recordEvent({ series_id: series.series_id, event_type: 'like' }).catch(() => {});
      }
    } catch (e) {
      setIsLiked(prev);
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
  if (!series) return <ErrorState message="Series not found." />;

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
              {inWatchlist ? 'In Watchlist' : '+ Watchlist'}
            </button>
            <button
              onClick={toggleLike}
              className={`btn-ghost ${isLiked ? '!border-success !text-success !bg-success/10' : ''}`}
              aria-pressed={isLiked}
            >
              {isLiked ? 'Liked' : 'Like'}
            </button>
          </div>
        </div>
      </div>

      {recs?.why_recommended?.length > 0 && (
        <section className="mb-8 rounded-xl border border-border bg-surface p-5">
          <h2 className="text-base font-semibold text-text mb-2">Why you might like it</h2>
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

      <ProviderSection providers={providers?.providers} justwatchUrl={providers?.justwatch_url} watchNowUrl={providers?.watch_now_url} region={providers?.region} seriesId={series?.series_id} tmdbConfigured={providers?.tmdb_configured} />

      {recs?.recommendations?.length > 0 && (
        <section className="mb-8">
          <h2 className="text-base font-semibold text-text mb-3">You might also like</h2>
          <SeriesGrid
            series={recs.recommendations}
            relevanceScores={Object.fromEntries(recs.recommendations.map(r => [r.series_id, r.relevance_score]))}
          />
        </section>
      )}
    </div>
  );
}
