import { useRegion } from '../context/RegionContext';
import { t } from '../i18n';

function GlobeIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="w-4 h-4 flex-shrink-0 text-text-muted"
    >
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18" />
      <path d="M12 3a13.5 13.5 0 0 1 0 18 13.5 13.5 0 0 1 0-18z" />
    </svg>
  );
}

/**
 * Region picker for the sidebar. Uses a native <select> for keyboard and
 * screen-reader support; the globe icon marks its purpose without relying
 * on flag emojis (which render inconsistently across platforms).
 */
export default function RegionSelector() {
  const { region, regions, setRegion, ready } = useRegion();

  if (!ready || regions.length === 0) return null;

  return (
    <label className="flex items-center gap-2 px-2 py-1.5 text-sm text-text-secondary">
      <GlobeIcon />
      <span className="sr-only">{t('region.selectorAria')}</span>
      <select
        value={region || ''}
        onChange={(e) => setRegion(e.target.value)}
        aria-label={t('region.selectorAria')}
        className="flex-1 min-w-0 bg-surface text-text text-sm focus:text-text focus:outline-none cursor-pointer"
      >
        {regions.map(r => (
          <option key={r.code} value={r.code}>{r.name}</option>
        ))}
      </select>
    </label>
  );
}