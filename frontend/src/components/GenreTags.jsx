export default function GenreTags({ genres, limit = 3 }) {
  const all = genres || [];
  const shown = all.slice(0, limit);
  const overflow = all.length - limit;

  if (!shown.length) {
    return null;
  }

  return (
    <div className="flex flex-wrap gap-1">
      {shown.map(g => (
        <span key={g} className="px-2 py-0.5 rounded text-xs bg-surface-2 text-text-muted">
          {g}
        </span>
      ))}
      {overflow > 0 && (
        <span className="px-2 py-0.5 rounded text-xs text-text-muted">+{overflow}</span>
      )}
    </div>
  );
}
