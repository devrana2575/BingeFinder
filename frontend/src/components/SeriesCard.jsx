import { Link } from 'react-router-dom';
import PosterImage from './PosterImage';
import RatingBadge from './RatingBadge';
import GenreTags from './GenreTags';

export default function SeriesCard({ series, relevanceScore, showFreeHint }) {
  const id = series.series_id;
  const title = series.name || 'Untitled';
  const year = series.premiered ? series.premiered.slice(0, 4) : null;
  const score = relevanceScore ?? series.relevance_score;

  return (
    <div className="group bg-surface border border-border rounded-xl overflow-hidden flex flex-col transition-colors duration-150 hover:border-border-hover">
      <Link to={`/series/${id}`} className="block relative aspect-[2/3] bg-surface-2">
        <PosterImage src={series.image} title={title} />
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
              {Math.round(score * 100)}% match
            </span>
          )}
        </div>

        {showFreeHint && series._free_providers?.length > 0 && (
          <span className="text-xs text-free font-medium mb-2">
            Free: {series._free_providers.map(p => p.provider_name).join(', ')}
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
            View Details
          </Link>
        </div>
      </div>
    </div>
  );
}
