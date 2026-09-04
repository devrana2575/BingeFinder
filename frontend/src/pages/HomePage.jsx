import { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import SeriesGrid from '../components/SeriesGrid';
import { SkeletonGrid } from '../components/Skeletons';
import ErrorState from '../components/ErrorState';
import EmptyState from '../components/EmptyState';

function HeroSection() {
  const [query, setQuery] = useState('');
  const navigate = useNavigate();

  const handleSubmit = (e) => {
    e.preventDefault();
    if (query.trim()) navigate(`/discover?q=${encodeURIComponent(query.trim())}`);
  };

  return (
    <section className="rounded-2xl border border-border bg-surface p-8 sm:p-12 mb-8">
      <h1 className="text-2xl sm:text-3xl font-bold text-text mb-2" style={{ fontFamily: 'Sora, sans-serif' }}>
        What's your next binge?
      </h1>
      <p className="text-text-muted text-sm mb-6 max-w-lg">
        Search 3,500+ series or let us find something for you.
      </p>
      <form onSubmit={handleSubmit} className="flex gap-3 max-w-lg">
        <label htmlFor="hero-search" className="sr-only">Search for a series</label>
        <input
          id="hero-search"
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Search for a series..."
          className="flex-1 px-4 py-2.5 rounded-lg bg-bg border border-border text-text text-sm placeholder:text-text-muted focus:border-accent"
        />
        <button type="submit" className="btn-primary">Search</button>
      </form>
      <Link to="/surprise" className="inline-block mt-4 text-sm text-text-secondary hover:text-accent transition-colors">
        Not sure? Try Surprise Me
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
          key, emoji: val.emoji, label: val.label,
        }));
        setMoods(items);
      })
      .catch(() => {});
  }, []);

  if (!moods.length) return null;

  return (
    <section className="mb-8">
      <h2 className="text-base font-semibold text-text mb-3">Pick a mood</h2>
      <div className="flex gap-2 overflow-x-auto pb-2 -mx-1 px-1">
        {moods.map(m => (
          <Link
            key={m.key}
            to={`/discover/vibes/${m.key}`}
            className="flex-shrink-0 px-4 py-2 rounded-lg bg-surface border border-border text-sm text-text-secondary hover:border-accent hover:text-accent transition-colors whitespace-nowrap"
          >
            {m.emoji} {m.label}
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
        <Link to={linkTo} className="text-xs text-accent hover:underline flex-shrink-0">{linkText || 'View all'}</Link>
      )}
    </div>
  );
}

export default function HomePage() {
  const { isAuth } = useAuth();
  const [tonight, setTonight] = useState(null);
  const [gems, setGems] = useState(null);
  const [recs, setRecs] = useState(null);
  const [freeTonight, setFreeTonight] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    const tasks = [
      api.tonightsBinge().catch(e => { console.error(e); return []; }),
      api.hiddenGems().catch(e => { console.error(e); return []; }),
      api.freeTonight().catch(e => { console.error(e); return []; }),
    ];
    if (isAuth) {
      tasks.push(api.personalizedRecs().catch(() => null));
    }
    Promise.all(tasks)
      .then(results => {
        setTonight(results[0]);
        setGems(results[1]);
        setFreeTonight(results[2]);
        if (isAuth) setRecs(results[3]);
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [isAuth]);

  useEffect(load, [load]);

  if (loading) {
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

  const hasTonight = tonight?.length > 0;
  const hasGems = gems?.length > 0;
  const hasRecs = recs?.length > 0;
  const hasFreeTonight = freeTonight?.length > 0;

  return (
    <div>
      <HeroSection />
      <MoodSlider />

      {hasTonight && (
        <section className="mb-8">
          <SectionHeader title="Tonight's Binge" subtitle="Fresh picks for your next binge" />
          <SeriesGrid series={tonight} />
        </section>
      )}

      {isAuth && hasRecs && (
        <section className="mb-8">
          <SectionHeader title="Recommended For You" subtitle="Based on your history" linkTo="/for-you" />
          <SeriesGrid
            series={recs}
            relevanceScores={Object.fromEntries(recs.map(r => [r.series_id, r.relevance_score]))}
          />
        </section>
      )}

      {isAuth && !hasRecs && (
        <section className="mb-8">
          <EmptyState
            title="Personalized picks are coming"
            message="Keep exploring and we'll learn what you like."
          />
        </section>
      )}

      {hasGems && (
        <section className="mb-8">
          <SectionHeader title="Hidden Gems" subtitle="Less obvious, highly rated" linkTo="/discover" linkText="Discover more" />
          <SeriesGrid series={gems} />
        </section>
      )}

      {hasFreeTonight && (
        <section className="mb-8">
          <SectionHeader title="Free Tonight" subtitle="Stream free in India right now" linkTo="/discover" linkText="View all" />
          <SeriesGrid series={freeTonight} />
        </section>
      )}
    </div>
  );
}
