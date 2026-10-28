import React, { useCallback, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, CheckCircle2, Download, MoreVertical, RefreshCw, Trash2 } from 'lucide-react';
import * as Menu from '@radix-ui/react-dropdown-menu';
import { toast } from 'sonner';
import { toFriendlyError } from '@/api/client';
import { AiDisclaimer, Button, EmptyState, ErrorState, Notice, ProgressSteps, SkeletonRows } from '@/ui/primitives';
import { ConfirmDialog, TabList, TabPanel, TabTrigger, TabsRoot } from '@/ui/overlays';
import { SEVERITY_ORDER, type Severity } from '@/ui/risk';
import { cn, formatDate, plural, titleCase } from '@/lib/utils';
import {
  contractTypeLabel, counterpartyLine, downloadContractFile, useContract, useDeleteContract, useRetryContract,
  type ContractDetail, type Finding,
} from './api';
import { AskPanel, CounterpartyCard, FindingCard, KeyTerms, LABEL, MissingCard, Verdict } from './components';
import { ContractText, type TextFocus } from './ContractText';

const STEPS = [
  { key: 'queued', label: 'Waiting to start' },
  { key: 'parsing', label: 'Reading your file' },
  { key: 'reading', label: 'Finding the clauses and key terms' },
  { key: 'analysing', label: 'Checking risky clauses and Indian-law issues' },
  { key: 'verifying', label: 'Matching every finding to the exact text' },
  { key: 'scoring', label: 'Scoring the contract' },
];

/** Extra guidance per failure kind (the message itself already says what happened). */
const FAILURE_HELP: Record<string, string> = {
  auth: 'Ask your administrator to check the Gemini API key.',
  quota: 'Wait a few minutes, then try again.',
  unavailable: 'This is usually temporary.',
  invalid_output: 'Trying again usually fixes this.',
  bad_input: 'Try uploading a clearer or different copy of the file.',
};

/* ------------------------------------------------------------------ pieces */

const ProcessingCard: React.FC<{ c: ContractDetail }> = ({ c }) => (
  <div className="mx-auto max-w-md rounded-2xl bg-surface-2 p-7">
    <p className={LABEL}>Reading</p>
    <h2 className="mt-2 font-display text-2xl leading-tight text-ink">{c.title || c.filename || 'Your contract'}</h2>
    <p className="mb-6 mt-2 text-sm text-ink-2">This usually takes 30 to 60 seconds. You can leave this page; it keeps running.</p>
    <div aria-live="polite">
      <ProgressSteps
        steps={c.stage === 'ocr' ? [STEPS[0], STEPS[1], { key: 'ocr', label: 'Reading the scanned pages with AI' }, ...STEPS.slice(2)] : STEPS}
        current={c.stage ?? 'queued'}
      />
    </div>
  </div>
);

const SeverityFilter: React.FC<{ value: Severity | 'all'; onChange: (v: Severity | 'all') => void; counts: Record<string, number> }> = ({ value, onChange, counts }) => (
  <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter by severity">
    {(['all', ...SEVERITY_ORDER] as const).filter((s) => s === 'all' || counts[s] > 0).map((s) => (
      <button key={s} onClick={() => onChange(s)} aria-pressed={value === s}
        className={cn('min-h-[32px] rounded-full border px-3 py-1 text-xs font-medium transition-colors',
          value === s ? 'border-primary bg-primary text-primary-on' : 'border-line-strong bg-surface text-ink-2 hover:bg-surface-2')}>
        {s === 'all' ? 'All' : titleCase(s)} <span className={cn('tabular-nums', value === s ? 'opacity-70' : 'text-ink-3')}>{counts[s]}</span>
      </button>
    ))}
  </div>
);

/* ------------------------------------------------------------------ the contract view */

export const ContractView: React.FC<{ id: string }> = ({ id }) => {
  const navigate = useNavigate();
  const { data: c, isLoading, isError, error, refetch, isFetching } = useContract(id);
  const retry = useRetryContract();
  const del = useDeleteContract();
  const [tab, setTab] = useState('findings');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [sevFilter, setSevFilter] = useState<Severity | 'all'>('all');
  const [showClosed, setShowClosed] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [focus, setFocus] = useState<TextFocus | null>(null);

  const jumpToFinding = useCallback((f: Finding) => {
    setActiveId(f.id);
    setFocus({ segmentId: f.segment_id, findingId: f.verified && f.quote ? f.id : null, quote: null, nonce: Date.now() });
  }, []);
  const jumpToMark = useCallback((findingId: string | null) => {
    if (!findingId) return;
    setActiveId(findingId);
    setTab('findings');
  }, []);
  const seeInContract = useCallback((segmentId: string | null, quote: string | null) => {
    setActiveId(null);
    setFocus({ segmentId, findingId: null, quote, nonce: Date.now() });
  }, []);

  const { issues, missing, counts } = useMemo(() => {
    const visible = (c?.findings ?? []).filter((f) => showClosed || f.status === 'open');
    const counts: Record<string, number> = { all: 0, critical: 0, high: 0, medium: 0, low: 0 };
    visible.filter((f) => f.source !== 'missing').forEach((f) => { counts.all++; counts[f.severity]++; });
    return {
      issues: visible.filter((f) => f.source !== 'missing' && (sevFilter === 'all' || f.severity === sevFilter)),
      missing: visible.filter((f) => f.source === 'missing'),
      counts,
    };
  }, [c, sevFilter, showClosed]);

  if (isLoading) {
    return <div className="p-6 pr-28 sm:pr-[19rem]" aria-busy="true" aria-label="Loading contract"><SkeletonRows rows={5} /></div>;
  }
  if (isError || !c) {
    const fe = toFriendlyError(error);
    return (
      <div className="space-y-4 p-6 pr-28 sm:pr-[19rem]">
        <Link to="/contracts" className="inline-flex items-center gap-1 rounded text-sm font-medium text-ink-2 hover:text-ink"><ArrowLeft className="h-4 w-4" aria-hidden />All contracts</Link>
        <ErrorState title={fe.status === 404 ? 'Contract not found' : 'Could not load this contract'}
          message={fe.status === 404 ? 'It may have been deleted, or it belongs to another company.' : fe.message}
          onRetry={fe.status === 404 ? undefined : () => refetch()} retrying={isFetching} />
      </div>
    );
  }

  const running = c.status === 'processing' || c.status === 'queued';
  const analyzed = c.status === 'analyzed';
  const cov = c.score_breakdown?.coverage;
  const truncated = !!cov?.truncated;
  const reviewedSegments = truncated ? cov?.reviewed_segments ?? null : null;
  const sub = [
    contractTypeLabel(c.contract_type, c.contract_type_label),
    counterpartyLine(c.facts, c.counterparty_name),
    c.page_count ? plural(c.page_count, 'page') : null,
    `Uploaded ${formatDate(c.created_at)}`,
  ].filter(Boolean).join(' · ');
  const warnings = c.warnings.filter((w) => !(truncated && /very long/i.test(w)));

  const menu = (
    <Menu.Root>
      <Menu.Trigger asChild><button type="button" aria-label="More actions" className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-ink-2 transition-colors hover:bg-surface-2 hover:text-ink"><MoreVertical className="h-4 w-4" aria-hidden /></button></Menu.Trigger>
      <Menu.Portal>
        <Menu.Content align="end" sideOffset={6} className="z-50 w-52 rounded-xl border border-line bg-surface p-1.5 shadow-float">
          <Menu.Item disabled={running} className="flex min-h-[40px] cursor-pointer items-center gap-2 rounded-md px-3 text-sm text-ink outline-none data-[disabled]:opacity-50 data-[highlighted]:bg-surface-2"
            onSelect={() => retry.mutate(c.id, { onError: (e) => toast.error(toFriendlyError(e).message) })}>
            <RefreshCw className="h-4 w-4" aria-hidden />Analyse again
          </Menu.Item>
          <Menu.Item className="flex min-h-[40px] cursor-pointer items-center gap-2 rounded-md px-3 text-sm text-critical-ink outline-none data-[highlighted]:bg-critical-soft"
            onSelect={() => setConfirmDelete(true)}>
            <Trash2 className="h-4 w-4" aria-hidden />Delete contract
          </Menu.Item>
        </Menu.Content>
      </Menu.Portal>
    </Menu.Root>
  );

  return (
    <div className="flex h-full flex-col">
      <header className="flex min-h-[72px] shrink-0 items-start justify-between gap-3 border-b border-line bg-surface py-4 pl-4 pr-28 sm:pl-8 sm:pr-60">
        <div className="min-w-0">
          <Link to="/contracts" className="mb-1.5 inline-flex items-center gap-1 rounded text-xs font-medium text-ink-2 hover:text-ink"><ArrowLeft className="h-3.5 w-3.5" aria-hidden />All contracts</Link>
          <h1 className="truncate font-display text-2xl leading-tight text-ink sm:text-[1.75rem]" title={c.title ?? undefined}>{c.title || c.filename || 'Contract'}</h1>
          <p className="mt-0.5 truncate text-[13px] text-ink-3">{sub}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {analyzed && (
            <Button variant="secondary" size="sm" icon={<Download className="h-4 w-4" aria-hidden />}
              onClick={() => downloadContractFile(c.id, c.filename || 'contract').catch((e) => toast.error(toFriendlyError(e).message))}>
              <span className="max-sm:sr-only">Original file</span>
            </Button>
          )}
          {menu}
        </div>
      </header>

      <ConfirmDialog open={confirmDelete} onOpenChange={setConfirmDelete} danger loading={del.isPending}
        title="Delete this contract?" description="The file, its analysis and its calendar reminders will be permanently removed. This can't be undone." confirmLabel="Delete"
        onConfirm={() => del.mutate(c.id, { onSuccess: () => { toast.success('Contract deleted'); navigate('/contracts'); }, onError: (e) => toast.error(toFriendlyError(e).message) })} />

      {(running || c.status === 'failed') && (
        <div className="flex-1 overflow-y-auto px-4 py-12 sm:py-20">
          {running && <ProcessingCard c={c} />}
          {c.status === 'failed' && (
            <div className="mx-auto max-w-md space-y-3">
              <ErrorState
                title={c.error_kind === 'legacy' ? 'This contract needs a fresh review' : "We couldn't finish reading this contract"}
                message={`${c.error_message ?? 'Something went wrong.'} ${c.error_kind ? FAILURE_HELP[c.error_kind] ?? '' : ''}`.trim()}
                onRetry={() => retry.mutate(c.id, { onError: (e) => toast.error(toFriendlyError(e).message) })} retrying={retry.isPending} />
              <p className="px-1 text-xs text-ink-3">Nothing was scored. We never show a "safe" result for a contract we could not read.</p>
            </div>
          )}
        </div>
      )}

      {analyzed && (
        <div className="min-h-0 flex-1 overflow-y-auto md:flex md:overflow-hidden">
          {/* centre: the contract itself */}
          <div className="bg-surface-2/50 px-4 py-8 sm:px-8 md:min-w-0 md:flex-1 md:overflow-y-auto" id="contract-scroll">
            <div className="mx-auto mb-6 max-w-[44rem] space-y-3">
              {truncated && (
                <Notice tone="warn" title="Long contract: only part of it was reviewed">
                  We reviewed {cov?.reviewed_pages && cov?.total_pages && cov.total_pages > 1 ? `the first ${cov.reviewed_pages} of ${cov.total_pages} pages` : `the first ${cov?.reviewed_segments} of ${cov?.total_segments} sections`}.
                  Anything after that was not checked, and "missing clause" checks were skipped.
                </Notice>
              )}
              {warnings.map((w) => <Notice key={w} tone="warn">{w}</Notice>)}
            </div>
            <ContractText segments={c.segments} findings={c.findings} hasPages={c.has_pages} reviewedSegments={reviewedSegments} focus={focus} activeId={activeId} onMark={jumpToMark} />
            <AiDisclaimer className="mx-auto mt-8 max-w-[44rem]" />
          </div>

          {/* right rail: the verdict (first on phones) */}
          <aside aria-label="Verdict" className="border-b border-line bg-surface max-md:order-first md:w-96 md:shrink-0 md:overflow-y-auto md:border-b-0 md:border-l">
            <Verdict contract={c} />
            <TabsRoot value={tab} onValueChange={setTab}>
              <TabList label="Contract review" className="sticky top-0 z-10 bg-surface px-3">
                <TabTrigger value="findings" count={counts.all}>Findings</TabTrigger>
                <TabTrigger value="terms">Key terms</TabTrigger>
                <TabTrigger value="ask">Ask</TabTrigger>
              </TabList>

              <TabPanel value="findings" className="space-y-4 px-4 pb-10 pt-5">
                {c.findings.some((f) => f.source !== 'missing') && (
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <SeverityFilter value={sevFilter} onChange={setSevFilter} counts={counts} />
                    <label className="flex min-h-[32px] cursor-pointer items-center gap-1.5 rounded text-xs text-ink-2">
                      <input type="checkbox" className="h-3.5 w-3.5 accent-[var(--primary)]" checked={showClosed} onChange={(e) => setShowClosed(e.target.checked)} />
                      Show closed
                    </label>
                  </div>
                )}
                {counts.all === 0 && missing.length === 0 ? (
                  <EmptyState icon={<CheckCircle2 className="h-5 w-5" />} title="No significant issues found" className="py-10"
                    description="We found no clause that clearly works against you. That isn't a guarantee: read the key terms, and ask a lawyer if the deal is large." />
                ) : (
                  <>
                    {issues.map((f) => <FindingCard key={f.id} finding={f} contractId={c.id} active={activeId === f.id} onJump={jumpToFinding} />)}
                    {issues.length === 0 && counts.all > 0 && <EmptyState title="No findings at this severity" description="Pick another level above to see the rest." className="py-8" />}
                    {missing.length > 0 && sevFilter === 'all' && (
                      <section aria-labelledby="missing-h" className="pt-4">
                        <h3 id="missing-h" className={cn(LABEL, 'mb-3')}>Not in this contract</h3>
                        <ul className="space-y-3">{missing.map((f) => <MissingCard key={f.id} finding={f} />)}</ul>
                      </section>
                    )}
                  </>
                )}
              </TabPanel>

              <TabPanel value="terms" className="space-y-6 px-5 pb-10 pt-5">
                <KeyTerms contract={c} />
                <CounterpartyCard name={c.counterparty_name} type={c.contract_type} />
              </TabPanel>

              <TabPanel value="ask" className="px-5 pb-0 pt-5"><AskPanel contractId={c.id} onSee={seeInContract} /></TabPanel>
            </TabsRoot>
          </aside>
        </div>
      )}
    </div>
  );
};
