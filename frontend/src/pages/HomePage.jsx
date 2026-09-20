import { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useRegion } from '../context/RegionContext';
import { t } from '../i18n';
import RegionSelector from '../components/RegionSelector';
import SeriesGrid from '../components/SeriesGrid';
import SearchSuggest from '../components/SearchSuggest';
import { SkeletonGrid } from '../components/Skeletons';
import ErrorState from '../components/ErrorState';
import EmptyState from '../components/EmptyState';

function HeroSection() {
  const navigate = useNavigate();

  return (
    <section className="rounded-2xl border border-border bg-surface p-8 sm:p-12 mb-8">
      <h1 className="text-2xl sm:text-3xl font-bold text-text mb-2" style={{ fontFamily: 'Sora, sans-serif' }}>
        {t('hero.title')}
      </h1>
      <p className="text-text-muted text-sm mb-6 max-w-lg">
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
      <Link to="/surprise" className="inline-block mt-4 text-sm text-text-secondary hover:text-accent transition-colors">
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
  const [newNoteworthy, setNewNoteworthy] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setError(null);
    setTrending(null);
    setGems(null);
    setRecs(null);
    setFreeTonight(null);
    setNewNoteworthy(null);

    api.trending()
      .then(d => setTrending(d))
      .catch(e => { console.error(e); setTrending([]); });
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
    }
  }, [isAuth, region]);

  useEffect(load, [load]);

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
  const hasGems = gems?.length > 0;
  const hasRecs = recs?.length > 0;
  const hasFreeTonight = freeTonight?.length > 0;
  const hasNewNoteworthy = newNoteworthy?.length > 0;

  return (
    <div>
      {isAuth && (
        <div className="flex justify-end mb-4">
          <div className="rounded-lg border border-border bg-surface">
            <RegionSelector />
          </div>
        </div>
      )}

      <HeroSection />
      <MoodSlider />

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
          <SeriesGrid series={freeTonight} showFreeHint />
        </section>
      )}
    </div>
  );
}