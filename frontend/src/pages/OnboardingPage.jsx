import { useState, useEffect, useCallback } from 'react';
import { useNavigate, Navigate } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useRegion } from '../context/RegionContext';
import { t } from '../i18n';

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

const STEPS = ['genres', 'languages', 'favorites'];

function Chip({ label, active, onClick, disabled }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-pressed={active}
      className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
        active
          ? 'bg-accent text-bg border-accent font-semibold'
          : 'bg-surface border-border text-text-secondary hover:border-accent hover:text-accent'
      } disabled:opacity-40 disabled:cursor-not-allowed`}
    >
      {label}
    </button>
  );
}

function FavoriteRow({ series, loved, onToggle }) {
  const title = series.name || series.title || t('card.untitled');
  const year = series.premiered ? series.premiered.slice(0, 4) : null;
  return (
    <div className="flex items-center gap-3 p-3 rounded-lg bg-surface border border-border">
      {series.image ? (
        <img
          src={series.image}
          alt=""
          loading="lazy"
          className="w-10 h-14 rounded object-cover bg-surface-3"
          onError={(e) => { e.currentTarget.style.display = 'none'; }}
        />
      ) : (
        <div className="w-10 h-14 rounded bg-surface-3 flex items-center justify-center text-xs text-text-muted">
          {title.charAt(0)}
        </div>
      )}
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-text truncate">
          {title}{year ? ` (${year})` : ''}
        </div>
        <div className="text-xs text-text-muted truncate">{(series.genres || []).join(' · ') || '\u00a0'}</div>
      </div>
      <button
        type="button"
        onClick={() => onToggle(series.series_id)}
        aria-pressed={loved}
        className={`flex-shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors ${
          loved
            ? 'bg-free text-bg border-free'
            : 'bg-surface border-border text-text-secondary hover:border-accent hover:text-accent'
        }`}
      >
        {loved ? t('onboarding.favoriteAdded') : t('onboarding.favoriteAdd')}
      </button>
    </div>
  );
}

export default function OnboardingPage() {
  const { isAuth, loading: authLoading } = useAuth();
  const { region } = useRegion();
  const navigate = useNavigate();

  const [step, setStep] = useState(0);
  const [languages, setLanguages] = useState([]);
  const [genres, setGenres] = useState([]);
  const [lovedIds, setLovedIds] = useState(new Set());
  const [favorites, setFavorites] = useState([]);
  const [query, setQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!isAuth) return;
    let mounted = true;
    Promise.all([api.getSettings(), api.reactions(), api.trending()])
      .then(([settings, reacts, trending]) => {
        if (!mounted) return;
        setLanguages(settings.languages || []);
        setGenres(settings.genres || []);
        setLovedIds(new Set(reacts.filter(r => r.reaction === 'love').map(r => r.series_id)));
        setFavorites(Array.isArray(trending) ? trending.slice(0, 8) : []);
      })
      .catch(() => {});
  }, [isAuth]);

  useEffect(() => {
    if (!query.trim()) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      setSearching(true);
      api.search({ q: query.trim(), limit: 8 })
        .then(d => { if (!cancelled) setFavorites(d.results || d || []); })
        .catch(() => {})
        .finally(() => { if (!cancelled) setSearching(false); });
    }, 300);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [query]);

  const toggleInList = (list, setList, item, max) =>
    setList(prev => prev.includes(item) ? prev.filter(i => i !== item) : (prev.length >= max ? prev : [...prev, item]));

  const toggleFavorite = useCallback((seriesId) => {
    const willLove = !lovedIds.has(seriesId);
    setLovedIds(prev => {
      const next = new Set(prev);
      if (willLove) next.add(seriesId); else next.delete(seriesId);
      return next;
    });
    if (willLove) {
      api.setReaction(seriesId, 'love').catch(() => {});
    } else {
      api.clearReaction(seriesId).catch(() => {});
    }
  }, [lovedIds]);

  const finish = useCallback(async () => {
    setSaving(true);
    setError(null);
    try {
      await api.updateSettings({ region, languages, genres });
      navigate('/');
    } catch (e) {
      setError(e.message || t('onboarding.savedError'));
      setSaving(false);
    }
  }, [region, languages, genres, navigate]);

  if (authLoading) return <div className="h-40 skeleton" />;
  if (!isAuth) return <Navigate to="/login" replace />;

  const isLastStep = step === STEPS.length - 1;
  const stepLabel = STEPS[step];

  return (
    <div className="max-w-2xl mx-auto mt-10">
      <div className="mb-2 flex items-center gap-2">
        {STEPS.map((_, i) => (
          <div key={i} className={`h-1 flex-1 rounded ${i <= step ? 'bg-accent' : 'bg-surface-3'}`} />
        ))}
      </div>
      <p className="text-xs text-text-muted mb-6">
        {t('onboarding.stepCount', { current: step + 1, total: STEPS.length })}
      </p>

      {error && (
        <div className="mb-4 p-3 rounded-lg bg-danger/10 border border-danger/20 text-sm text-danger text-center">
          {error}
        </div>
      )}

      {stepLabel === 'genres' && (
        <fieldset className="rounded-xl border border-border bg-surface p-5">
          <legend className="px-1 text-sm font-semibold text-text">{t('onboarding.genresTitle')}</legend>
          <p className="text-xs text-text-muted mt-1 mb-4">
            {t('onboarding.genresHint', { max: MAX_GENRES })}
          </p>
          <div className="flex flex-wrap gap-2">
            {GENRE_OPTIONS.map(opt => (
              <Chip
                key={opt}
                label={opt}
                active={genres.includes(opt)}
                disabled={!genres.includes(opt) && genres.length >= MAX_GENRES}
                onClick={() => toggleInList(genres, setGenres, opt, MAX_GENRES)}
              />
            ))}
          </div>
        </fieldset>
      )}

      {stepLabel === 'languages' && (
        <fieldset className="rounded-xl border border-border bg-surface p-5">
          <legend className="px-1 text-sm font-semibold text-text">{t('onboarding.languagesTitle')}</legend>
          <p className="text-xs text-text-muted mt-1 mb-4">
            {t('onboarding.languagesHint', { max: MAX_LANGUAGES })}
          </p>
          <div className="flex flex-wrap gap-2">
            {LANGUAGE_OPTIONS.map(opt => (
              <Chip
                key={opt}
                label={opt}
                active={languages.includes(opt)}
                disabled={!languages.includes(opt) && languages.length >= MAX_LANGUAGES}
                onClick={() => toggleInList(languages, setLanguages, opt, MAX_LANGUAGES)}
              />
            ))}
          </div>
        </fieldset>
      )}

      {stepLabel === 'favorites' && (
        <div className="rounded-xl border border-border bg-surface p-5">
          <h2 className="text-sm font-semibold text-text">{t('onboarding.favoritesTitle')}</h2>
          <p className="text-xs text-text-muted mt-1 mb-4">
            {t('onboarding.favoritesHint')}
            {lovedIds.size > 0 && (
              <span className="ml-1 text-free font-medium">
                {t('onboarding.favoritesCount', { count: lovedIds.size })}
              </span>
            )}
          </p>
          <input
            type="search"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder={t('onboarding.searchPlaceholder')}
            className="w-full px-3 py-2 mb-4 rounded-lg bg-bg border border-border text-text text-sm placeholder:text-text-muted focus:border-accent"
          />
          {searching ? (
            <div className="h-24 skeleton" />
          ) : favorites.length === 0 ? (
            <p className="text-sm text-text-muted">{t('onboarding.favoritesEmpty')}</p>
          ) : (
            <div className="space-y-2 max-h-[50vh] overflow-y-auto pr-1">
              {favorites.map(s => (
                <FavoriteRow
                  key={s.series_id}
                  series={s}
                  loved={lovedIds.has(s.series_id)}
                  onToggle={toggleFavorite}
                />
              ))}
            </div>
          )}
        </div>
      )}

      <div className="flex items-center justify-between mt-6">
        <button
          type="button"
          onClick={() => navigate('/')}
          className="text-sm text-text-muted hover:text-text-secondary"
        >
          {t('onboarding.skip')}
        </button>
        <div className="flex gap-2">
          {step > 0 && (
            <button type="button" onClick={() => setStep(s => s - 1)} className="btn-ghost">
              {t('onboarding.back')}
            </button>
          )}
          {isLastStep ? (
            <button onClick={finish} disabled={saving} className="btn-primary">
              {saving ? t('onboarding.saving') : t('onboarding.finish')}
            </button>
          ) : (
            <button type="button" onClick={() => setStep(s => s + 1)} className="btn-primary">
              {t('onboarding.next')}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}