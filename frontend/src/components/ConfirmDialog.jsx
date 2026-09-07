import { useEffect, useRef } from 'react';

export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  cancelLabel = 'Cancel',
  tone = 'danger',
  onConfirm,
  onClose,
}) {
  const confirmRef = useRef(null);
  const cancelRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const timer = setTimeout(() => cancelRef.current && cancelRef.current.focus(), 0);
    const onKey = (e) => {
      if (e.key === 'Escape') onClose();
      if (e.key === 'Tab') {
        const nodes = [cancelRef.current, confirmRef.current];
        if (nodes.every(Boolean)) {
          const first = nodes[0];
          const last = nodes[1];
          if (e.shiftKey && document.activeElement === first) {
            e.preventDefault();
            last.focus();
          } else if (!e.shiftKey && document.activeElement === last) {
            e.preventDefault();
            first.focus();
          }
        }
      }
    };
    document.addEventListener('keydown', onKey);
    return () => {
      clearTimeout(timer);
      document.removeEventListener('keydown', onKey);
    };
  }, [open, onClose]);

  if (!open) return null;

  const confirmButton =
    tone === 'danger' ? 'btn-danger' : 'btn-primary';

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center p-4"
      role="presentation"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="absolute inset-0 bg-black/60 fade-in" aria-hidden="true" />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        aria-describedby="confirm-dialog-message"
        className="relative w-full max-w-sm rounded-2xl border border-border bg-surface p-6 shadow-xl shadow-black/50 fade-in"
      >
        <h2 id="confirm-dialog-title" className="text-base font-bold text-text mb-2">
          {title}
        </h2>
        {message && (
          <p id="confirm-dialog-message" className="text-sm text-text-secondary mb-6">
            {message}
          </p>
        )}
        <div className="flex justify-end gap-3">
          <button ref={cancelRef} onClick={onClose} className="btn-ghost">
            {cancelLabel}
          </button>
          <button ref={confirmRef} onClick={onConfirm} className={confirmButton}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}