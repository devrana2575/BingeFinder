import { Link } from 'react-router-dom';
import PosterImage from './PosterImage';
import { t } from '../i18n';

const TYPE_LABELS = {
  tv_series: 'card.typeSeries',
  anime: 'card.typeAnime',
};

// Cosine similarity / relevance scores are NOT calibrated probabilities, so we
// never render them as "92% match". Bucketed language keeps the claim honest.
function matchLabel(score) {
  if (score == null) return null;
  if (score >= 0.75) return t('card.strongMatch');
  if (score >= 0.5) return t('card.goodMatch');
  return t('card.recommended');
}

export default function SeriesCard({
  series,
  relevanceScore,
  showFreeHint,
  showMatch = false,
  onRemove,
  removeLabel,
}) {
  const id = series.series_id;
  // Recommendation endpoints return `title`; catalog/search/discovery return
  // `name`. Never render a placeholder like "Untitled" when a title exists
  // under either key.
  const title = series.name || series.title || t('card.untitled');
  const year = series.premiered ? series.premiered.slice(0, 4) : null;
  const score = relevanceScore ?? series.relevance_score;
  const typeLabel = series.content_type === 'anime'
    ? t(TYPE_LABELS.anime)
    : t(TYPE_LABELS.tv_series);
  const match = matchLabel(score);
  const freeTier = series.free_tier;
  const freeNames = series.free_provider_names || [];
  const isFree = freeTier === 'free' || freeTier === 'free_with_ads';

  return (
    <article className="group relative flex flex-col">
      <Link
        to={`/series/${id}`}
        className="block relative aspect-[2/3] rounded-xl overflow-hidden bg-surface-2 ring-1 ring-white/5 transition-all duration-200 group-hover:ring-accent/60 group-hover:shadow-[0_10px_30px_-12px_rgba(41,121,255,0.55)] group-focus-visible:ring-2 group-focus-visible:ring-accent-light"
      >
        <PosterImage src={series.image} title={title} className="transition-transform duration-300 group-hover:scale-[1.04]" />

        <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/10 to-transparent opacity-70 group-hover:opacity-90 transition-opacity" />

        {(showFreeHint && (isFree || (freeTier == null && freeNames.length > 0))) && (
          <span className="absolute top-2 left-2 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-free text-bg">
            {isFree && freeTier === 'free_with_ads' ? t('card.freeWithAds') : t('card.free')}
          </span>
        )}

        {showMatch && match && (
          <span className="absolute top-2 right-2 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-black/65 backdrop-blur-sm text-accent-light ring-1 ring-accent/40">
            {match}
          </span>
        )}

        <div className="absolute inset-x-0 bottom-0 p-2.5">
          {series.rating != null && (
            <span className="inline-flex items-center gap-1 text-[11px] font-bold text-warning">
              <span aria-hidden>★</span>{series.rating.toFixed(1)}
            </span>
          )}
        </div>
      </Link>

      {onRemove && (
        <button
          type="button"
          onClick={(e) => { e.preventDefault(); onRemove(series); }}
          aria-label={removeLabel || t('action.remove')}
          className="absolute top-2 right-2 w-7 h-7 rounded-full bg-black/70 text-text ring-1 ring-border hover:bg-danger hover:text-white flex items-center justify-center text-sm transition-colors z-10"
        >
          {'\u00d7'}
        </button>
      )}

      <div className="mt-2">
        <Link to={`/series/${id}`} className="block">
          <h3 className="font-semibold text-sm text-text leading-snug line-clamp-2 hover:text-accent transition-colors">
            {title}
          </h3>
        </Link>
        <p className="text-[11px] text-text-muted mt-0.5 truncate">
          {typeLabel}{year ? ` · ${year}` : ''}
        </p>
      </div>
    </article>
  );
}