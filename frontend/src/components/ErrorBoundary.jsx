import { Component } from 'react';

/**
 * Last line of defense against a render-time crash. Without this, any
 * unexpected component error blanks the entire app. The fallback keeps the
 * user oriented and offers a safe reload.
 */
export default class ErrorBoundary extends Component {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    // Keep diagnostics in the browser console; wire this to an error tracker
    // (Sentry, etc.) when one is configured.
    console.error('Unhandled UI error:', error, info?.componentStack);
  }

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <div className="min-h-screen bg-bg text-text flex items-center justify-center p-6">
        <div className="max-w-md text-center">
          <p className="text-xs uppercase tracking-[0.16em] text-text-muted mb-3">Something went wrong</p>
          <h1 className="text-2xl font-bold mb-3" style={{ fontFamily: 'Sora, sans-serif' }}>
            This page hit an unexpected error
          </h1>
          <p className="text-sm text-text-secondary mb-6">
            Your data is safe. Reload the page to keep browsing.
          </p>
          <button className="btn-primary" onClick={() => window.location.reload()}>
            Reload BingeFinder
          </button>
        </div>
      </div>
    );
  }
}
