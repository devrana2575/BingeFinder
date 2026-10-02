import { useState } from 'react';

/**
 * Cinematic hero for the homepage. Uses a real landscape backdrop from
 * /discover/featured (no extra assets or dependencies) and cycles through a
 * few of them when more than one is available.
 */
export default function Hero({ backdrops = [], brand, title, tagline, subtitle, count, children }) {
  const [index, setIndex] = useState(0);
  const slides = backdrops.filter(Boolean);
  const active = slides.length > 0 ? slides[index % slides.length] : null;

  return (
    <section className="relative overflow-hidden rounded-2xl mb-8 sm:mb-10 isolate">
      <div className="absolute inset-0 -z-10 bg-surface-2" />

      {active && (
        <div
          key={active}
          className="absolute inset-0 -z-10 bg-cover bg-center opacity-45 fade-in"
          style={{ backgroundImage: `url(${active})` }}
        />
      )}

      {/* Cinematic scrims: keeps text legible over any artwork. */}
      <div className="absolute inset-0 -z-10 bg-gradient-to-r from-bg via-bg/85 to-bg/20" />
      <div className="absolute inset-0 -z-10 bg-gradient-to-t from-bg via-transparent to-bg/60" />
      <div className="absolute -top-24 -right-16 -z-10 w-80 h-80 rounded-full bg-accent/20 blur-[100px]" />

      <div className="px-5 py-10 sm:px-10 sm:py-16 lg:py-20 max-w-2xl">
        <p className="text-[11px] font-bold uppercase tracking-[0.22em] text-accent-light mb-3">
          {brand}
        </p>
        <h1
          className="text-3xl sm:text-5xl font-extrabold tracking-tight text-text leading-[1.05] mb-3"
          style={{ fontFamily: 'Sora, sans-serif' }}
        >
          {title}
        </h1>
        <p className="text-sm font-semibold text-accent-light mb-2">{tagline}</p>
        <p className="text-sm text-text-secondary max-w-md mb-6">{subtitle}</p>

        <div className="mb-5">{children}</div>

        <div className="flex items-center gap-3 text-[11px] text-text-muted">
          {count != null && <span>{count.toLocaleString()} titles</span>}
          {slides.length > 1 && (
            <div className="flex gap-1.5" role="tablist" aria-label="Featured backdrops">
              {slides.map((_, i) => (
                <button
                  key={i}
                  type="button"
                  role="tab"
                  aria-selected={i === (index % slides.length)}
                  aria-label={`Featured ${i + 1}`}
                  onClick={() => setIndex(i)}
                  className={`h-1.5 rounded-full transition-all ${
                    i === (index % slides.length) ? 'w-6 bg-accent' : 'w-1.5 bg-white/25 hover:bg-white/40'
                  }`}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}