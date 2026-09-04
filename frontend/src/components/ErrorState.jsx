export default function ErrorState({ message, onRetry }) {
  return (
    <div className="text-center py-12">
      <p className="text-text-secondary mb-4">{message || 'Something went wrong.'}</p>
      {onRetry && (
        <button onClick={onRetry} className="btn-ghost">
          Try Again
        </button>
      )}
    </div>
  );
}
