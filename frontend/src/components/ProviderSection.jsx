import { useState } from 'react';
import { t } from '../i18n';
import { api } from '../api/client';

function ProviderCard({ platform, action, watchNowUrl, justwatchUrl, seriesId }) {
  const href = platform.watch_url || watchNowUrl || justwatchUrl;
  const label = platform.watch_url || watchNowUrl ? t('detail.watchNow') : t('detail.viewAvailability');
  return (
    <div className="flex items-center gap-3 p-3 rounded-lg bg-surface-2 border border-border">
      {platform.logo_url ? (
        <img
          src={platform.logo_url}
          alt={platform.provider_name}
          loading="lazy"
          className="w-8 h-8 rounded"
          onError={(e) => { e.currentTarget.style.display = 'none'; }}
        />
      ) : null}
      {!platform.logo_url && (
        <div className="w-8 h-8 rounded bg-surface-3 flex items-center justify-center text-xs text-text-muted">
          {platform.provider_name?.charAt(0)}
        </div>
      )}
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-text truncate">{platform.provider_name}</div>
        <div className="text-xs text-text-muted">{action}</div>
      </div>
      {href && (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          onClick={() => {
            if (seriesId) api.recordEvent({ series_id: seriesId, event_type: 'provider_click' }).catch(() => {});
          }}
          className="flex-shrink-0 text-xs font-semibold text-accent hover:underline whitespace-nowrap"
        >
          {label}
        </a>
      )}
    </div>
  );
}

function SectionLabel({ children }) {
  return (
    <div className="mb-2">
      <span className="text-xs font-bold uppercase tracking-wider text-free">{children}</span>
    </div>
  );
}

export default function ProviderSection({ providers, justwatchUrl, watchNowUrl, region, seriesId, status }) {
  const [showPaid, setShowPaid] = useState(false);

  const regionLabel = (region || 'US').toUpperCase();

  const free = (providers?.free) || [];
  const ads = (providers?.ads) || [];
  const flatrate = providers?.flatrate || [];
  const rent = providers?.rent || [];
  const buy = providers?.buy || [];
  const hasPaid = flatrate.length > 0 || rent.length > 0 || buy.length > 0;

  const isLoading = providers == null && status == null;
  const isNotConfigured = status === 'not_configured';
  const isError = status === 'error';
  const emptyResult = status === 'ok' && free.length === 0 && ads.length === 0
    && flatrate.length === 0 && rent.length === 0 && buy.length === 0;

  // Keyless fallback: when structured watch-availability isn't configured or
  // temporarily fails, still give the user a real, region-aware JustWatch page
  // to verify where a title is free. Real data, never fabricated — the deep
  // link is derived from the title + region.
  const JustWatchFallback = ({ message }) => (
    <section className="rounded-xl border border-border bg-surface p-5 mb-8">
      <div className="flex items-baseline justify-between mb-3">
        <h2 className="text-base font-semibold text-text">{t('detail.watchProviderTitle')}</h2>
        <span className="text-xs text-text-muted">{regionLabel}</span>
      </div>
      <p className="text-sm text-text-muted mb-4">{message}</p>
      {justwatchUrl && (
        <a
          href={justwatchUrl}
          target="_blank"
          rel="noopener noreferrer"
          onClick={() => {
            if (seriesId) api.recordEvent({ series_id: seriesId, event_type: 'provider_click' }).catch(() => {});
          }}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-bg bg-free hover:opacity-90 transition-opacity"
        >
          {t('detail.justwatchAvailability', { region: regionLabel })}
        </a>
      )}
      <p className="text-xs text-text-muted mt-3">{t('detail.justwatchHint')}</p>
    </section>
  );

  if (isNotConfigured) {
    return <JustWatchFallback message={t('detail.watchProviderNotConfigured')} />;
  }

  if (isError) {
    return <JustWatchFallback message={t('detail.watchProviderError')} />;
  }

  if (isLoading) {
    return (
      <section className="rounded-xl border border-border bg-surface p-5 mb-8">
        <h2 className="text-base font-semibold text-text mb-3">{t('detail.watchProviderTitle')}</h2>
        <p className="text-sm text-text-muted">{t('detail.watchProviderLoading')}</p>
      </section>
    );
  }

  if (emptyResult) {
    return (
      <section className="rounded-xl border border-border bg-surface p-5 mb-8">
        <h2 className="text-base font-semibold text-text mb-3">{t('detail.watchProviderTitle')}</h2>
        <p className="text-sm text-text-muted">
          {t('detail.noOptionsInRegion', { region: regionLabel })}
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-xl border border-border bg-surface p-5 mb-8">
      <div className="flex items-baseline justify-between mb-4">
        <h2 className="text-base font-semibold text-text">{t('detail.watchProviderTitle')}</h2>
        <span className="text-xs text-text-muted">{regionLabel}</span>
      </div>

      {free.length > 0 && (
        <div className="mb-3">
          <SectionLabel>{t('detail.free')}</SectionLabel>
          <div className="space-y-2">
            {free.map((p, i) => (
              <ProviderCard key={`free-${p.provider_name}-${i}`} platform={p} action={t('detail.free')} watchNowUrl={watchNowUrl} justwatchUrl={justwatchUrl} seriesId={seriesId} />
            ))}
          </div>
        </div>
      )}

      {ads.length > 0 && (
        <div className="mb-3">
          <SectionLabel>{t('detail.freeWithAds')}</SectionLabel>
          <div className="space-y-2">
            {ads.map((p, i) => (
              <ProviderCard key={`ads-${p.provider_name}-${i}`} platform={p} action={t('detail.freeWithAds')} watchNowUrl={watchNowUrl} justwatchUrl={justwatchUrl} seriesId={seriesId} />
            ))}
          </div>
        </div>
      )}

      {free.length === 0 && ads.length === 0 && (
        <p className="text-sm text-text-muted mb-4">
          {t('detail.noFreeInRegion', { region: regionLabel })}
        </p>
      )}

      {hasPaid && (
        <div>
          <button
            onClick={() => setShowPaid(!showPaid)}
            className="text-xs text-text-secondary hover:text-accent transition-colors mb-2 flex items-center gap-1"
          >
            {t('detail.otherWays')}
            <span className={`text-[10px] transition-transform ${showPaid ? 'rotate-90' : ''}`}>&#9654;</span>
          </button>
          {showPaid && (
            <div className="mt-2">
              {flatrate.length > 0 && (
                <div className="mb-3">
                  <SectionLabel>{t('detail.subscription')}</SectionLabel>
                  <div className="space-y-2">
                    {flatrate.map((p, i) => (
                      <ProviderCard key={`sub-${p.provider_name}-${i}`} platform={p} action={t('detail.subscription')} watchNowUrl={watchNowUrl} justwatchUrl={justwatchUrl} seriesId={seriesId} />
                    ))}
                  </div>
                </div>
              )}
              {(rent.length > 0 || buy.length > 0) && (
                <div>
                  <SectionLabel>{t('detail.rentBuy')}</SectionLabel>
                  <div className="space-y-2">
                    {rent.map((p, i) => (
                      <ProviderCard key={`rent-${p.provider_name}-${i}`} platform={p} action={t('detail.rentBuy')} watchNowUrl={watchNowUrl} justwatchUrl={justwatchUrl} seriesId={seriesId} />
                    ))}
                    {buy.map((p, i) => (
                      <ProviderCard key={`buy-${p.provider_name}-${i}`} platform={p} action={t('detail.rentBuy')} watchNowUrl={watchNowUrl} justwatchUrl={justwatchUrl} seriesId={seriesId} />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {free.length === 0 && ads.length === 0 && !hasPaid && (
        <p className="text-sm text-text-muted">
          {t('detail.noOptionsInRegion', { region: regionLabel })}
        </p>
      )}
    </section>
  );
}