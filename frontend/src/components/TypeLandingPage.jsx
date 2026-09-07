import { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useRegion } from '../context/RegionContext';
import { t } from '../i18n';
import SeriesGrid from './SeriesGrid';
import { SkeletonGrid } from './Skeletons';
import ErrorState from './ErrorState';
import EmptyState from './EmptyState';

const TYPE_LABELS = {
  tv_series: 'types.series',
  movie: 'types.movies',
  anime: 'types.anime',
};

const TYPE_SUBTITLES = {
  tv_series: 'types.seriesSub',
  movie: 'types.moviesSub',
  anime: 'types.animeSub',
};

function SectionHeader({ title, linkTo, viewAll }) {
  return (
    <div className="flex items-end justify-between mb-3">
      <h2 className="text-base font-semibold text-text">{title}</h2>
      {linkTo && (
        <Link to={linkTo} className="text-xs text-accent hover:underline flex-shrink-0">
          {viewAll || t('section.viewAll')}
        </Link>
      )}
    </div>
  );
}

export default function TypeLandingPage({ type }) {
  const { region } = useRegion();
  const navigate = useNavigate();
  const [trending, setTrending] = useState(null);
  const [gems, setGems] = useState(null);
  const [freeTonight, setFreeTonight] = useState(null);
  const [newNoteworthy, setNewNoteworthy] = useState(null);
  const [count, setCount] = useState(null);
  const [query, setQuery] = useState('');
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const labelKey = TYPE_LABELS[type] || 'types.series';
  const subKey = TYPE_SUBTITLES[type] || 'types.seriesSub';

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    const tasks = [
      api.search({ content_type: type }).then(d => setCount(d.total_results || 0)).catch(() => null),
      api.trending(type).catch(e => { console.error(e); return []; }),
      api.hiddenGems(type).catch(e => { console.error(e); return []; }),
      api.freeTonight(region, type).catch(e => { console.error(e); return []; }),
      api.newNoteworthy(type).catch(e => { console.error(e); return []; }),
    ];
    Promise.all(tasks)
      .then(results => {
        setTrending(results[1]);
        setGems(results[2]);
        setFreeTonight(results[3]);
        setNewNoteworthy(results[4]);
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [type, region]);

  useEffect(load, [load]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (query.trim()) {
      navigate(`/discover?type=${type}&q=${encodeURIComponent(query.trim())}`);
    }
  };

  if (loading) {
    return (
      <>
        <div className="rounded-2xl border border-border bg-surface p-8 mb-8">
          <div className="h-8 w-64 skeleton mb-2" />
          <div className="h-4 w-96 skeleton mb-6" />
          <div className="h-10 w-full max-w-lg skeleton rounded-lg" />
        </div>
        <SkeletonGrid count={5} />
      </>
    );
  }

  if (error) return <ErrorState message={error} onRetry={load} />;

  const hasAny = (trending?.length || 0) + (gems?.length || 0) + (freeTonight?.length || 0) + (newNoteworthy?.length || 0) > 0;

  return (
    <div>
      <section className="rounded-2xl border border-border bg-surface p-8 sm:p-10 mb-8">
        <h1 className="text-2xl sm:text-3xl font-bold text-text mb-1" style={{ fontFamily: 'Sora, sans-serif' }}>
          {t(labelKey)}
        </h1>
        <p className="text-text-muted text-sm mb-5 max-w-lg">
          {count != null && count > 0
            ? t('types.count', { count: count.toLocaleString(), label: t(labelKey).toLowerCase() })
            : t(subKey)}
        </p>
        <form onSubmit={handleSubmit} className="flex gap-3 max-w-lg">
          <label htmlFor={`${type}-search`} className="sr-only">{t('types.searchLabel')}</label>
          <input
            id={`${type}-search`}
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder={t('types.searchPlaceholder', { label: t(labelKey) })}
            className="flex-1 px-4 py-2.5 rounded-lg bg-bg border border-border text-text text-sm placeholder:text-text-muted focus:border-accent"
          />
          <button type="submit" className="btn-primary">{t('types.searchButton')}</button>
        </form>
        <Link to={`/discover?type=${type}`} className="inline-block mt-4 text-sm text-text-secondary hover:text-accent transition-colors">
          {t('types.browseAll', { label: t(labelKey) })}
        </Link>
      </section>

      {!hasAny ? (
        <EmptyState
          title={t('types.emptyTitle', { label: t(labelKey) })}
          message={t('types.emptyMsg', { label: t(labelKey) })}
        />
      ) : (
        <>
          {trending?.length > 0 && (
            <section className="mb-8">
              <SectionHeader title={t('home.trending')} subtitle={null} linkTo={`/discover?type=${type}`} />
              <SeriesGrid series={trending} />
            </section>
          )}

          {gems?.length > 0 && (
            <section className="mb-8">
              <SectionHeader title={t('home.hiddenGems')} linkTo={`/discover?type=${type}`} />
              <SeriesGrid series={gems} />
            </section>
          )}

          {newNoteworthy?.length > 0 && (
            <section className="mb-8">
              <SectionHeader title={t('home.newNoteworthy')} />
              <SeriesGrid series={newNoteworthy} />
            </section>
          )}

          {freeTonight?.length > 0 && (
            <section className="mb-8">
              <SectionHeader title={t('home.freeTonight')} linkTo={`/discover?type=${type}`} />
              <SeriesGrid series={freeTonight} showFreeHint />
            </section>
          )}
        </>
      )}
    </div>
  );
}