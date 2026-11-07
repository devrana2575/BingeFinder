/**
 * Cinematic hero for the homepage and type landing pages.
 *
 * Intentionally artwork-free: no backdrop image is rendered behind the
 * headline. A pair of soft gradients plus an accent glow give it depth while
 * keeping the page light and fast.
 */
export default function Hero({ brand, title, tagline, subtitle, count, children }) {
  return (
    <section className="relative mb-8 sm:mb-10 isolate">
      {/* Soft accent wash that fades into the page background, so the hero has
          no visible panel edge and reads as part of the page rather than a
          separate card. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 -z-10"
        style={{
          background:
            'radial-gradient(ellipse 55% 120% at 85% -10%, rgba(41,121,255,0.14), transparent 70%), radial-gradient(ellipse 45% 90% at 0% 110%, rgba(41,121,255,0.06), transparent 70%)',
        }}
      />

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

        {count != null && (
          <div className="flex items-center gap-3 text-[11px] text-text-muted">
            <span>{count.toLocaleString()} titles</span>
          </div>
        )}
      </div>
    </section>
  );
}
