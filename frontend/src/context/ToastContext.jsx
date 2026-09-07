import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';
import { t } from '../i18n';

const ToastContext = createContext(null);

const KIND_STYLE = {
  success: {
    border: 'border-success/40',
    iconBg: 'bg-success/15',
    icon: 'text-success',
    glyph: '\u2713',
  },
  info: {
    border: 'border-accent/40',
    iconBg: 'bg-accent/15',
    icon: 'text-accent',
    glyph: 'i',
  },
  error: {
    border: 'border-danger/40',
    iconBg: 'bg-danger/15',
    icon: 'text-danger',
    glyph: '!',
  },
};

function ToastItem({ toast, onDismiss }) {
  const style = KIND_STYLE[toast.kind] || KIND_STYLE.info;
  return (
    <div
      role={toast.kind === 'error' ? 'alert' : 'status'}
      className={`pointer-events-auto flex items-start gap-3 max-w-sm w-full px-4 py-3 rounded-xl border ${style.border} bg-surface shadow-lg shadow-black/40 fade-in`}
    >
      <span
        aria-hidden="true"
        className={`flex-shrink-0 w-5 h-5 rounded-full ${style.iconBg} ${style.icon} flex items-center justify-center text-xs font-bold`}
      >
        {style.glyph}
      </span>
      <p className="text-sm text-text flex-1">{toast.message}</p>
      <button
        onClick={() => onDismiss(toast.id)}
        aria-label={t('toast.dismiss')}
        className="flex-shrink-0 text-text-muted hover:text-text text-sm px-1"
      >
        {'\u00d7'}
      </button>
    </div>
  );
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const timers = useRef(new Map());

  const dismiss = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
  }, []);

  const pushToast = useCallback((kind, message, opts = {}) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    setToasts(prev => [...prev.slice(-3), { id, kind, message }]);
    const timeoutMs = opts.timeout ?? 4000;
    const timer = setTimeout(() => dismiss(id), timeoutMs);
    timers.current.set(id, timer);
    return id;
  }, [dismiss]);

  const value = useMemo(
    () => ({
      toast: pushToast,
      success: msg => pushToast('success', msg),
      info: msg => pushToast('info', msg),
      error: msg => pushToast('error', msg),
    }),
    [pushToast],
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 items-end pointer-events-none">
        {toasts.map(t => (
          <ToastItem key={t.id} toast={t} onDismiss={dismiss} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within a ToastProvider');
  return ctx;
}