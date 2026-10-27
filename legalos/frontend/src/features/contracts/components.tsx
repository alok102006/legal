import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertOctagon, BookMarked, Check, CheckCircle2, ChevronDown, Copy, CornerDownRight, HelpCircle, Landmark, Send, ShieldAlert, Undo2 } from 'lucide-react';
import { toast } from 'sonner';
import { toFriendlyError } from '@/api/client';
import { useVendorMatch } from '@/features/vendors/api';
import { VendorRiskBadge } from '@/features/vendors/components';
import { Badge, Button, ErrorState, Notice, Spinner, Textarea } from '@/ui/primitives';
import { SeverityBadge, type RiskLevel, type Severity } from '@/ui/risk';
import { cn, formatDate, formatMoney, plural, titleCase } from '@/lib/utils';
import {
  contractTypeLabel, useChat, useSetFindingStatus,
  type ChatCitation, type ContractDetail, type ContractFacts, type Finding,
} from './api';

export const CATEGORY_LABEL: Record<string, string> = {
  liability_indemnity: 'Liability & indemnity',
  termination: 'Termination',
  lock_in_exclusivity: 'Lock-in & exclusivity',
  non_compete: 'Non-compete',
  penalty_damages: 'Penalties & damages',
  payment_terms: 'Payment terms',
  auto_renewal: 'Auto-renewal',
  unilateral_change: 'One-sided changes',
  ip_ownership: 'IP ownership',
  confidentiality: 'Confidentiality',
  dispute_resolution: 'Disputes & jurisdiction',
  force_majeure: 'Force majeure',
  assignment_subcontract: 'Assignment & subcontracting',
  data_protection: 'Data protection',
  stamp_execution: 'Stamp duty & signing',
  other: 'Other',
};

/** Static class names per severity (Tailwind needs to see the full strings). */
export const SEV_STYLE: Record<Severity, { mark: string; bar: string; dot: string }> = {
  critical: { mark: 'bg-critical-soft', bar: 'border-critical', dot: 'bg-critical' },
  high: { mark: 'bg-serious-soft', bar: 'border-serious', dot: 'bg-serious' },
  medium: { mark: 'bg-warn-soft', bar: 'border-warn', dot: 'bg-warn' },
  low: { mark: 'bg-primary-soft', bar: 'border-primary', dot: 'bg-primary' },
};

export const RISK_DOT: Record<RiskLevel, string> = { low: 'bg-good', medium: 'bg-warn', high: 'bg-critical' };

/* ------------------------------------------------------------------ verdict (top of the right rail) */

const LEVEL_UI: Record<RiskLevel, { label: string; fill: string; track: string; ink: string; Icon: React.ElementType }> = {
  low: { label: 'Low risk', fill: 'var(--good)', track: 'var(--good-soft)', ink: 'text-good-ink', Icon: CheckCircle2 },
  medium: { label: 'Medium risk', fill: 'var(--warn)', track: 'var(--warn-soft)', ink: 'text-warn-ink', Icon: ShieldAlert },
  high: { label: 'High risk', fill: 'var(--critical)', track: 'var(--critical-soft)', ink: 'text-critical-ink', Icon: AlertOctagon },
};

export const Verdict: React.FC<{ contract: ContractDetail }> = ({ contract: c }) => {
  const level = (c.risk_level ?? 'low') as RiskLevel;
  const score = c.overall_score ?? 0;
  const l = LEVEL_UI[level];
  const counts = c.finding_counts;
  const parts = ([['critical', counts.critical], ['high', counts.high], ['medium', counts.medium], ['low', counts.low]] as const)
    .filter(([, n]) => n > 0).map(([k, n]) => `${n} ${k}`);
  const drivers = c.score_breakdown?.top_drivers ?? [];
  return (
    <section aria-label="Verdict" className="px-5 pb-4 pt-5">
      <p className="text-xs font-semibold uppercase tracking-wider text-ink-3">Before you sign</p>
      <div className="mt-2 flex items-end justify-between gap-3">
        <div className="flex items-baseline gap-1.5">
          <span className="text-5xl font-bold leading-none tracking-tight text-ink">{score}</span>
          <span className="text-sm text-ink-3">/ 100</span>
        </div>
        <p className={cn('flex items-center gap-1.5 pb-0.5 text-sm font-semibold', l.ink)}>
          <l.Icon className="h-4 w-4" aria-hidden />{l.label}
        </p>
      </div>
      <div role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={score} aria-label={`Risk score ${score} out of 100, ${l.label}`}
        className="mt-3 h-2 w-full overflow-hidden rounded-full" style={{ background: l.track }}>
        <div className="h-full rounded-full transition-all duration-700" style={{ width: `${Math.min(100, score)}%`, background: l.fill }} />
      </div>
      <p className="mt-2 text-[13px] font-medium text-ink-2">{parts.length ? parts.join(' · ') : 'No evidence-backed issues'}</p>
      <p className="text-xs text-ink-3">Counts only findings backed by exact text in the contract or an Indian-law check.</p>
      {drivers.length > 0 && (
        <ul className="mt-3 space-y-1.5 border-t border-line pt-3" aria-label="Biggest risks">
          {drivers.map((d) => (
            <li key={d} className="flex items-start gap-2 text-[13px] text-ink">
              <CornerDownRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ink-3" aria-hidden />
              <span className="min-w-0 truncate" title={d}>{d}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
};

/* ------------------------------------------------------------------ key terms */

export const KeyTerms: React.FC<{ contract: ContractDetail }> = ({ contract: c }) => {
  const facts: ContractFacts | null = c.facts;
  const rows: [string, React.ReactNode][] = [];
  const typeLabel = contractTypeLabel(c.contract_type);
  if (typeLabel) rows.push(['Type', facts?.contract_type_detail ? `${typeLabel} · ${facts.contract_type_detail}` : typeLabel]);
  const parties = facts?.parties ?? [];
  if (parties.length) {
    rows.push(['Parties', (
      <ul className="space-y-1">
        {parties.map((p) => (
          <li key={p.name}>{p.name}<span className="block text-xs font-normal text-ink-3">{p.role}{p.is_our_client ? ' (you)' : ''}</span></li>
        ))}
      </ul>
    )]);
  }
  if (facts) {
    if (facts.contract_value_amount) rows.push(['Value', `${formatMoney(facts.contract_value_amount, facts.contract_value_currency)}${facts.contract_value_basis ? ` (${facts.contract_value_basis})` : ''}`]);
    const dates = [facts.effective_date && `Starts ${formatDate(facts.effective_date)}`, facts.term_description, facts.end_date && `ends ${formatDate(facts.end_date)}`].filter(Boolean).join(' · ');
    if (dates) rows.push(['Term', dates]);
    if (facts.auto_renewal !== null && facts.auto_renewal !== undefined)
      rows.push(['Renewal', facts.auto_renewal ? `Renews automatically${facts.renewal_notice_days ? ` unless you give ${plural(facts.renewal_notice_days, 'day')}' notice` : ''}` : 'Does not renew automatically']);
    const pay = [facts.payment_days !== null && facts.payment_days !== undefined && `Due in ${plural(facts.payment_days, 'day')}`, facts.payment_terms_text].filter(Boolean).join(' · ');
    if (pay) rows.push(['Payment', pay]);
    if (facts.late_payment_interest) rows.push(['Late payment', facts.late_payment_interest]);
    const term = [facts.termination_terms,
      facts.termination_notice_days_client != null && `You can leave with ${plural(facts.termination_notice_days_client, 'day')}' notice`,
      facts.termination_notice_days_other != null && `They can leave with ${plural(facts.termination_notice_days_other, 'day')}' notice`].filter(Boolean).join(' ');
    if (term) rows.push(['Ending it', term]);
    if (facts.liability_cap_present !== null && facts.liability_cap_present !== undefined)
      rows.push(['Liability cap', facts.liability_cap_present ? (facts.liability_cap_text || 'Yes') : 'No cap, so liability is unlimited']);
    if (facts.governing_law) rows.push(['Governing law', facts.governing_law]);
    if (facts.jurisdiction || facts.dispute_mechanism)
      rows.push(['Disputes', [facts.dispute_mechanism && titleCase(facts.dispute_mechanism), facts.jurisdiction, facts.arbitration_seat && `seat: ${facts.arbitration_seat}`].filter(Boolean).join(' · ')]);
  }

  return (
    <div className="space-y-5">
      {c.summary_points.length > 0 && (
        <section aria-label="In plain English">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-ink-3">In plain English</h3>
          <ul className="mt-2 space-y-2">
            {c.summary_points.map((p) => (
              <li key={p} className="flex gap-2 text-[13px] leading-snug text-ink"><CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary-ink" aria-hidden />{p}</li>
            ))}
          </ul>
        </section>
      )}
      <section aria-label="Key terms">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-ink-3">Key terms</h3>
        <dl className="mt-2 divide-y divide-line">
          {rows.map(([k, v]) => (
            <div key={k} className="grid grid-cols-[6.5rem_1fr] gap-3 py-2.5 text-[13px]">
              <dt className="text-ink-3">{k}</dt>
              <dd className="min-w-0 font-medium text-ink">{v}</dd>
            </div>
          ))}
        </dl>
        {rows.length === 0 && <p className="mt-2 text-sm text-ink-2">No key terms could be read from this document.</p>}
      </section>
      {facts?.key_dates && facts.key_dates.length > 0 && (
        <section aria-label="Dates to remember">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-ink-3">Dates to remember</h3>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-[13px] text-ink">{facts.key_dates.map((d) => <li key={d}>{d}</li>)}</ul>
          <p className="mt-2 text-xs text-ink-3">The end date and the last day to stop auto-renewal are added to your Compliance calendar.</p>
        </section>
      )}
    </div>
  );
};

/* ------------------------------------------------------------------ counterparty / supplier link */

const BUSINESS_TYPES = new Set(['supply', 'service', 'distribution', 'franchise', 'software_license', 'partnership', 'other']);

export const CounterpartyCard: React.FC<{ name: string | null; type: string | null }> = ({ name, type }) => {
  const { data: vendor, isLoading } = useVendorMatch(name);
  if (!name || (type && !BUSINESS_TYPES.has(type))) return null;
  const msme = vendor?.msme_category;
  return (
    <section aria-label="Supplier check" className="rounded-xl border border-line bg-surface-2/60 p-3.5">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-ink-3">Check {name}</h3>
      {isLoading ? <p className="mt-2 text-[13px] text-ink-2">Checking your supplier list…</p> : vendor ? (
        <div className="mt-2 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <VendorRiskBadge risk={vendor.risk_level} />
            {msme && msme !== 'unknown' && <Badge>MSME: {titleCase(msme)}</Badge>}
            <Link to={`/vendors/${vendor.id}`} className="text-[13px] font-medium text-primary-ink underline">Open supplier check</Link>
          </div>
          {(msme === 'micro' || msme === 'small') && (
            <Notice tone="warn" title="45-day payment rule applies">
              A {msme} enterprise must be paid within 45 days or statutory interest applies. Compare with the payment terms.
            </Notice>
          )}
        </div>
      ) : (
        <p className="mt-2 text-[13px] text-ink-2">
          Not checked yet. <Link to={`/vendors?name=${encodeURIComponent(name)}`} className="font-medium text-primary-ink underline">Verify this business</Link> to see whether the GSTIN is genuine and whether the MSME payment rule applies.
        </p>
      )}
    </section>
  );
};

/* ------------------------------------------------------------------ finding card (compact) */

export const FindingCard: React.FC<{
  finding: Finding;
  contractId: string;
  active: boolean;
  onJump: (f: Finding) => void;
}> = ({ finding: f, contractId, active, onJump }) => {
  const setStatus = useSetFindingStatus(contractId);
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const inactive = f.status !== 'open';
  const ref = useRef<HTMLElement>(null);

  useEffect(() => { if (active) ref.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); }, [active]);

  const change = (status: Finding['status']) =>
    setStatus.mutate({ findingId: f.id, status }, { onError: (e) => toast.error(toFriendlyError(e).message) });

  const copy = async () => {
    if (!f.suggested_wording) return;
    try {
      await navigator.clipboard.writeText(f.suggested_wording);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      toast.error("Couldn't copy. Select the text and copy it manually.");
    }
  };

  const canJump = !!f.segment_id;
  const hasDetails = !!(f.suggested_wording || f.legal_note || f.condition_note || !f.verified || f.source === 'rule');

  return (
    <article ref={ref} aria-label={f.title}
      className={cn('rounded-xl border bg-surface transition-all', active ? 'border-primary ring-2 ring-primary/25' : 'border-line', inactive && 'opacity-65')}>
      <button type="button" disabled={!canJump} onClick={() => onJump(f)}
        className={cn('block w-full rounded-t-xl p-3.5 text-left', canJump && 'hover:bg-surface-2/70')}
        aria-label={canJump ? `${f.title}. Show in the contract` : f.title}>
        <span className="flex items-center gap-2">
          <SeverityBadge severity={f.severity} />
          {f.source === 'rule' && <Badge tone="info" icon={<Landmark className="h-3 w-3" aria-hidden />}>Indian law</Badge>}
          {f.status === 'resolved' && <Badge tone="good" icon={<CheckCircle2 className="h-3 w-3" aria-hidden />}>Resolved</Badge>}
          {f.status === 'dismissed' && <Badge>Dismissed</Badge>}
          <span className="ml-auto shrink-0 text-xs text-ink-3">{f.page ? `Page ${f.page}` : f.segment_id ? `Clause ${f.segment_id.replace(/^S/, '')}` : ''}</span>
        </span>
        <span className="mt-2 block text-sm font-semibold leading-snug text-ink">{f.title}</span>
        <span className="mt-0.5 line-clamp-2 block text-[13px] leading-snug text-ink-2">{f.why_it_matters}</span>
        {f.quote && (
          <span className={cn('mt-2.5 line-clamp-3 block border-l-2 pl-2.5 font-serif text-[13px] italic leading-snug text-ink', SEV_STYLE[f.severity].bar)}>
            “{f.quote}”
          </span>
        )}
      </button>

      <div className="px-3.5 pb-3">
        {f.recommendation && (
          <p className="rounded-lg bg-primary-soft px-3 py-2 text-[13px] leading-snug text-primary-ink">
            <span className="font-semibold">Suggested change: </span>{f.recommendation}
          </p>
        )}

        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
          {hasDetails && (
            <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open}
              className="flex min-h-[32px] items-center gap-1 text-xs font-medium text-ink-2 hover:text-ink">
              <ChevronDown className={cn('h-3.5 w-3.5 transition-transform', open && 'rotate-180')} aria-hidden />
              {open ? 'Less' : 'Wording, legal note'}
            </button>
          )}
          <span className="ml-auto flex items-center gap-1">
            {f.status === 'open' ? (
              <>
                <Button size="sm" variant="ghost" className="h-8 px-2 text-xs" onClick={() => change('resolved')} disabled={setStatus.isPending} icon={<Check className="h-3.5 w-3.5" aria-hidden />}>Resolved</Button>
                <Button size="sm" variant="ghost" className="h-8 px-2 text-xs" onClick={() => change('dismissed')} disabled={setStatus.isPending}>Not a concern</Button>
              </>
            ) : (
              <Button size="sm" variant="ghost" className="h-8 px-2 text-xs" onClick={() => change('open')} loading={setStatus.isPending} icon={<Undo2 className="h-3.5 w-3.5" aria-hidden />}>Reopen</Button>
            )}
          </span>
        </div>

        {open && (
          <div className="mt-2 space-y-2.5 border-t border-line pt-3 text-[13px]">
            {f.source !== 'missing' && !f.verified && f.quote && (
              <p className="flex items-start gap-1.5 text-warn-ink"><HelpCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />We couldn't match this quote to the document text, so it isn't counted in the score.</p>
            )}
            {f.condition_note && <p className="text-ink-2"><strong className="text-ink">When this applies: </strong>{f.condition_note}</p>}
            {f.suggested_wording && (
              <div>
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-ink-3">Replacement wording</p>
                <p className="whitespace-pre-wrap rounded-lg border border-line bg-surface-2/60 p-2.5 font-serif text-ink">{f.suggested_wording}</p>
                <Button size="sm" variant="secondary" className="mt-1.5" onClick={copy} icon={copied ? <Check className="h-3.5 w-3.5" aria-hidden /> : <Copy className="h-3.5 w-3.5" aria-hidden />}>
                  {copied ? 'Copied' : 'Copy wording'}
                </Button>
              </div>
            )}
            {f.legal_note && (
              <div className="rounded-lg bg-surface-2 p-2.5 text-ink-2">
                <p className="flex items-center gap-1.5 text-xs font-semibold text-ink"><BookMarked className="h-3.5 w-3.5" aria-hidden />Legal note</p>
                <p className="mt-1">{f.legal_note}</p>
                {f.legal_ref && <p className="mt-1 text-xs text-ink-3">Reference: {f.legal_ref}</p>}
                <p className="mt-1 text-xs text-ink-3">General information. Confirm with a lawyer or CA before relying on it.</p>
              </div>
            )}
          </div>
        )}
      </div>
    </article>
  );
};

/** A protection the contract lacks: no quote to point at, so it is a plain card. */
export const MissingCard: React.FC<{ finding: Finding }> = ({ finding: f }) => (
  <li className="rounded-xl border border-dashed border-line-strong bg-surface p-3.5">
    <div className="flex flex-wrap items-center gap-2">
      <Badge tone="warn">Missing</Badge><Badge>{CATEGORY_LABEL[f.category] ?? titleCase(f.category)}</Badge>
    </div>
    <p className="mt-2 text-sm font-semibold text-ink">{f.title}</p>
    <p className="mt-0.5 text-[13px] leading-snug text-ink-2">{f.why_it_matters}</p>
    {f.suggested_wording && (
      <details className="mt-2">
        <summary className="cursor-pointer text-xs font-medium text-primary-ink">Suggested clause to add</summary>
        <p className="mt-1.5 whitespace-pre-wrap rounded-lg bg-surface-2 p-2.5 font-serif text-[13px] text-ink">{f.suggested_wording}</p>
      </details>
    )}
  </li>
);

/* ------------------------------------------------------------------ ask the contract */

const SUGGESTIONS = [
  'How can this contract be ended, and by whom?',
  'What are the payment terms and what if payment is late?',
  'Am I liable for losses? Is there a limit?',
  'Which law and courts apply in a dispute?',
];

export const AskPanel: React.FC<{
  contractId: string;
  onSee: (segmentId: string | null, quote: string | null) => void;
  disabled?: boolean;
}> = ({ contractId, onSee, disabled }) => {
  const { messages, ask } = useChat(contractId);
  const [text, setText] = useState('');
  const endRef = useRef<HTMLDivElement>(null);
  const list = messages.data ?? [];

  useEffect(() => { if (list.length || ask.isPending) endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); }, [list.length, ask.isPending]);

  const send = (q: string) => {
    const question = q.trim();
    if (question.length < 3 || ask.isPending) return;
    setText('');
    ask.mutate(question);
  };

  const error = useMemo(() => (ask.isError ? toFriendlyError(ask.error) : null), [ask.isError, ask.error]);

  return (
    <div className="flex min-h-full flex-col">
      <div className="flex-1 space-y-3" aria-live="polite">
        <p className="text-[13px] text-ink-3">Answers come only from this contract, with the exact words quoted. If it doesn't say, we'll tell you.</p>
        {messages.isLoading && <Spinner label="Loading conversation" />}
        {!messages.isLoading && list.length === 0 && (
          <div className="flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button key={s} disabled={disabled || ask.isPending} onClick={() => send(s)}
                className="rounded-full border border-line-strong bg-surface px-3 py-1.5 text-left text-[13px] text-ink transition-colors hover:bg-surface-2 disabled:opacity-50">
                {s}
              </button>
            ))}
          </div>
        )}
        {list.map((m) => (
          <div key={m.id} className={cn('flex', m.role === 'user' ? 'justify-end' : 'justify-start')}>
            <div className={cn('max-w-[94%] rounded-2xl px-3.5 py-2.5 text-[13px] leading-snug', m.role === 'user' ? 'bg-primary text-primary-on' : 'border border-line bg-surface')}>
              <p className="whitespace-pre-wrap">{m.content}</p>
              {m.role === 'assistant' && m.found_in_contract === false && (
                <Badge tone="warn" className="mt-2" icon={<HelpCircle className="h-3 w-3" aria-hidden />}>Not covered in this contract</Badge>
              )}
              {m.role === 'assistant' && m.citations.length > 0 && (
                <ul className="mt-2.5 space-y-1.5 border-t border-line pt-2.5">
                  {m.citations.map((c: ChatCitation, i) => (
                    <li key={i} className="rounded-lg bg-surface-2 p-2 text-xs text-ink-2">
                      <span className="line-clamp-4 font-serif italic">“{c.quote}”</span>
                      <span className="mt-1 flex flex-wrap items-center gap-x-3 text-ink-3">
                        {c.page ? <span>Page {c.page}</span> : null}
                        {c.verified && c.segment_id && (
                          <button className="flex items-center gap-1 font-medium text-primary-ink underline" onClick={() => onSee(c.segment_id, c.quote)}>
                            <CornerDownRight className="h-3 w-3" aria-hidden />Show in contract
                          </button>
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        ))}
        {ask.isPending && <Spinner label="Reading the contract…" />}
        {error && <ErrorState title="Couldn't get an answer" message={error.message} onRetry={error.retryable ? () => ask.reset() : undefined} />}
        <div ref={endRef} />
      </div>

      <form className="sticky bottom-0 -mx-5 mt-3 flex items-end gap-2 border-t border-line bg-surface px-5 py-3" onSubmit={(e) => { e.preventDefault(); send(text); }}>
        <label htmlFor="ask-input" className="sr-only">Ask a question about this contract</label>
        <Textarea
          id="ask-input" value={text} rows={2} placeholder="Ask about this contract…" disabled={disabled}
          className="min-h-[44px] flex-1 resize-none text-sm"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(text); } }}
        />
        <Button type="submit" disabled={disabled || text.trim().length < 3} loading={ask.isPending} aria-label="Ask" icon={<Send className="h-4 w-4" aria-hidden />} />
      </form>
    </div>
  );
};
