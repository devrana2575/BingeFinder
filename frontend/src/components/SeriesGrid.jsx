import SeriesCard from './SeriesCard';

export default function SeriesGrid({ series, relevanceScores, showFreeHint, showMatch, onRemove, removeLabel }) {
  if (!series || series.length === 0) {
    return null;
  }

  return (
    <div className="card-grid">
      {series.map(s => {
        const id = s.series_id;
        return (
          <SeriesCard
            key={id}
            series={s}
            relevanceScore={relevanceScores?.[id]}
            showFreeHint={showFreeHint}
            showMatch={showMatch}
            onRemove={onRemove}
            removeLabel={removeLabel}
          />
        );
      })}
    </div>
  );
}