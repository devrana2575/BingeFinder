import { useState, useEffect, useCallback, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useRegion } from '../context/RegionContext';
import { t } from '../i18n';
import SeriesGrid from '../components/SeriesGrid';
import SearchSuggest from '../components/SearchSuggest';
import { SkeletonGrid } from '../components/Skeletons';
import ErrorState from '../components/ErrorState';
import EmptyState from '../components/EmptyState';

function HeroSection() {
  const navigate = useNavigate();

  return (
    <section className="mb-8">
      <h1 className="text-lg sm:text-xl font-bold text-text mb-1" style={{ fontFamily: 'Sora, sans-serif' }}>
        {t('hero.title')}
      </h1>
      <p className="text-text-muted text-sm mb-3 max-w-lg">
        {t('hero.subtitleNoCount')}
      </p>
      <div className="max-w-lg">
        <label htmlFor="hero-search" className="sr-only">{t('hero.searchLabel')}</label>
        <SearchSuggest
          onSearch={q => navigate(`/discover?q=${encodeURIComponent(q.trim())}`)}
          actionLabel={t('hero.searchButton')}
          placeholder={t('hero.searchPlaceholder')}
          inputClassName="flex-1 px-4 py-2.5 rounded-lg bg-bg border border-border text-text text-sm placeholder:text-text-muted focus:border-accent"
        />
      </div>
      <Link to="/surprise" className="inline-block mt-3 text-sm text-text-secondary hover:text-accent transition-colors">
        {t('hero.surpriseLink')}
      </Link>
    </section>
  );
}

function MoodSlider() {
  const [moods, setMoods] = useState([]);

  useEffect(() => {
    api.vibes()
      .then(data => {
        const items = Object.entries(data).map(([key, val]) => ({
          key, label: val.label,
        }));
        setMoods(items);
      })
      .catch(() => {});
  }, []);

  if (!moods.length) return null;

  return (
    <section className="mb-8">
      <h2 className="text-base font-semibold text-text mb-3">{t('mood.title')}</h2>
      <div className="flex gap-2 overflow-x-auto pb-2 -mx-1 px-1">
        {moods.map(m => (
          <Link
            key={m.key}
            to={`/discover/vibes/${m.key}`}
            className="flex-shrink-0 px-4 py-2 rounded-lg bg-surface border border-border text-sm text-text-secondary hover:border-accent hover:text-accent transition-colors whitespace-nowrap"
          >
            {m.label}
          </Link>
        ))}
      </div>
    </section>
  );
}

function SectionHeader({ title, subtitle, linkTo, linkText }) {
  return (
    <div className="flex items-end justify-between mb-3">
      <div>
        <h2 className="text-base font-semibold text-text">{title}</h2>
        {subtitle && <p className="text-xs text-text-muted mt-0.5">{subtitle}</p>}
      </div>
      {linkTo && (
        <Link to={linkTo} className="text-xs text-accent hover:underline flex-shrink-0">{linkText || t('section.viewAll')}</Link>
      )}
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
  const [topRated, setTopRated] = useState(null);
  const [newNoteworthy, setNewNoteworthy] = useState(null);
  const [continueWatching, setContinueWatching] = useState(null);
  const [becauseWatched, setBecauseWatched] = useState(null);
  const [freePlatform, setFreePlatform] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setError(null);
    setTrending(null);
    setGems(null);
    setRecs(null);
    setFreeTonight(null);
    setTopRated(null);
    setNewNoteworthy(null);
    setContinueWatching(null);
    setBecauseWatched(null);
    setFreePlatform(null);

    api.trending()
      .then(d => setTrending(d))
      .catch(e => { console.error(e); setTrending([]); });
    api.featured(undefined, 8)
      .then(d => setTopRated(d))
      .catch(e => { console.error(e); setTopRated([]); });
    api.hiddenGems()
      .then(d => setGems(d))
      .catch(e => { console.error(e); setGems([]); });
    api.freeTonight(region)
      .then(d => setFreeTonight(d))
      .catch(e => { console.error(e); setFreeTonight([]); });
    api.newNoteworthy()
      .then(d => setNewNoteworthy(d))
      .catch(e => { console.error(e); setNewNoteworthy([]); });
    if (isAuth) {
      api.personalizedRecs(region)
        .then(d => setRecs(d))
        .catch(e => { console.error(e); setRecs([]); });
      api.recentlyViewed()
        .then(d => {
          setContinueWatching(d);
          const last = d?.[0];
          if (last) {
            api.seriesRecs(last.series_id)
              .then(res => {
                const list = Array.isArray(res) ? res : res?.recommendations || [];
                setBecauseWatched(list);
              })
              .catch(() => setBecauseWatched([]));
          } else {
            setBecauseWatched([]);
          }
        })
        .catch(e => { console.error(e); setContinueWatching([]); setBecauseWatched([]); });
    }
  }, [isAuth, region]);

  useEffect(load, [load]);

  const guestPicks = useMemo(() => {
    if (isAuth || !trending?.length) return null;
    let prefs = {};
    try { prefs = JSON.parse(localStorage.getItem('bf_guest_prefs') || '{}'); } catch {}
    const likedTypes = new Set(prefs.liked_types || []);
    const genres = new Set((prefs.genres || []).map(g => String(g).toLowerCase()));
    const languages = new Set((prefs.languages || []).map(l => String(l).toLowerCase()));

    const pool = trending.filter(s => {
      if (likedTypes.size > 0 && !likedTypes.has(s.content_type)) return false;
      if (genres.size > 0 && !(s.genres || []).some(g => genres.has(String(g).toLowerCase()))) return false;
      return true;
    });
    if (pool.length === 0) return null;
    const langScore = s => languages.size > 0 && s.language && languages.has(String(s.language).toLowerCase()) ? 1 : 0;
    return [...pool].sort((a, b) =>
      (langScore(b) - langScore(a)) || ((b.rating || 0) - (a.rating || 0))
    ).slice(0, 10);
  }, [isAuth, trending]);

  const nothingLoaded = trending === null && gems === null && freeTonight === null &&
    newNoteworthy === null && (recs === null || !isAuth);

  if (nothingLoaded) {
    return (
      <>
        <div className="rounded-2xl border border-border bg-surface p-8 sm:p-12 mb-8">
          <div className="h-8 w-64 skeleton mb-2" />
          <div className="h-4 w-96 skeleton mb-6" />
          <div className="h-10 w-full max-w-lg skeleton rounded-lg" />
        </div>
        <SkeletonGrid count={5} />
      </>
    );
  }

  if (error) return <ErrorState message={error} onRetry={load} />;

  const hasTrending = trending?.length > 0;
  const hasTopRated = topRated?.length > 0;
  const hasGems = gems?.length > 0;
  const hasRecs = recs?.length > 0;
  const hasFreeTonight = freeTonight?.length > 0;
  const hasNewNoteworthy = newNoteworthy?.length > 0;
  const hasContinueWatching = isAuth && continueWatching?.length > 0;
  const watchedName = continueWatching?.[0]?.name;
  const hasBecauseWatched = isAuth && watchedName && becauseWatched?.length > 0;

  const freePlatforms = [
    ...new Map(
      (freeTonight || [])
        .flatMap(s => s.free_providers || [])
        .filter(p => p.provider_id && p.provider_name)
        .map(p => [p.provider_id, p])
    ).values(),
  ];
  const filteredFreeTonight = freePlatform
    ? (freeTonight || []).filter(s => (s.free_providers || []).some(p => p.provider_id === freePlatform))
    : (freeTonight || []);

  return (
    <div>
      <HeroSection />
      <MoodSlider />

      {hasTopRated && (
        <section className="mb-8">
          <SectionHeader title={t('home.topRated')} subtitle={t('home.topRatedSub')} />
          <SeriesGrid series={topRated} />
        </section>
      )}

      {hasContinueWatching && (
        <section className="mb-8">
          <SectionHeader title={t('home.continueWatching')} />
          <SeriesGrid series={continueWatching} />
        </section>
      )}

      {hasBecauseWatched && (
        <section className="mb-8">
          <SectionHeader title={t('home.becauseYouWatched', { name: watchedName })} />
          <SeriesGrid series={becauseWatched.slice(0, 8)} />
        </section>
      )}

      {guestPicks && (
        <section className="mb-8">
          <SectionHeader title={t('home.personalizedPicks')} subtitle={t('home.personalizedPicksSub')} />
          <SeriesGrid series={guestPicks} />
        </section>
      )}

      {hasTrending && (
        <section className="mb-8">
          <SectionHeader title={t('home.trending')} subtitle={t('home.trendingSub')} />
          <SeriesGrid series={trending} />
        </section>
      )}

      {isAuth && hasRecs && (
        <section className="mb-8">
          <SectionHeader title={t('home.recommendedForYou')} subtitle={t('home.recommendedForYouSub')} linkTo="/for-you" />
          <SeriesGrid
            series={recs}
            relevanceScores={Object.fromEntries(recs.map(r => [r.series_id, r.relevance_score]))}
          />
        </section>
      )}

      {isAuth && !hasRecs && (
        <section className="mb-8">
          <EmptyState
            title={t('home.personalizedComing')}
            message={t('home.personalizedComingMsg')}
          />
        </section>
      )}

      {hasGems && (
        <section className="mb-8">
          <SectionHeader title={t('home.hiddenGems')} subtitle={t('home.hiddenGemsSub')} linkTo="/discover" linkText={t('section.discoverMore')} />
          <SeriesGrid series={gems} />
        </section>
      )}

      {hasNewNoteworthy && (
        <section className="mb-8">
          <SectionHeader title={t('home.newNoteworthy')} subtitle={t('home.newNoteworthySub')} />
          <SeriesGrid series={newNoteworthy} />
        </section>
      )}

      {hasFreeTonight && (
        <section className="mb-8">
          <SectionHeader title={t('home.freeTonight')} subtitle={t('home.freeTonightSub')} linkTo="/discover" linkText={t('section.viewAll')} />
          <div className="flex gap-2 overflow-x-auto pb-2 mb-3 -mx-1 px-1">
            <button
              type="button"
              onClick={() => setFreePlatform(null)}
              className={`flex-shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors ${
                freePlatform === null
                  ? 'bg-accent text-bg border-accent'
                  : 'bg-surface border-border text-text-secondary hover:border-accent hover:text-accent'
              }`}
            >
              {t('freeFilter.all')}
            </button>
            {freePlatforms.map(fp => (
              <button
                key={fp.provider_id}
                type="button"
                onClick={() => setFreePlatform(fp.provider_id)}
                className={`flex-shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors ${
                  freePlatform === fp.provider_id
                    ? 'bg-accent text-bg border-accent'
                    : 'bg-surface border-border text-text-secondary hover:border-accent hover:text-accent'
                }`}
              >
                {fp.logo_url ? (
                  <img src={fp.logo_url} alt="" loading="lazy" className="w-4 h-4 rounded object-contain" />
                ) : null}
                {fp.provider_name}
              </button>
            ))}
          </div>
          <SeriesGrid series={filteredFreeTonight} showFreeHint />
        </section>
      )}
    </div>
  );
}