import { useState, useEffect, useCallback, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useRegion } from '../context/RegionContext';
import { t } from '../i18n';
import Hero from '../components/Hero';
import PosterRail from '../components/PosterRail';
import SearchSuggest from '../components/SearchSuggest';
import { SkeletonGrid } from '../components/Skeletons';
import ErrorState from '../components/ErrorState';
import EmptyState from '../components/EmptyState';

function HeroActions() {
  const navigate = useNavigate();

  return (
    <div className="flex flex-col sm:flex-row gap-3 sm:items-center">
      <div className="flex-1 min-w-0 max-w-xl">
        <label htmlFor="hero-search" className="sr-only">{t('hero.searchLabel')}</label>
        <SearchSuggest
          onSearch={q => navigate(`/discover?q=${encodeURIComponent(q.trim())}`)}
          placeholder={t('hero.searchPlaceholder')}
          containerClassName="w-full"
          inputClassName="w-full px-4 py-3 rounded-full bg-bg/70 backdrop-blur border border-border text-text text-sm placeholder:text-text-muted focus:border-accent focus:outline-none"
        />
      </div>
      <Link
        to="/surprise"
        className="btn-primary flex-shrink-0 px-5 py-3 text-sm whitespace-nowrap"
      >
        <span aria-hidden className="mr-1.5">✦</span>{t('hero.surpriseCta')}
      </Link>
    </div>
  );
}

function VibeChips() {
  const [moods, setMoods] = useState([]);

  useEffect(() => {
    api.vibes()
      .then(data => setMoods(Object.entries(data).map(([key, val]) => ({ key, label: val.label }))))
      .catch(() => {});
  }, []);

  if (!moods.length) return null;

  return (
    <div className="flex gap-2 overflow-x-auto pb-1 -mx-1 px-1 mt-5">
      {moods.map(m => (
        <Link
          key={m.key}
          to={`/discover/vibes/${m.key}`}
          className="flex-shrink-0 px-3.5 py-1.5 rounded-full bg-white/5 hover:bg-accent/20 ring-1 ring-border text-xs font-medium text-text-secondary hover:text-accent-light transition-colors whitespace-nowrap"
        >
          {m.label}
        </Link>
      ))}
    </div>
  );
}

export default function HomePage() {
  const { isAuth } = useAuth();
  const { region } = useRegion();
  const [trending, setTrending] = useState(null);
  const [gems, setGems] = useState(null);
  const [recs, setRecs] = useState(null);
  const [freeTonight, setFreeTonight] = useState(null);
  const [featured, setFeatured] = useState(null);
  const [newNoteworthy, setNewNoteworthy] = useState(null);
  const [becauseWatched, setBecauseWatched] = useState(null);
  const [watchedName, setWatchedName] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setError(null);
    setTrending(null);
    setGems(null);
    setRecs(null);
    setFreeTonight(null);
    setFeatured(null);
    setNewNoteworthy(null);
    setBecauseWatched(null);
    setWatchedName(null);

    api.trending()
      .then(setTrending)
      .catch(e => { console.error(e); setTrending([]); });
    // /discover/featured returns landscape backdrops — used for the hero art.
    api.featured(undefined, 4)
      .then(setFeatured)
      .catch(e => { console.error(e); setFeatured([]); });
    api.hiddenGems()
      .then(setGems)
      .catch(e => { console.error(e); setGems([]); });
    api.freeTonight(region)
      .then(setFreeTonight)
      .catch(e => { console.error(e); setFreeTonight([]); });
    api.newNoteworthy()
      .then(setNewNoteworthy)
      .catch(e => { console.error(e); setNewNoteworthy([]); });

    if (isAuth) {
      api.personalizedRecs(region)
        .then(setRecs)
        .catch(e => { console.error(e); setRecs([]); });
      api.recentlyViewed()
        .then(d => {
          const last = d?.[0];
          if (!last) return;
          setWatchedName(last.name);
          return api.seriesRecs(last.series_id)
            .then(res => setBecauseWatched(Array.isArray(res) ? res : res?.recommendations || []))
            .catch(() => setBecauseWatched([]));
        })
        .catch(e => { console.error(e); });
    }
  }, [isAuth, region]);

  useEffect(load, [load]);

  const guestPicks = useMemo(() => {
    if (isAuth || !trending?.length) return null;
    let prefs = {};
    try { prefs = JSON.parse(localStorage.getItem('bf_guest_prefs') || '{}'); } catch {}
    const likedTypes = new Set(prefs.liked_types || []);
    const genres = new Set((prefs.genres || []).map(g => String(g).toLowerCase()));

    const pool = trending.filter(s => {
      if (likedTypes.size > 0 && !likedTypes.has(s.content_type)) return false;
      if (genres.size > 0 && !(s.genres || []).some(g => genres.has(String(g).toLowerCase()))) return false;
      return true;
    });
    if (pool.length === 0) return null;
    return [...pool].sort((a, b) => (b.rating || 0) - (a.rating || 0)).slice(0, 12);
  }, [isAuth, trending]);

  const nothingLoaded = trending === null && gems === null && freeTonight === null &&
    newNoteworthy === null && featured === null;

  if (nothingLoaded) {
    return (
      <>
        <div className="rounded-2xl bg-surface p-8 sm:p-12 mb-9">
          <div className="h-10 w-72 skeleton mb-3" />
          <div className="h-4 w-96 skeleton mb-6" />
          <div className="h-12 w-full max-w-xl skeleton rounded-full" />
        </div>
        <SkeletonGrid count={5} />
      </>
    );
  }

  if (error) return <ErrorState message={error} onRetry={load} />;

  const count = (featured?.length || 0) + (trending?.length || 0);
  const hasRecs = isAuth && recs?.length > 0;

  return (
    <div>
      <Hero
        backdrops={(featured || []).map(f => f.image)}
        brand={t('hero.brand')}
        title={t('hero.title')}
        tagline={t('hero.tagline')}
        subtitle={t('hero.subtitle')}
        count={count > 0 ? count : null}
      >
        <HeroActions />
        <VibeChips />
      </Hero>

      {(hasRecs || guestPicks) && (
        <PosterRail
          title={t('home.personalizedPicks')}
          subtitle={isAuth ? t('home.recommendedForYouSub') : t('home.personalizedPicksSub')}
          series={hasRecs ? recs : guestPicks}
          linkTo="/for-you"
          showMatch
        />
      )}

      {trending?.length > 0 && (
        <PosterRail
          title={t('home.trending')}
          subtitle={t('home.trendingSub')}
          series={trending}
          linkTo="/discover"
        />
      )}

      {becauseWatched?.length > 0 && (
        <PosterRail
          title={`${t('home.becauseYouWatched', { name: watchedName })}`}
          series={becauseWatched.slice(0, 12)}
          showMatch
        />
      )}

      {gems?.length > 0 && (
        <PosterRail
          title={t('home.hiddenGems')}
          subtitle={t('home.hiddenGemsSub')}
          series={gems}
          linkTo="/discover"
          linkText={t('section.discoverMore')}
        />
      )}

      {newNoteworthy?.length > 0 && (
        <PosterRail
          title={t('home.newNoteworthy')}
          subtitle={t('home.newNoteworthySub')}
          series={newNoteworthy}
        />
      )}

      {freeTonight?.length > 0 && (
        <PosterRail
          title={t('home.freeTonight')}
          subtitle={t('home.freeTonightSub')}
          series={freeTonight}
          linkTo="/discover"
          showFreeHint
        />
      )}

      {isAuth && !hasRecs && (
        <EmptyState
          title={t('home.personalizedComing')}
          message={t('home.personalizedComingMsg')}
          action={<Link to="/discover" className="btn-primary">{t('cta.startBrowsing')}</Link>}
        />
      )}
    </div>
  );
}