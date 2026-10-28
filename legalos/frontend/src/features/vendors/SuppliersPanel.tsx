import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { RefreshCw, Users } from 'lucide-react';
import { toast } from 'sonner';
import { toFriendlyError } from '@/api/client';
import { Button, ErrorState, Skeleton } from '@/ui/primitives';
import { SidePanel, closeSidePanel } from '@/ui/sidepanel';
import { cn } from '@/lib/utils';
import { useRecheckAll, useVendors, type VendorBrief } from './api';
import { VendorRiskBadge, ago } from './components';

const FILTERS = [
  { value: 'all', label: 'All', test: () => true },
  { value: 'attention', label: 'Needs attention', test: (v: VendorBrief) => v.risk_level === 'high' || v.risk_level === 'medium' },
  { value: 'safe', label: 'Safe', test: (v: VendorBrief) => v.risk_level === 'low' },
  { value: 'unverified', label: 'Not verified', test: (v: VendorBrief) => v.risk_level === 'unverified' },
] as const;

type FilterValue = (typeof FILTERS)[number]['value'];

const SupplierRow: React.FC<{ v: VendorBrief; active: boolean }> = ({ v, active }) => (
  <Link to={`/vendors/${v.id}`} aria-current={active ? 'page' : undefined}
    onClick={() => { if (window.matchMedia('(max-width: 767px)').matches) closeSidePanel('vendors-saved'); }}
    className={cn('flex items-start justify-between gap-2 rounded-xl px-2.5 py-2 hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary', active && 'bg-surface-2')}>
    <span className="min-w-0">
      <span className="block truncate text-[13.5px] font-medium text-ink">{v.name}</span>
      <span className="block truncate font-mono text-xs text-ink-2">{v.gstin ?? v.pan ?? v.udyam_number ?? 'No number saved'}</span>
      <span className="block text-xs text-ink-3">{v.last_checked_at ? `Checked ${ago(v.last_checked_at)}` : 'Not checked'}</span>
    </span>
    <span className="mt-0.5 shrink-0"><VendorRiskBadge risk={v.risk_level} short /></span>
  </Link>
);

/** The saved suppliers, tucked into the right-hand panel. Shared by the check desk and the supplier page. */
export const SuppliersPanel: React.FC<{ activeId?: string }> = ({ activeId }) => {
  const vendors = useVendors();
  const recheckAll = useRecheckAll();
  const [filter, setFilter] = useState<FilterValue>('all');
  const data = vendors.data ?? [];
  const list = useMemo(() => {
    const f = FILTERS.find((x) => x.value === filter) ?? FILTERS[0];
    return data.filter(f.test);
  }, [data, filter]);

  const runRecheckAll = () => recheckAll.mutate(undefined, {
    onSuccess: (r) => {
      const bits = [
        `${r.rechecked} of ${r.total} re-checked`,
        r.live_lookups ? `${r.live_lookups} live` : null,
        r.from_cache ? `${r.from_cache} from cache` : null,
        r.failed ? `${r.failed} could not be reached (earlier verdict kept)` : null,
        r.deferred ? `${r.deferred} left for next time (limit ${r.max_live_per_run} live lookups per run)` : null,
      ].filter(Boolean).join(' · ');
      const changed = r.changed.length ? `Changed: ${r.changed.map((c) => `${c.name} (${c.previous} to ${c.current})`).join('; ')}` : 'No verdict changed.';
      toast.success(bits, { description: changed, duration: 8000 });
    },
    onError: (e) => toast.error(toFriendlyError(e).message),
  });

  return (
    <SidePanel storageKey="vendors-saved" title="Your suppliers" icon={Users} count={vendors.data?.length}>
      {vendors.isLoading && <div className="space-y-2 pt-1">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-14" />)}</div>}
      {vendors.isError && <ErrorState message={toFriendlyError(vendors.error).message} onRetry={() => vendors.refetch()} />}
      {vendors.data && vendors.data.length === 0 && (
        <p className="px-2 pt-1 text-sm text-ink-2">No saved suppliers yet. After a check, choose Save supplier. It is kept here with its verdict, and linked to any contract or notice that mentions it.</p>
      )}
      {vendors.data && vendors.data.length > 0 && (
        <>
          <div className="mb-3 px-1">
            <Button size="sm" variant="secondary" className="w-full" loading={recheckAll.isPending} onClick={runRecheckAll} icon={<RefreshCw className="h-4 w-4" aria-hidden />}>Re-check all</Button>
            <p className="mt-1.5 text-xs text-ink-3">Answers fetched in the last 24 hours are reused, so this does not pay for the same lookup twice.</p>
          </div>
          <div className="mb-2 flex flex-wrap gap-1.5 px-1" role="group" aria-label="Filter suppliers">
            {FILTERS.map((f) => (
              <button key={f.value} type="button" onClick={() => setFilter(f.value)} aria-pressed={filter === f.value}
                className={cn('rounded-full border border-line-strong px-2.5 py-1 text-xs font-medium transition-colors', filter === f.value ? 'border-primary bg-primary text-primary-on' : 'bg-surface text-ink-2 hover:bg-surface-2')}>
                {f.label}<span className={cn('ml-1', filter === f.value ? 'opacity-70' : 'text-ink-3')}>{data.filter(f.test).length}</span>
              </button>
            ))}
          </div>
          {list.length === 0
            ? <p className="px-2 pt-2 text-sm text-ink-2">Nothing in this group. Try another filter.</p>
            : <ul className="space-y-0.5">{list.map((v) => <li key={v.id}><SupplierRow v={v} active={v.id === activeId} /></li>)}</ul>}
        </>
      )}
    </SidePanel>
  );
};
