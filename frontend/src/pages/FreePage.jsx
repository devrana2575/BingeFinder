import { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import { useRegion } from '../context/RegionContext';
import { t } from '../i18n';
import SeriesGrid from '../components/SeriesGrid';
import { SkeletonGrid } from '../components/Skeletons';
import ErrorState from '../components/ErrorState';
import EmptyState from '../components/EmptyState';

const TABS = [
  { key: 'tv_series', label: 'free.tabSeries' },
  { key: 'anime', label: 'free.tabAnime' },
  { key: 'all', label: 'free.tabAll' },
];

const VALID_TABS = new Set(TABS.map(tab => tab.key));

export default function FreePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { region, regionName } = useRegion();
  const [series, setSeries] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const requestedTab = searchParams.get('type') || 'tv_series';
  const activeTab = VALID_TABS.has(requestedTab) ? requestedTab : 'tv_series';
  const contentType = activeTab === 'all' ? undefined : activeTab;

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    setSeries(null);
    api.freeTonight(region, contentType, 24)
      .then(data => setSeries(Array.isArray(data) ? data : []))
      .catch(e => {
        setError(e.message);
        setSeries([]);
      })
      .finally(() => setLoading(false));
  }, [region, contentType]);

  useEffect(load, [load]);

  const setTab = (key) => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev);
      if (key === 'tv_series') next.delete('type');
      else next.set('type', key);
      return next;
    });
  };

  const titleKey = activeTab === 'anime'
    ? 'free.animeTitle'
    : activeTab === 'all'
      ? 'free.title'
      : 'free.seriesTitle';

  const subtitleKey = activeTab === 'anime'
    ? 'free.animeSubtitle'
    : activeTab === 'all'
      ? 'free.subtitle'
      : 'free.seriesSubtitle';

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-xl font-bold text-text mb-1">{t(titleKey)}</h1>
        <p className="text-sm text-text-muted">
          {t(subtitleKey, { region: regionName })}
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2 mb-4">
        {TABS.map(tab => {
          const active = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => setTab(tab.key)}
              aria-pressed={active}
              className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
                active
                  ? 'bg-accent text-bg border-accent font-semibold'
                  : 'bg-surface border-border text-text-secondary hover:border-accent hover:text-accent'
              }`}
            >
              {t(tab.label)}
            </button>
          );
        })}
        {!loading && !error && series?.length > 0 && (
          <span className="text-xs text-text-muted ml-1">
            {t('free.results', { count: series.length, region: regionName })}
          </span>
        )}
      </div>

      {loading ? (
        <SkeletonGrid />
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : series.length === 0 ? (
        <EmptyState
          title={t('free.emptyTitle', { region: regionName })}
          message={t('free.emptyMsg')}
          action={(
            <div className="flex flex-wrap items-center justify-center gap-3">
              <Link to="/discover" className="btn-primary">{t('free.browseAll')}</Link>
              <Link to="/settings" className="btn-ghost">{t('free.changeRegion')}</Link>
            </div>
          )}
        />
      ) : (
        <>
          <SeriesGrid series={series} showFreeHint />
          <p className="text-xs text-text-muted mt-6 max-w-2xl">{t('free.disclaimer')}</p>
        </>
      )}
    </div>
  );
}
