export default function EmptyState({ title, message, action }) {
  return (
    <div className="text-center py-16">
      {title && <h3 className="text-lg font-semibold text-text mb-2">{title}</h3>}
      {message && <p className="text-text-muted text-sm mb-6 max-w-md mx-auto">{message}</p>}
      {action}
    </div>
  );
}
