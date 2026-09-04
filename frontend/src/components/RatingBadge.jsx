export default function RatingBadge({ rating }) {
  if (rating == null) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold bg-surface-2 text-text-muted">
        N/A
      </span>
    );
  }

  let colorClass;
  if (rating >= 8.0) colorClass = 'bg-success/20 text-success';
  else if (rating >= 6.5) colorClass = 'bg-warning/20 text-warning';
  else colorClass = 'bg-danger/20 text-danger';

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold ${colorClass}`}>
      {rating.toFixed(1)}
    </span>
  );
}
