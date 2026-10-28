import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

type State = { error: Error | null };

/** Keeps one broken screen from blanking the whole app: shows what went wrong and offers a reload. */
export class ErrorBoundary extends React.Component<{ children: React.ReactNode; resetKey?: string }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State { return { error }; }

  componentDidUpdate(prev: { resetKey?: string }) {
    if (prev.resetKey !== this.props.resetKey && this.state.error) this.setState({ error: null });
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('Screen crashed', error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="mx-auto flex max-w-lg flex-col items-center px-6 py-24 text-center" role="alert">
        <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-critical-soft text-critical-ink" aria-hidden><AlertCircle className="h-5 w-5" /></span>
        <h2 className="mt-4 text-lg font-semibold text-ink">This screen hit a problem</h2>
        <p className="mt-1 text-sm text-ink-2">Your data is safe. Reload the screen; if it keeps happening, tell us what you clicked.</p>
        <p className="mt-3 max-w-full truncate rounded-lg bg-surface-2 px-3 py-1.5 font-mono text-xs text-ink-3">{this.state.error.message}</p>
        <button onClick={() => window.location.reload()} className="btn-raised mt-5 inline-flex h-10 items-center gap-2 rounded-xl bg-primary px-4 text-sm font-medium text-primary-on">
          <RefreshCw className="h-4 w-4" aria-hidden />Reload
        </button>
      </div>
    );
  }
}
