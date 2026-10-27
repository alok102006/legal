/** Shared building blocks that give every workspace the same structure:
 *  intro (what it does, in 3 steps) · list toolbar (search, filters, "New") · first-run panel with a sample. */
import React, { useEffect, useState } from 'react';
import { Search, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button, Card, Input, Select } from './primitives';
import { Modal } from './overlays';

export const HowItWorks: React.FC<{ steps: [string, string][]; className?: string }> = ({ steps, className }) => (
  <ol className={cn('grid gap-3 sm:grid-cols-3', className)}>
    {steps.map(([title, body], i) => (
      <li key={title} className="flex gap-3 rounded-xl border border-line bg-surface p-4">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary-soft text-sm font-bold text-primary-ink" aria-hidden>{i + 1}</span>
        <span><span className="block text-sm font-semibold text-ink">{title}</span><span className="block text-sm text-ink-2">{body}</span></span>
      </li>
    ))}
  </ol>
);

export const FirstRun: React.FC<{
  icon: React.ReactNode; title: string; description: string; steps: [string, string][];
  primary: React.ReactNode; onSample?: () => void; sampleLabel?: string; sampleLoading?: boolean;
}> = ({ icon, title, description, steps, primary, onSample, sampleLabel, sampleLoading }) => (
  <Card className="p-6 sm:p-8">
    <div className="flex flex-col items-start gap-5 sm:flex-row">
      <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-primary-ink" aria-hidden>{icon}</span>
      <div className="min-w-0 flex-1">
        <h2 className="text-xl font-semibold text-ink">{title}</h2>
        <p className="mt-1 max-w-2xl text-sm text-ink-2">{description}</p>
        <div className="mt-4 flex flex-wrap gap-2">
          {primary}
          {onSample && <Button variant="secondary" size="lg" onClick={onSample} loading={sampleLoading} icon={<Sparkles className="h-4 w-4" aria-hidden />}>{sampleLabel ?? 'Try with a sample'}</Button>}
        </div>
      </div>
    </div>
    <HowItWorks steps={steps} className="mt-6" />
  </Card>
);

export interface ToolbarFilter { value: string; label: string; count?: number }

export const ListToolbar: React.FC<{
  search: string; onSearch: (v: string) => void; placeholder?: string;
  filters?: ToolbarFilter[]; filter?: string; onFilter?: (v: string) => void;
  sort?: { value: string; options: { value: string; label: string }[]; onChange: (v: string) => void };
  action?: React.ReactNode; count?: number;
}> = ({ search, onSearch, placeholder = 'Search…', filters, filter, onFilter, sort, action, count }) => (
  <div className="mb-4 flex flex-col gap-3">
    <div className="flex flex-wrap items-center gap-2">
      <div className="relative min-w-[200px] flex-1">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3" aria-hidden />
        <Input value={search} onChange={(e) => onSearch(e.target.value)} placeholder={placeholder} className="pl-9" aria-label={placeholder} />
      </div>
      {sort && (
        <Select value={sort.value} onChange={(e) => sort.onChange(e.target.value)} aria-label="Sort" className="w-auto">
          {sort.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </Select>
      )}
      {action}
    </div>
    {filters && filters.length > 0 && (
      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filter">
        {filters.map((f) => (
          <button key={f.value} onClick={() => onFilter?.(f.value)} aria-pressed={filter === f.value}
            className={cn('min-h-[36px] rounded-full border px-3 py-1 text-sm font-medium transition-colors', filter === f.value ? 'border-primary bg-primary-soft text-primary-ink' : 'border-line-strong text-ink-2 hover:bg-surface-2')}>
            {f.label}{f.count !== undefined && <span className="ml-1 text-ink-3">{f.count}</span>}
          </button>
        ))}
        {count !== undefined && <span className="ml-auto text-xs text-ink-3">{count} shown</span>}
      </div>
    )}
  </div>
);

/** Opens a dialog when the URL has ?new=1 (used by the command palette and dashboard quick actions). */
export function useNewParam(param = 'new'): [boolean, (o: boolean) => void] {
  const [open, setOpen] = useState(() => new URLSearchParams(window.location.search).get(param) === '1');
  useEffect(() => {
    if (new URLSearchParams(window.location.search).get(param) === '1') {
      const url = new URL(window.location.href); url.searchParams.delete(param);
      window.history.replaceState({}, '', url.toString());
    }
  }, [param]);
  return [open, setOpen];
}

export const NewDialog: React.FC<{ open: boolean; onOpenChange: (o: boolean) => void; title: string; description?: string; children: React.ReactNode }> = (p) => (
  <Modal open={p.open} onOpenChange={p.onOpenChange} title={p.title} description={p.description}>{p.children}</Modal>
);
