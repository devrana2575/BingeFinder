import { Link } from 'react-router-dom';
import PosterImage from './PosterImage';
import RatingBadge from './RatingBadge';
import GenreTags from './GenreTags';
import { t } from '../i18n';

export default function SeriesCard({ series, relevanceScore, showFreeHint, onRemove, removeLabel }) {
  const id = series.series_id;
  const title = series.name || t('card.untitled');
  const year = series.premiered ? series.premiered.slice(0, 4) : null;
  const score = relevanceScore ?? series.relevance_score;
  const freeTier = series.free_tier;
  const freeNames = series.free_provider_names || [];
  const myServices = series._my_services || series.my_services || [];

  return (
    <div className="group bg-surface border border-border rounded-xl overflow-hidden flex flex-col transition-colors duration-150 hover:border-border-hover">
      <Link to={`/series/${id}`} className="block relative aspect-[2/3] bg-surface-2">
        <PosterImage src={series.image} title={title} />
        {onRemove && (
          <button
            type="button"
            onClick={(e) => {
              e.preventDefault();
              onRemove(series);
            }}
            aria-label={removeLabel || 'Remove'}
            className="absolute top-2 right-2 w-7 h-7 rounded-full bg-black/70 text-text border border-border hover:border-danger hover:text-danger flex items-center justify-center text-sm transition-colors"
          >
            {'\u00d7'}
          </button>
        )}
        {showFreeHint && (freeTier === 'free' || freeTier === 'free_with_ads') && (
          <span
            className={`absolute top-2 left-2 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
              freeTier === 'free' ? 'bg-free text-bg' : 'bg-accent text-bg'
            }`}
          >
            {freeTier === 'free' ? t('card.free') : t('card.freeWithAds')}
          </span>
        )}
        {showFreeHint && freeTier == null && freeNames.length > 0 && (
          <span className="absolute top-2 left-2 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-free text-bg">
            {t('card.free')}
          </span>
        )}
      </Link>

      <div className="p-3 flex flex-col flex-1">
        <Link to={`/series/${id}`}>
          <h3 className="font-semibold text-sm text-text leading-snug line-clamp-2 mb-1 hover:text-accent transition-colors">
            {title}{year ? ` (${year})` : ''}
          </h3>
        </Link>

        <div className="flex items-center gap-1.5 flex-wrap mb-2">
          <RatingBadge rating={series.rating} />
          {score != null && (
            <span className="text-xs font-semibold text-accent">
              {t('card.match', { score: Math.round(score * 100) })}
            </span>
          )}
        </div>

        {showFreeHint && freeNames.length > 0 && (
          <span className="text-xs text-free font-medium mb-2">
            {t('card.freeOn', { names: freeNames.join(', ') })}
          </span>
        )}

        {myServices.length > 0 && (
          <span className="text-xs font-semibold text-accent mb-2">
            {t('card.onServices', { names: myServices.join(', ') })}
          </span>
        )}

        <div className="mb-3">
          <GenreTags genres={series.genres} />
        </div>

        <div className="mt-auto">
          <Link
            to={`/series/${id}`}
            className="block w-full text-center py-2 rounded-lg text-sm font-semibold text-text-secondary border border-border hover:border-accent hover:text-accent transition-colors"
          >
            {t('card.viewDetails')}
          </Link>
        </div>
      </div>
    </div>
  );
}