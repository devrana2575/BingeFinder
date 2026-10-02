import { Link } from 'react-router-dom';
import SeriesCard from './SeriesCard';

/**
 * Horizontally scrollable poster rail — the primary homepage browsing pattern.
 * Keeps the page from reading like a dense database grid.
 */
export default function PosterRail({ title, subtitle, series, linkTo, linkText, showFreeHint, showMatch }) {
  if (!series || series.length === 0) return null;

  return (
    <section className="mb-9">
      <div className="flex items-end justify-between gap-4 mb-3">
        <div className="min-w-0">
          <h2 className="text-lg font-bold text-text tracking-tight">{title}</h2>
          {subtitle && <p className="text-xs text-text-muted mt-0.5 truncate">{subtitle}</p>}
        </div>
        {linkTo && (
          <Link to={linkTo} className="text-xs font-semibold text-accent hover:text-accent-light transition-colors flex-shrink-0">
            {linkText} →
          </Link>
        )}
      </div>
      <div className="flex gap-3 overflow-x-auto no-scrollbar pb-2 -mx-1 px-1 snap-x snap-mandatory">
        {series.map(s => (
          <div key={s.series_id} className="w-[140px] sm:w-[168px] flex-shrink-0 snap-start">
            <SeriesCard series={s} showFreeHint={showFreeHint} showMatch={showMatch} />
          </div>
        ))}
      </div>
    </section>
  );
}