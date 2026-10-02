import { useState, useEffect, useCallback } from 'react';
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

const TYPE_LABELS = {
  tv_series: 'types.series',
  anime: 'types.anime',
};

const TYPE_SUBTITLES = {
  tv_series: 'types.seriesSub',
  anime: 'types.animeSub',
};

/**
 * Shared landing experience for /series and /anime. Both categories get the
 * same first-class treatment: cinematic hero, search, trending, popular,
 * hidden gems, because-you-watched, new & noteworthy, free tonight.
 */
export default function TypeLandingPage({ type }) {
  const { region } = useRegion();
  const { isAuth } = useAuth();
  const navigate = useNavigate();
  const [trending, setTrending] = useState(null);
  const [popular, setPopular] = useState(null);
  const [gems, setGems] = useState(null);
  const [freeTonight, setFreeTonight] = useState(null);
  const [newNoteworthy, setNewNoteworthy] = useState(null);
  const [becauseWatched, setBecauseWatched] = useState(null);
  const [watchedName, setWatchedName] = useState(null);
  const [error, setError] = useState(null);

  const labelKey = TYPE_LABELS[type] || 'types.series';
  const subKey = TYPE_SUBTITLES[type] || 'types.seriesSub';

  const load = useCallback(() => {
    setError(null);
    setTrending(null);
    setPopular(null);
    setGems(null);
    setFreeTonight(null);
    setNewNoteworthy(null);
    setBecauseWatched(null);
    setWatchedName(null);

    api.trending(type)
      .then(setTrending)
      .catch(e => { console.error(e); setTrending([]); });
    api.featured(type, 4)
      .then(setPopular)
      .catch(e => { console.error(e); setPopular([]); });
    api.hiddenGems(type)
      .then(setGems)
      .catch(e => { console.error(e); setGems([]); });
    api.freeTonight(region, type)
      .then(setFreeTonight)
      .catch(e => { console.error(e); setFreeTonight([]); });
    api.newNoteworthy(type)
      .then(setNewNoteworthy)
      .catch(e => { console.error(e); setNewNoteworthy([]); });

    if (isAuth) {
      api.recentlyViewed()
        .then(d => {
          const last = d?.[0];
          if (!last) return;
          setWatchedName(last.name);
          return api.seriesRecs(last.series_id)
            .then(res => setBecauseWatched(Array.isArray(res) ? res : res?.recommendations || []))
            .catch(() => setBecauseWatched([]));
        })
        .catch(() => {});
    }
  }, [type, region, isAuth]);

  useEffect(load, [load]);

  const nothingLoaded = trending === null && popular === null && gems === null &&
    freeTonight === null && newNoteworthy === null;

  if (nothingLoaded) {
    return (
      <>
        <div className="rounded-2xl bg-surface p-8 mb-9">
          <div className="h-10 w-64 skeleton mb-3" />
          <div className="h-4 w-96 skeleton mb-6" />
          <div className="h-12 w-full max-w-lg skeleton rounded-full" />
        </div>
        <SkeletonGrid count={5} />
      </>
    );
  }

  if (error) return <ErrorState message={error} onRetry={load} />;

  const total = (trending?.length || 0) + (popular?.length || 0) + (gems?.length || 0) +
    (freeTonight?.length || 0) + (newNoteworthy?.length || 0);

  return (
    <div>
      <Hero
        backdrops={(popular || []).map(f => f.image)}
        brand={t(labelKey)}
        title={t(subKey)}
        tagline={t('hero.tagline')}
        subtitle={t('hero.subtitle')}
        count={total || null}
      >
        <div className="max-w-xl">
          <label htmlFor={`${type}-search`} className="sr-only">{t('types.searchLabel')}</label>
          <SearchSuggest
            contentType={type}
            onSearch={q => navigate(`/discover?type=${type}&q=${encodeURIComponent(q.trim())}`)}
            placeholder={t('types.searchPlaceholder', { label: t(labelKey) })}
            containerClassName="w-full"
            inputClassName="w-full px-4 py-3 rounded-full bg-bg/70 backdrop-blur border border-border text-text text-sm placeholder:text-text-muted focus:border-accent focus:outline-none"
          />
        </div>
        <Link
          to={`/discover?type=${type}`}
          className="inline-block mt-4 text-sm font-semibold text-accent-light hover:text-accent transition-colors"
        >
          {t('types.browseAll', { label: t(labelKey) })} →
        </Link>
      </Hero>

      {total === 0 ? (
        <EmptyState
          title={t('types.emptyTitle', { label: t(labelKey) })}
          message={t('types.emptyMsg', { label: t(labelKey) })}
        />
      ) : (
        <>
          {trending?.length > 0 && (
            <PosterRail title={t('home.trending')} series={trending} linkTo={`/discover?type=${type}`} />
          )}

          {popular?.length > 0 && (
            <PosterRail title={t('home.popular')} series={popular} linkTo={`/discover?type=${type}`} />
          )}

          {becauseWatched?.length > 0 && (
            <PosterRail
              title={t('home.becauseYouWatched', { name: watchedName })}
              series={becauseWatched.slice(0, 12)}
              showMatch
            />
          )}

          {gems?.length > 0 && (
            <PosterRail title={t('home.hiddenGems')} subtitle={t('home.hiddenGemsSub')} series={gems} />
          )}

          {newNoteworthy?.length > 0 && (
            <PosterRail title={t('home.newNoteworthy')} subtitle={t('home.newNoteworthySub')} series={newNoteworthy} />
          )}

          {freeTonight?.length > 0 && (
            <PosterRail
              title={t('home.freeTonight')}
              subtitle={t('home.freeTonightSub')}
              series={freeTonight}
              showFreeHint
            />
          )}
        </>
      )}
    </div>
  );
}