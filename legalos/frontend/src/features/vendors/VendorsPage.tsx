import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ArrowRight, BadgeCheck, CircleCheckBig, CornerDownLeft, Landmark, RefreshCw, Search, ShieldCheck, X } from 'lucide-react';
import { toast } from 'sonner';
import { toFriendlyError } from '@/api/client';
import { Button, ErrorState, Input, Skeleton } from '@/ui/primitives';
import { cn, timeAgo } from '@/lib/utils';
import { useCheckIdentifier, useCreateVendor, useVendors, type CheckResult } from './api';
import { IdentifierStrip, VerificationCard, viewFromResult } from './components';
import { clean, parseIdentifier } from './identifiers';
import { SuppliersPanel } from './SuppliersPanel';

/* ------------------------------------------------------------------ save from the desk */

const SaveSupplier: React.FC<{ result: CheckResult; fallbackName: string; savedId: string | null; onSaved: (id: string) => void }> = ({ result, fallbackName, savedId, onSaved }) => {
  const create = useCreateVendor();
  const known = result.suggested_name ?? result.saved_vendor?.name ?? (fallbackName || null);
  const [asking, setAsking] = useState(false);
  const [name, setName] = useState(known ?? '');
  const id = savedId ?? result.saved_vendor?.id ?? null;

  if (id) {
    return <Link to={`/vendors/${id}`} className="inline-flex h-9 items-center gap-1.5 rounded-lg px-3 text-sm font-medium text-primary-ink hover:bg-primary-soft"><BadgeCheck className="h-4 w-4" aria-hidden />Saved - open supplier<ArrowRight className="h-4 w-4" aria-hidden /></Link>;
  }
  const save = (n: string) => {
    const payload = result.kind === 'gstin' ? { name: n, gstin: result.identifier } : result.kind === 'pan' ? { name: n, pan: result.identifier } : { name: n, udyam_number: result.identifier };
    create.mutate(payload, { onSuccess: (v) => { onSaved(v.id); toast.success('Supplier saved'); }, onError: (e) => toast.error(toFriendlyError(e).message) });
  };
  if (asking) {
    return (
      <form className="flex flex-wrap items-center gap-2" onSubmit={(e) => { e.preventDefault(); if (name.trim().length >= 2) save(name.trim()); }}>
        <Input autoFocus aria-label="Supplier name" className="h-9 w-56" placeholder="Name as on the invoice" value={name} onChange={(e) => setName(e.target.value)} />
        <Button size="sm" type="submit" loading={create.isPending} disabled={name.trim().length < 2}>Save</Button>
        <Button size="sm" variant="ghost" onClick={() => setAsking(false)}>Cancel</Button>
      </form>
    );
  }
  return <Button size="sm" loading={create.isPending} onClick={() => (known ? save(known) : setAsking(true))}>Save supplier</Button>;
};

/* ------------------------------------------------------------------ page */

export const VendorsPage: React.FC = () => {
  const [params, setParams] = useSearchParams();
  const nameParam = params.get('name') ?? '';
  const inputRef = useRef<HTMLInputElement>(null);
  const [raw, setRaw] = useState('');
  const [savedId, setSavedId] = useState<string | null>(null);
  const parsed = useMemo(() => parseIdentifier(raw), [raw]);
  const check = useCheckIdentifier();
  const hasResult = check.isPending || check.isError || !!check.data;

  // ?new=1 (Home, command palette) puts the cursor straight in the box
  useEffect(() => {
    if (params.get('new') === '1') {
      inputRef.current?.focus();
      const next = new URLSearchParams(params); next.delete('new');
      setParams(next, { replace: true });
    }
  }, [params, setParams]);
  useEffect(() => { inputRef.current?.focus(); }, []);

  const submit = (value = raw) => {
    const v = clean(value);
    if (!v) { inputRef.current?.focus(); return; }
    setSavedId(null);
    check.mutate({ identifier: v, name: nameParam || undefined });
  };

  return (
    <div className="relative h-full overflow-hidden">
      <SuppliersPanel />
      <div className="h-full overflow-y-auto">
        <div className={cn('mx-auto w-full max-w-5xl px-6 pb-20 transition-[padding] duration-300 sm:px-10', hasResult ? 'pt-16' : 'pt-[10vh]')}>
          <section aria-labelledby="desk-title" className="text-center">
            <h1 id="desk-title" className="font-display text-4xl leading-tight text-ink sm:text-5xl">Check a supplier before you pay</h1>
            <p className="mx-auto mt-3 max-w-md text-sm text-ink-2 sm:text-base">Paste a GSTIN, PAN or Udyam number from the invoice.</p>

            {nameParam && (
              <p className="mx-auto mt-4 inline-flex max-w-full items-center gap-2 rounded-full bg-surface-2 px-3 py-1.5 text-sm text-ink-2">
                <span className="truncate">Checking <strong className="text-ink">{nameParam}</strong>? Paste their GSTIN below.</span>
                <button type="button" aria-label="Dismiss" className="shrink-0 rounded-full p-0.5 hover:bg-surface" onClick={() => { const n = new URLSearchParams(params); n.delete('name'); setParams(n, { replace: true }); }}><X className="h-3.5 w-3.5" aria-hidden /></button>
              </p>
            )}

            <form className="btn-quiet relative mx-auto mt-8 max-w-2xl rounded-2xl border border-line-strong bg-surface transition-shadow focus-within:ring-4 focus-within:ring-primary/15" onSubmit={(e) => { e.preventDefault(); submit(); }} role="search">
              <Search className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-ink-3" aria-hidden />
              <Input ref={inputRef} value={raw} onChange={(e) => setRaw(e.target.value.toUpperCase())} aria-label="GSTIN, PAN or Udyam number"
                placeholder="GSTIN, PAN or Udyam number" autoComplete="off" autoCapitalize="characters" spellCheck={false} maxLength={40}
                className="h-14 rounded-2xl border-0 bg-transparent pl-12 pr-16 font-mono text-lg tracking-wider !shadow-none placeholder:font-sans placeholder:tracking-normal sm:pr-32" />
              <Button type="submit" size="md" loading={check.isPending} disabled={!clean(raw)} aria-label="Check"
                className="absolute right-2 top-1/2 -translate-y-1/2 max-sm:w-10 max-sm:!min-h-0 max-sm:px-0 sm:px-5" icon={<CornerDownLeft className="h-4 w-4 sm:hidden" aria-hidden />}>
                <span className="hidden sm:inline">Check</span>
              </Button>
            </form>

            <IdentifierStrip parsed={parsed} />
          </section>

          {/* result */}
          <div className="mx-auto mt-10 max-w-2xl" aria-live="polite">
            {check.isPending && (
              <div className="space-y-3 rounded-2xl bg-surface-2 p-6" role="status" aria-label="Checking">
                <Skeleton className="h-4 w-24" /><Skeleton className="h-8 w-2/3" /><Skeleton className="h-16 w-full" />
              </div>
            )}
            {check.isError && <ErrorState title="Could not run this check" message={toFriendlyError(check.error).message} onRetry={() => submit()} />}
            {check.data && !check.isPending && (
              <VerificationCard view={viewFromResult(check.data)} onRetryRegistry={() => submit(check.data.identifier)} retrying={check.isPending}
                actions={<>
                  <Button size="sm" variant="secondary" icon={<RefreshCw className="h-4 w-4" aria-hidden />} onClick={() => submit(check.data.identifier)}>Re-check</Button>
                  <SaveSupplier key={check.data.checked_at} result={check.data} fallbackName={nameParam} savedId={savedId} onSaved={setSavedId} />
                </>} />
            )}
          </div>

          {!hasResult && <DeskBelow />}
        </div>
      </div>
    </div>
  );
};

/* What happens when you check, plus the latest saved suppliers, so the page is not empty before the first search. */
const DeskBelow: React.FC = () => {
  const vendors = useVendors();
  const recent = (vendors.data ?? []).slice(0, 4);
  const steps: [React.ElementType, string, string][] = [
    [ShieldCheck, 'Identity', 'The number is checked as you type: state code, PAN, entity type and the check digit. Typos and fake numbers never reach the registry.'],
    [Landmark, 'Registry', 'The GST registry is asked live for the legal name, status and registration date. If it cannot answer, we say so.'],
    [CircleCheckBig, 'Verdict', 'Safe to proceed, check before paying, or do not pay, with the reasons that drove it and any contracts or notices that mention the supplier.'],
  ];
  return (
    <div className="mt-16">
      <p className="text-center text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-2">What happens when you check</p>
      <ul className="mt-5 grid gap-4 md:grid-cols-3">
        {steps.map(([Icon, title, body], i) => (
          <li key={title} className="rounded-2xl bg-surface-2 p-5">
            <div className="flex items-center gap-3">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-surface text-ink-2 shadow-card" aria-hidden><Icon className="h-4 w-4" /></span>
              <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-3">Step {i + 1}</span>
            </div>
            <p className="mt-3 text-[15px] font-semibold text-ink">{title}</p>
            <p className="mt-1 text-sm leading-relaxed text-ink-2">{body}</p>
          </li>
        ))}
      </ul>
      {recent.length > 0 && (
        <div className="mt-12">
          <div className="mb-4 flex items-center justify-between">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-2">Recently checked</p>
            <span className="text-xs text-ink-3">{vendors.data?.length} saved · open the panel for all</span>
          </div>
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {recent.map((v) => (
              <li key={v.id}>
                <Link to={`/vendors/${v.id}`} className="block rounded-2xl bg-surface-2 p-4 transition-colors hover:bg-surface-2/70">
                  <span className="block truncate text-[15px] font-medium text-ink">{v.name}</span>
                  <span className="mt-0.5 block truncate font-mono text-xs text-ink-3">{v.gstin ?? v.pan ?? v.udyam_number ?? 'No number'}</span>
                  <span className="mt-3 block text-xs text-ink-2">{v.last_checked_at ? `Checked ${timeAgo(v.last_checked_at)}` : 'Not checked yet'}</span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};
