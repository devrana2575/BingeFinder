import { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useRegion } from '../context/RegionContext';
import { t } from '../i18n';
import { SkeletonText } from '../components/Skeletons';

const GUEST_PREFS_KEY = 'bf_guest_prefs';

const LANGUAGE_OPTIONS = [
  'English', 'Hindi', 'Spanish', 'French', 'German', 'Korean',
  'Japanese', 'Chinese', 'Italian', 'Portuguese', 'Arabic', 'Russian',
];

const GENRE_OPTIONS = [
  'Action', 'Adventure', 'Animation', 'Comedy', 'Crime', 'Drama',
  'Fantasy', 'Horror', 'Mystery', 'Romance', 'Science-Fiction',
  'Thriller', 'Documentary', 'Family', 'History', 'War',
];

const MAX_LANGUAGES = 5;
const MAX_GENRES = 8;

function ChipGroup({ label, hint, options, selected, onToggle, max }) {
  return (
    <fieldset className="rounded-xl border border-border bg-surface p-5">
      <legend className="px-1 text-sm font-semibold text-text">{label}</legend>
      <p className="text-xs text-text-muted mt-1">{hint}</p>
      <div className="flex flex-wrap gap-2 mt-3">
        {options.map(opt => {
          const active = selected.includes(opt);
          const disabled = !active && selected.length >= max;
          return (
            <button
              key={opt}
              type="button"
              onClick={() => onToggle(opt)}
              disabled={disabled}
              aria-pressed={active}
              className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
                active
                  ? 'bg-accent text-bg border-accent font-semibold'
                  : 'bg-surface border-border text-text-secondary hover:border-accent hover:text-accent'
              } disabled:opacity-40 disabled:cursor-not-allowed`}
            >
              {opt}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}

export default function SettingsPage() {
  const { isAuth } = useAuth();
  const { region, regionName, regions, setRegion, ready: regionReady } = useRegion();

  const [loading, setLoading] = useState(true);
  const [languages, setLanguages] = useState([]);
  const [genres, setGenres] = useState([]);
  const [services, setServices] = useState([]);
  const [availableProviders, setAvailableProviders] = useState([]);
  const [providersError, setProvidersError] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      let prefs = {};
      if (isAuth) {
        try { prefs = await api.getSettings(); } catch {}
      } else {
        try { prefs = JSON.parse(localStorage.getItem(GUEST_PREFS_KEY) || '{}'); } catch {}
      }
      if (!mounted) return;
      setLanguages(prefs.languages || []);
      setGenres(prefs.genres || []);
      setServices(prefs.services || []);
      setLoading(false);
    };
    load();
    return () => { mounted = false; };
  }, [isAuth]);

  useEffect(() => {
    let mounted = true;
    setProvidersError(false);
    api.availableProviders(region)
      .then(d => {
        if (!mounted) return;
        setAvailableProviders(Array.isArray(d.providers) ? d.providers : []);
      })
      .catch(() => { if (mounted) setProvidersError(true); });
    return () => { mounted = false; };
  }, [region]);

  const toggle = (list, setList, item) =>
    setList(prev => prev.includes(item) ? prev.filter(i => i !== item) : [...prev, item]);

  const toggleService = (id) =>
    setServices(prev => prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]);

  const save = useCallback(async () => {
    setSaving(true);
    setError(null);
    setSaved(false);
    const payload = { region, languages, genres, services };
    if (isAuth) {
      try {
        await api.updateSettings(payload);
        setSaved(true);
      } catch (e) {
        setError(e.message || t('settings.savedError'));
      }
    } else {
      localStorage.setItem(GUEST_PREFS_KEY, JSON.stringify({ languages, genres, services }));
      setSaved(true);
    }
    setSaving(false);
  }, [isAuth, region, languages, genres, services]);

  if (loading || !regionReady) {
    return (
      <div className="max-w-xl">
        <div className="h-7 w-40 skeleton mb-2" />
        <SkeletonText lines={8} />
      </div>
    );
  }

  return (
    <div className="max-w-xl">
      <h1 className="text-xl font-bold text-text mb-1">{t('settings.title')}</h1>
      <p className="text-sm text-text-muted mb-6">{t('settings.subtitle')}</p>
      {!isAuth && (
        <p className="text-xs text-text-muted bg-surface border border-border rounded-lg px-3 py-2 mb-4">
          {t('settings.guestNote')}
        </p>
      )}

      <div className="rounded-xl border border-border bg-surface p-5 mb-4">
        <label htmlFor="settings-region" className="text-sm font-semibold text-text">
          {t('settings.region')}
        </label>
        <p className="text-xs text-text-muted mt-1 mb-3">{t('settings.regionHint')}</p>
        <select
          id="settings-region"
          value={region || ''}
          onChange={(e) => setRegion(e.target.value)}
          className="w-full px-3 py-2 rounded-lg bg-bg border border-border text-text text-sm focus:border-accent"
        >
          {regions.map(r => <option key={r.code} value={r.code}>{r.name}</option>)}
        </select>
        <p className="text-xs text-text-muted mt-2">Showing: {regionName}</p>
      </div>

      <div className="space-y-4 mb-6">
        <ChipGroup
          label={t('settings.languages')}
          hint={t('settings.languagesHint', { max: MAX_LANGUAGES })}
          options={LANGUAGE_OPTIONS}
          selected={languages}
          onToggle={(item) => toggle(languages, setLanguages, item)}
          max={MAX_LANGUAGES}
        />
        <ChipGroup
          label={t('settings.genres')}
          hint={t('settings.genresHint', { max: MAX_GENRES })}
          options={GENRE_OPTIONS}
          selected={genres}
          onToggle={(item) => toggle(genres, setGenres, item)}
          max={MAX_GENRES}
        />
      </div>

      <fieldset className="rounded-xl border border-border bg-surface p-5 mb-6">
        <legend className="px-1 text-sm font-semibold text-text">{t('settings.services')}</legend>
        <p className="text-xs text-text-muted mt-1">{t('settings.servicesHint')}</p>
        {providersError ? (
          <p className="text-xs text-text-muted mt-3">{t('settings.servicesUnavailable')}</p>
        ) : availableProviders.length === 0 ? (
          <p className="text-xs text-text-muted mt-3">{t('settings.servicesUnavailable')}</p>
        ) : (
          <div className="flex flex-wrap gap-2 mt-3">
            {availableProviders.map(provider => {
              const active = services.includes(provider.provider_id);
              return (
                <button
                  key={provider.provider_id}
                  type="button"
                  onClick={() => toggleService(provider.provider_id)}
                  aria-pressed={active}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm border transition-colors ${
                    active
                      ? 'bg-accent text-bg border-accent font-semibold'
                      : 'bg-surface border-border text-text-secondary hover:border-accent hover:text-accent'
                  }`}
                >
                  {provider.logo_url ? (
                    <img
                      src={provider.logo_url}
                      alt=""
                      loading="lazy"
                      className="w-5 h-5 rounded"
                      onError={(e) => { e.currentTarget.style.display = 'none'; }}
                    />
                  ) : null}
                  <span>{provider.provider_name}</span>
                </button>
              );
            })}
          </div>
        )}
      </fieldset>

      {error && <p className="text-sm text-danger mb-2">{error}</p>}
      {saved && !error && <p className="text-sm text-success mb-2">{t('settings.saved')}</p>}

      <button onClick={save} disabled={saving} className="btn-primary">
        {saving ? '…' : t('settings.save')}
      </button>
    </div>
  );
}