import SeriesCard from './SeriesCard';

export default function SeriesGrid({ series, relevanceScores, showFreeHint, onRemove, removeLabel }) {
  if (!series || series.length === 0) {
    return null;
  }

  return (
    <div className="card-grid">
      {series.map(s => {
        const id = s.series_id;
        const score = relevanceScores?.[id];
        return (
          <SeriesCard
            key={id}
            series={s}
            relevanceScore={score}
            showFreeHint={showFreeHint}
            onRemove={onRemove}
            removeLabel={removeLabel}
          />
        );
      })}
    </div>
  );
}
