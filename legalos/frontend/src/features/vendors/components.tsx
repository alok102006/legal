import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, Bell, CheckCircle2, Circle, FileText, HelpCircle, PlugZap, ShieldAlert, ShieldCheck, ShieldQuestion, WifiOff, XCircle } from 'lucide-react';
import { Badge, Button } from '@/ui/primitives';
import { RiskLevelBadge } from '@/ui/risk';
import { cn, formatDate, formatDateTime } from '@/lib/utils';
import type { CheckResult, CheckStatus, IdKind, LinkedContract, LinkedNotice, RegistryInfo, RegistryMode, RegistrySource, VendorCheckItem, VendorDetail, VendorRisk } from './api';
import { kindLabel, type Parsed, type SegStatus } from './identifiers';

/* ------------------------------------------------------------------ verdicts */

type Tone = 'critical' | 'warn' | 'good' | 'neutral';

const RISK: Record<VendorRisk, { label: string; short: string; tone: Tone; Icon: React.ElementType; ink: string; panel: string; blurb: string }> = {
  high: { label: 'Do not pay', short: 'Do not pay', tone: 'critical', Icon: ShieldAlert, ink: 'text-critical-ink', panel: 'border-critical/40 bg-critical-soft', blurb: 'Something serious is wrong. Do not pay until the supplier explains it.' },
  medium: { label: 'Check before paying', short: 'Check first', tone: 'warn', Icon: AlertTriangle, ink: 'text-warn-ink', panel: 'border-warn/50 bg-warn-soft', blurb: 'Nothing fatal, but a few things do not add up. Confirm them before you pay.' },
  low: { label: 'Safe to proceed', short: 'Safe', tone: 'good', Icon: ShieldCheck, ink: 'text-good-ink', panel: 'border-good/40 bg-good-soft', blurb: 'Every check we could run passed, including the live registry.' },
  unverified: { label: 'Looks valid, not verified live', short: 'Not verified', tone: 'neutral', Icon: ShieldQuestion, ink: 'text-ink-2', panel: 'border-line-strong bg-surface-2', blurb: 'The number is well-formed, but we could not confirm it with the GST registry.' },
};

export const riskTone = (r: VendorRisk) => RISK[r];

export const VendorRiskBadge: React.FC<{ risk: VendorRisk; short?: boolean }> = ({ risk, short }) => {
  const r = RISK[risk];
  return <Badge tone={r.tone} icon={<r.Icon className="h-3.5 w-3.5" aria-hidden />}>{short ? r.short : r.label}</Badge>;
};

/** "3 days ago" */
export function ago(value: string | null | undefined): string {
  if (!value) return '';
  const secs = (Date.now() - new Date(value).getTime()) / 1000;
  if (!Number.isFinite(secs)) return '';
  const unit = (n: number, w: string) => `${n} ${w}${n === 1 ? '' : 's'} ago`;
  if (secs < 60) return 'just now';
  if (secs < 3600) return unit(Math.floor(secs / 60), 'minute');
  if (secs < 86400) return unit(Math.floor(secs / 3600), 'hour');
  if (secs < 86400 * 30) return unit(Math.floor(secs / 86400), 'day');
  return formatDate(value);
}

const PROVIDER_LABEL: Record<string, string> = { sandbox: 'Sandbox.co.in', generic: 'GST API', sample: 'sample data' };

/* ------------------------------------------------------------------ the number, character by character */

const CELL: Record<SegStatus, string> = {
  ok: 'border-good bg-good-soft text-good-ink',
  bad: 'border-critical bg-critical-soft text-critical-ink',
  partial: 'border-primary/60 bg-primary-soft text-primary-ink',
  empty: 'border-dashed border-line-strong text-ink-3',
};

export const IdentifierStrip: React.FC<{ parsed: Parsed }> = ({ parsed }) => {
  const { segs } = parsed;
  if (!parsed.kind || segs.length === 0) return null;
  const firstEmpty = segs.findIndex((s) => s.status === 'empty');
  const rows = segs.filter((s, i) => s.status !== 'empty' || i === firstEmpty);
  return (
    <div className="mt-5" aria-live="polite">
      <div className="flex w-full items-center justify-center" aria-hidden>
        {segs.map((s, si) => (
          <div key={s.id} className={cn('flex min-w-0 gap-[3px]', si > 0 && 'ml-2 sm:ml-3')}>
            {Array.from({ length: s.size }).map((_, i) => (
              <span key={i} className={cn('flex h-9 w-[1.35rem] items-center justify-center rounded-md border font-mono text-sm font-semibold transition-colors duration-150 sm:h-11 sm:w-8 sm:text-lg', CELL[s.text[i] ? s.status : 'empty'])}>
                {s.text[i] ?? '·'}
              </span>
            ))}
          </div>
        ))}
      </div>
      <ul className="mx-auto mt-4 max-w-md space-y-1.5 text-sm">
        {rows.map((s) => (
          <li key={s.id} className={cn('flex items-start gap-2', s.status === 'ok' ? 'text-good-ink' : s.status === 'bad' ? 'text-critical-ink' : s.status === 'partial' ? 'text-ink' : 'text-ink-3')}>
            {s.status === 'ok' ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden /> : s.status === 'bad' ? <XCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden /> : <Circle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}
            <span>{s.status === 'empty' ? `Next: ${s.hint}` : s.label}</span>
          </li>
        ))}
      </ul>
      {parsed.allOk && <p className="mx-auto mt-3 max-w-md text-sm text-ink-2">{parsed.summary}. Press Enter to check it against the registry.</p>}
    </div>
  );
};

/* ------------------------------------------------------------------ one check line */

const STATUS: Record<CheckStatus, { Icon: React.ElementType; ink: string; word: string }> = {
  pass: { Icon: CheckCircle2, ink: 'text-good-ink', word: 'Passed' },
  warn: { Icon: AlertTriangle, ink: 'text-warn-ink', word: 'Warning' },
  fail: { Icon: XCircle, ink: 'text-critical-ink', word: 'Problem' },
  unknown: { Icon: HelpCircle, ink: 'text-ink-3', word: 'Not checked' },
};

export const CheckRows: React.FC<{ checks: VendorCheckItem[] }> = ({ checks }) => (
  <ul className="divide-y divide-line">
    {checks.map((c) => {
      const s = STATUS[c.status];
      return (
        <li key={c.key + c.label} className="flex gap-3 py-3">
          <s.Icon className={cn('mt-0.5 h-5 w-5 shrink-0', s.ink)} aria-hidden />
          <div className="min-w-0">
            <p className="text-sm font-semibold text-ink">{c.label} <span className={cn('ml-1 text-xs font-medium', s.ink)}>{s.word}</span></p>
            <p className="text-sm text-ink-2">{c.detail}</p>
          </div>
        </li>
      );
    })}
  </ul>
);

/** Kept for other screens that list checks in a bordered box. */
export const CheckList: React.FC<{ checks: VendorCheckItem[] }> = ({ checks }) => (
  <div className="rounded-xl border border-line bg-surface px-3.5"><CheckRows checks={checks} /></div>
);

/* ------------------------------------------------------------------ the verification card */

export interface CheckView {
  kind: IdKind;
  identifier: string;
  name: string | null;
  state_name: string | null;
  risk_level: VendorRisk;
  summary: string;
  reasons: string[];
  checks: VendorCheckItem[];
  registry: RegistryInfo | null;
  registry_source: RegistrySource | null;
  registry_mode: RegistryMode;
  registry_provider: string | null;
  contracts: LinkedContract[];
  notices: LinkedNotice[];
  checked_at: string | null;
}

export const viewFromResult = (r: CheckResult): CheckView => ({
  kind: r.kind, identifier: r.identifier, name: r.suggested_name ?? r.saved_vendor?.name ?? null, state_name: r.state_name,
  risk_level: r.risk_level, summary: r.summary, reasons: r.reasons, checks: r.checks, registry: r.registry, registry_source: r.registry_source,
  registry_mode: r.registry_mode, registry_provider: r.registry_provider, contracts: r.contracts, notices: r.notices, checked_at: r.checked_at,
});

export const viewFromVendor = (v: VendorDetail): CheckView => ({
  kind: v.kind, identifier: v.gstin ?? v.pan ?? v.udyam_number ?? '', name: v.name, state_name: v.state_name,
  risk_level: v.risk_level, summary: v.summary ?? '', reasons: v.reasons, checks: v.checks, registry: v.registry, registry_source: v.registry_source,
  registry_mode: v.registry_mode, registry_provider: v.registry_provider, contracts: v.contracts, notices: v.notices, checked_at: v.last_checked_at,
});

const IDENTITY_KEYS = ['gstin', 'pan', 'entity', 'state', 'udyam'];

function useStagedReveal(total: number, runKey: string, animate: boolean): number {
  const reduce = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  const [n, setN] = useState(animate && !reduce ? 1 : total);
  useEffect(() => {
    if (!animate || reduce) { setN(total); return; }
    setN(1);
    let i = 1;
    const t = window.setInterval(() => { i += 1; setN(i); if (i >= total) window.clearInterval(t); }, 280);
    return () => window.clearInterval(t);
  }, [total, runKey, animate, reduce]);
  return n;
}

const Stage: React.FC<{ n: number; title: string; children: React.ReactNode; aside?: React.ReactNode }> = ({ n, title, children, aside }) => {
  const [shown, setShown] = useState(false);
  useEffect(() => { const id = requestAnimationFrame(() => setShown(true)); return () => cancelAnimationFrame(id); }, []);
  return (
    <section aria-label={title} className={cn('border-t border-line px-4 py-5 transition-all duration-300 motion-reduce:transition-none sm:px-6', shown ? 'translate-y-0 opacity-100' : 'translate-y-1 opacity-0')}>
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-ink">
          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-surface-2 text-[11px] font-semibold text-ink-2" aria-hidden>{n}</span>{title}
        </h3>
        {aside}
      </div>
      {children}
    </section>
  );
};

const Fact: React.FC<{ label: string; children: React.ReactNode; mono?: boolean }> = ({ label, children, mono }) => (
  <div className="min-w-0"><dt className="text-xs text-ink-3">{label}</dt><dd className={cn('truncate text-sm font-medium text-ink', mono && 'font-mono')}>{children}</dd></div>
);

const StatusPill: React.FC<{ status: string }> = ({ status }) => {
  const s = status.toLowerCase();
  if (s === 'active') return <Badge tone="good" icon={<CheckCircle2 className="h-3.5 w-3.5" aria-hidden />}>Active</Badge>;
  if (['cancelled', 'suspended', 'inactive'].includes(s)) return <Badge tone="critical" icon={<XCircle className="h-3.5 w-3.5" aria-hidden />}>{status}</Badge>;
  return <Badge>{status}</Badge>;
};

const RegistrySection: React.FC<{ view: CheckView; onRetry?: () => void; retrying?: boolean }> = ({ view, onRetry, retrying }) => {
  const reg = view.registry;
  const regChecks = view.checks.filter((c) => !IDENTITY_KEYS.includes(c.key));
  const src = view.registry_source;

  if ((src === 'live' || src === 'sample') && reg) {
    const rows = regChecks.filter((c) => !(c.key === 'registry' && c.status === 'pass'));
    return (
      <>
        {src === 'sample' && <p className="mb-3 rounded-lg bg-primary-soft px-3 py-2 text-sm text-primary-ink">Sample record (demo data). This is not a live registry answer.</p>}
        <dl className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3">
          {reg.legal_name && <Fact label="Legal name">{reg.legal_name}</Fact>}
          {reg.trade_name && <Fact label="Trade name">{reg.trade_name}</Fact>}
          {reg.status && <div><dt className="text-xs text-ink-3">Status</dt><dd className="mt-0.5"><StatusPill status={reg.status} /></dd></div>}
          {reg.registration_date && <Fact label="Registered on">{formatDate(reg.registration_date)}</Fact>}
          {reg.cancellation_date && <Fact label="Cancelled on">{formatDate(reg.cancellation_date)}</Fact>}
          {reg.constitution && <Fact label="Constitution">{reg.constitution}</Fact>}
          {reg.taxpayer_type && <Fact label="Taxpayer type">{reg.taxpayer_type}</Fact>}
          {reg.filing_status && <Fact label="Return filing">{reg.filing_status}</Fact>}
          {reg.state && <Fact label="State">{reg.state}</Fact>}
        </dl>
        {rows.length > 0 && <div className="mt-2"><CheckRows checks={rows} /></div>}
      </>
    );
  }

  const kind = reg?.error_kind;
  if (kind === 'auth' || kind === 'quota' || kind === 'unavailable') {
    return (
      <div role="alert" className="flex gap-3 rounded-xl border border-critical/40 bg-critical-soft p-4">
        <PlugZap className="mt-0.5 h-5 w-5 shrink-0 text-critical-ink" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-critical-ink">Registry lookup failed</p>
          <p className="mt-0.5 text-sm text-ink-2">{reg?.message?.replace(/^Registry lookup failed:\s*/, '') ?? 'The GST registry could not be reached.'} The offline checks above still stand. We have not assumed anything about the registration.</p>
          {onRetry && <Button className="mt-3" size="sm" variant="secondary" loading={retrying} onClick={onRetry}>Try the registry again</Button>}
        </div>
      </div>
    );
  }
  if (kind === 'not_found') {
    return (
      <div className="flex gap-3 rounded-xl border border-warn/50 bg-warn-soft p-4">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-warn-ink" aria-hidden />
        <div><p className="font-semibold text-warn-ink">No record in the GST registry</p>
          <p className="mt-0.5 text-sm text-ink-2">The number is well-formed, but the registry has no registration under it. Ask the supplier for their registration certificate before paying.</p></div>
      </div>
    );
  }
  const text = kind === 'no_gstin'
    ? `The GST registry is searched by GSTIN. This ${kindLabel(view.kind)} was checked for format only. Ask the supplier for their GSTIN to confirm GST registration.`
    : kind === 'invalid_gstin'
      ? 'Skipped, because the GSTIN did not pass the format check.'
      : 'Offline checks only. We cannot tell you whether this registration is active, cancelled or filing returns.';
  return (
    <div className="flex gap-3 rounded-xl border border-line bg-surface-2 p-4">
      <WifiOff className="mt-0.5 h-5 w-5 shrink-0 text-ink-3" aria-hidden />
      <div><p className="font-semibold text-ink">{kind === 'invalid_gstin' ? 'Registry not asked' : 'Live registry not connected - offline checks only'}</p>
        <p className="mt-0.5 text-sm text-ink-2">{text}</p></div>
    </div>
  );
};

const RELATED_ROW = 'flex items-center gap-2.5 rounded-lg px-2 py-2 text-sm hover:bg-surface-2';

const LinkedSection: React.FC<{ view: CheckView }> = ({ view }) => {
  if (view.contracts.length === 0 && view.notices.length === 0) {
    return <p className="text-sm text-ink-2">No contract or notice in your workspace mentions this supplier yet.</p>;
  }
  return (
    <ul className="-mx-2 space-y-0.5">
      {view.contracts.map((c) => (
        <li key={c.id}><Link to={`/contracts/${c.id}`} className={RELATED_ROW}>
          <FileText className="h-4 w-4 shrink-0 text-ink-3" aria-hidden /><span className="min-w-0 flex-1 truncate font-medium text-ink">{c.title ?? 'Contract'}</span>
          {c.status === 'analyzed' && <RiskLevelBadge level={c.risk_level as 'low' | 'medium' | 'high' | null} score={c.overall_score} />}
        </Link></li>
      ))}
      {view.notices.map((n) => (
        <li key={n.id}><Link to={`/notices/${n.id}`} className={RELATED_ROW}>
          <Bell className="h-4 w-4 shrink-0 text-ink-3" aria-hidden /><span className="min-w-0 flex-1 truncate font-medium text-ink">{n.title ?? 'Notice'}</span>
          <span className="shrink-0 text-xs text-ink-3">{n.response_deadline ? `Reply by ${formatDate(n.response_deadline)}` : 'Notice'}</span>
        </Link></li>
      ))}
    </ul>
  );
};

export const ModeChip: React.FC<{ mode: RegistryMode; provider: string | null }> = ({ mode, provider }) =>
  mode === 'live' ? <Badge tone="good" icon={<PlugZap className="h-3.5 w-3.5" aria-hidden />}>Live registry: {PROVIDER_LABEL[provider ?? ''] ?? provider ?? 'connected'}</Badge>
    : mode === 'sample' ? <Badge tone="info">Sample registry (demo)</Badge>
      : <Badge icon={<WifiOff className="h-3.5 w-3.5" aria-hidden />}>Offline checks only</Badge>;

export const VerificationCard: React.FC<{
  view: CheckView; animate?: boolean; actions?: React.ReactNode; onRetryRegistry?: () => void; retrying?: boolean; footer?: React.ReactNode;
}> = ({ view, animate = true, actions, onRetryRegistry, retrying, footer }) => {
  const stages = 4;
  const shown = useStagedReveal(stages, `${view.identifier}|${view.checked_at}`, animate);
  const R = RISK[view.risk_level];
  const identity = view.checks.filter((c) => IDENTITY_KEYS.includes(c.key));
  const reasons = view.reasons.length > 0 ? view.reasons : view.summary ? [view.summary] : [];

  return (
    <article className="overflow-hidden rounded-2xl border border-line bg-surface shadow-card" aria-label="Verification result">
      <header className="flex flex-wrap items-start justify-between gap-3 px-4 py-5 sm:px-6">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wide text-ink-3">{kindLabel(view.kind)}</p>
          <p className="break-all font-mono text-xl font-semibold tracking-wide text-ink sm:text-2xl">{view.identifier || '-'}</p>
          {(view.name || view.state_name) && <p className="mt-1 text-sm text-ink-2">{[view.name, view.state_name].filter(Boolean).join(' - ')}</p>}
        </div>
        <ModeChip mode={view.registry_mode} provider={view.registry_provider} />
      </header>

      <Stage n={1} title="Identity">
        {identity.length > 0 ? <CheckRows checks={identity} /> : <p className="text-sm text-ink-2">No offline checks apply.</p>}
      </Stage>

      {shown >= 2 && (
        <Stage n={2} title="Registry" aside={view.registry_mode === 'live' && view.registry_source === 'live' ? <span className="text-xs text-ink-3">Live answer</span> : undefined}>
          <RegistrySection view={view} onRetry={onRetryRegistry} retrying={retrying} />
        </Stage>
      )}

      {shown >= 3 && (
        <Stage n={3} title="Verdict">
          <div className={cn('rounded-xl border p-4', R.panel)} role="status">
            <div className="flex items-center gap-2.5">
              <R.Icon className={cn('h-6 w-6 shrink-0', R.ink)} aria-hidden />
              <p className={cn('text-lg font-semibold sm:text-xl', R.ink)}>{R.label}</p>
            </div>
            <p className="mt-1 text-sm text-ink-2">{R.blurb}</p>
            {reasons.length > 0 && (
              <ul className="mt-3 space-y-1.5 text-sm text-ink">
                {reasons.map((r, i) => <li key={i} className="flex gap-2"><span className={cn('mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-current', R.ink)} aria-hidden /><span>{r}</span></li>)}
              </ul>
            )}
          </div>
          <p className="mt-2 text-xs text-ink-3">Decision support from the checks above, not legal advice.</p>
        </Stage>
      )}

      {shown >= 4 && (
        <Stage n={4} title="Linked records">
          <LinkedSection view={view} />
        </Stage>
      )}

      {(actions || view.checked_at) && shown >= stages && (
        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-line bg-surface-2 px-4 py-3.5 sm:px-6">
          <p className="text-xs text-ink-3">{view.checked_at ? `Checked ${ago(view.checked_at)} (${formatDateTime(view.checked_at)})` : ''}</p>
          <div className="flex flex-wrap items-center gap-2">{actions}</div>
        </footer>
      )}
      {footer}
    </article>
  );
};
