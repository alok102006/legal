import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AlertTriangle, ArrowLeft, Check, CheckCircle2, Copy, Download, FileText, MoreVertical, Scale, Trash2, Undo2 } from 'lucide-react';
import * as Menu from '@radix-ui/react-dropdown-menu';
import { toast } from 'sonner';
import { toFriendlyError } from '@/api/client';
import { Button, ErrorState, ProgressSteps, SkeletonRows } from '@/ui/primitives';
import { ConfirmDialog, Modal } from '@/ui/overlays';
import { cn, formatDate, formatINR } from '@/lib/utils';
import { useDeleteNotice, useNotice, useRetryNotice, useSaveActions, useUpdateNotice, type NoticeDetail } from './api';
import { DeadlineStrip } from './DeadlineStrip';
import { downloadText } from './lib';
import { NoticeText } from './NoticeText';
import { ReplyEditor } from './ReplyEditor';

/* ------------------------------------------------------------------ stepper */

const Step: React.FC<{ n: number; title: string; done?: boolean; aside?: React.ReactNode; last?: boolean; children: React.ReactNode }> = ({ n, title, done, aside, last, children }) => (
  <li className={cn('relative pl-12', !last && 'pb-10')}>
    <span className={cn('absolute left-0 top-0 flex h-8 w-8 items-center justify-center rounded-full text-sm font-semibold tabular-nums shadow-card', done ? 'bg-good-soft text-good-ink' : 'bg-primary text-primary-on')}>
      {done ? <Check className="h-4 w-4" aria-label="Done" /> : n}
    </span>
    {!last && <span className="absolute bottom-1 left-4 top-11 w-px bg-line-strong" aria-hidden />}
    <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
      <h2 className="text-[17px] font-semibold tracking-[-0.01em] text-ink">{title}</h2>
      {aside && <span className="text-xs font-medium tabular-nums text-ink-3">{aside}</span>}
    </div>
    <div className="mt-3">{children}</div>
  </li>
);

const HANDLER_PILL: Record<string, string> = {
  owner: 'bg-good-soft text-good-ink',
  ca: 'bg-primary-soft text-primary-ink',
  lawyer: 'bg-warn-soft text-warn-ink',
  lawyer_required: 'bg-critical-soft text-critical-ink',
};
const HANDLER_NAME: Record<string, string> = { owner: 'You can handle it', ca: 'Your CA', lawyer: 'A lawyer', lawyer_required: 'Lawyer required' };

const TypeFacts: React.FC<{ n: NoticeDetail }> = ({ n }) => {
  const t = n.type_info;
  if (!t) return null;
  return (
    <div className="rounded-2xl bg-surface-2 px-5 py-4">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-[15px] font-semibold text-ink">{t.label}</p>
        <span className={cn('rounded-full px-2.5 py-0.5 text-xs font-semibold', HANDLER_PILL[t.handler])}>{HANDLER_NAME[t.handler] ?? t.handler}</span>
        {!t.verified && <span title={t.verify_note ?? undefined} className="rounded-full border border-line-strong bg-surface px-2.5 py-0.5 text-xs font-medium text-ink-2">Being verified</span>}
      </div>
      <p className="mt-1.5 text-sm leading-relaxed text-ink-2">{t.meaning}</p>
      <p className="mt-2 text-xs text-ink-3"><span className="font-semibold text-ink-2">Law:</span> {t.ref}</p>
      <p className="mt-0.5 text-xs text-ink-3"><span className="font-semibold text-ink-2">Who handles it:</span> {t.handler_label}</p>
      {!t.verified && t.verify_note && <p className="mt-1.5 text-xs text-ink-3">{t.verify_note}</p>}
    </div>
  );
};

const WhatThisIs: React.FC<{ n: NoticeDetail }> = ({ n }) => {
  const foreign = !!n.language && !/^en/i.test(n.language) && n.summary_local.length > 0;
  return (
  <div className="space-y-4">
    <p className="text-[15px] leading-relaxed text-ink">
      This is a <strong>{(n.type_info?.label ?? n.type_label)?.toLowerCase() ?? 'notice'}</strong>
      {n.issuer_name ? <> from <strong>{n.issuer_name}</strong>{n.issuer_role ? ` (${n.issuer_role})` : ''}</> : null}
      {n.notice_date ? <>, dated {formatDate(n.notice_date)}</> : null}.
      {n.form_or_section ? <> It is issued under <strong>{n.form_or_section}</strong>.</> : null}
    </p>
    <TypeFacts n={n} />
    {n.summary_points.length > 0 && <ul className="space-y-2.5">{n.summary_points.map((p) => <li key={p} className="flex gap-2.5 text-[15px] leading-7 text-ink"><span className="mt-[11px] h-1.5 w-1.5 shrink-0 rounded-full bg-ink-3" aria-hidden />{p}</li>)}</ul>}
    {foreign && (
      <details className="rounded-xl bg-surface-2 px-4 py-3">
        <summary className="cursor-pointer text-sm font-medium text-ink">In the notice's language ({n.language})</summary>
        <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm leading-relaxed text-ink-2">{n.summary_local.map((p) => <li key={p}>{p}</li>)}</ul>
      </details>
    )}
    {n.allegations.length > 0 && (
      <div>
        <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-2">What they allege</p>
        <ol className="space-y-2">
          {n.allegations.map((a, i) => (
            <li key={a} className="flex gap-3 text-sm leading-relaxed text-ink">
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-surface-2 text-[11px] font-semibold tabular-nums text-ink-2">{i + 1}</span>{a}
            </li>))}
        </ol>
      </div>
    )}
    {(n.amount_claimed || n.demands.length > 0) && (
      <div className="grid gap-3 sm:grid-cols-[auto_1fr]">
        {n.amount_claimed ? (
          <div className="rounded-2xl bg-surface-2 px-5 py-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-2">Amount claimed</p>
            <p className="mt-1 font-display text-4xl leading-none tabular-nums text-ink">{formatINR(n.amount_claimed)}</p>
          </div>) : null}
        {n.demands.length > 0 && (
          <div className="rounded-2xl bg-surface-2 px-5 py-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-2">What they demand</p>
            <ul className="mt-1 list-disc space-y-1 pl-4 text-sm text-ink">{n.demands.map((d) => <li key={d}>{d}</li>)}</ul>
          </div>)}
      </div>
    )}
    {n.reference_number && <p className="text-xs text-ink-3">Reference <span className="font-mono">{n.reference_number}</span></p>}
    {(n.pages > 1 || n.input_cleaned) && (
      <p className="text-xs text-ink-3">
        {n.pages > 1 ? `Read from ${n.pages} pages.` : ''}{n.pages > 1 && n.input_cleaned ? ' ' : ''}{n.input_cleaned ? 'We cleaned the WhatsApp formatting before reading it.' : ''}
      </p>
    )}
  </div>
  );
};

const WhatTheLawSays: React.FC<{ n: NoticeDetail }> = ({ n }) => {
  const ignored = n.legal_if_ignored ?? n.if_ignored;
  return (
    <div className="space-y-3">
      {n.legal_note ? (
        <>
          <p className="text-[15px] leading-relaxed text-ink">{n.legal_note}</p>
          <p className="flex items-start gap-2 rounded-xl bg-surface-2 px-3.5 py-2.5 text-xs text-ink-2">
            <Scale className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
            <span><strong className="text-ink">Source:</strong> {n.legal_ref}. General information, not advice. Confirm with a lawyer.</span>
          </p>
        </>
      ) : <p className="text-sm text-ink-2">We have no standard rule for this kind of notice, so follow the dates and sections in the notice itself and ask a lawyer how they apply.</p>}
      {n.statutes.length > 0 && <p className="text-sm text-ink-2"><strong className="text-ink">The notice cites: </strong>{n.statutes.join('; ')}</p>}
      {(ignored || n.consequences) && (
        <div className="rounded-xl border border-l-2 border-line border-l-serious bg-surface p-4 shadow-card">
          <p className="flex items-center gap-1.5 text-sm font-semibold text-serious-ink"><AlertTriangle className="h-4 w-4" aria-hidden />If you ignore it</p>
          {ignored && <p className="mt-1 text-sm text-ink">{ignored}</p>}
          {n.consequences && <p className="mt-1.5 text-sm text-ink-2"><strong className="text-ink">The sender says: </strong>{n.consequences}</p>}
        </div>
      )}
    </div>
  );
};

const Checklist: React.FC<{ n: NoticeDetail }> = ({ n }) => {
  const save = useSaveActions(n.id);
  const [docTicks, setDocTicks] = useState<Record<number, boolean>>({});
  const done = new Set(n.actions_done);
  const toggle = (i: number) => {
    const next = new Set(done);
    if (next.has(i)) next.delete(i); else next.add(i);
    save.mutate([...next].sort((a, b) => a - b), { onError: (e) => toast.error(toFriendlyError(e).message) });
  };
  const docs = n.drafts[0]?.documents_to_gather ?? [];
  return (
    <div className="space-y-4">
      {n.actions.length > 0 ? (
        <ul className="space-y-1.5">
          {n.actions.map((a, i) => (
            <li key={a}>
              <label className={cn('flex cursor-pointer items-start gap-3 rounded-xl px-4 py-3 transition-[background-color,box-shadow]', done.has(i) ? 'bg-surface-2' : 'bg-surface-2 hover:shadow-card')}>
                <input type="checkbox" className="mt-0.5 h-5 w-5 shrink-0 accent-[var(--primary)]" checked={done.has(i)} onChange={() => toggle(i)} />
                <span className={cn('text-[15px] leading-snug', done.has(i) ? 'text-ink-3 line-through' : 'text-ink')}>{a}</span>
              </label>
            </li>))}
        </ul>
      ) : <p className="text-sm text-ink-2">This notice was read before action steps were added. Use the documents below and the reply in the next step.</p>}
      {docs.length > 0 && (
        <div>
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-2">Documents to gather</p>
          <ul className="space-y-1">
            {docs.map((d, i) => (
              <li key={d}><label className="flex cursor-pointer items-start gap-2.5 text-sm text-ink">
                <input type="checkbox" className="mt-0.5 h-4 w-4 accent-[var(--primary)]" checked={!!docTicks[i]} onChange={(e) => setDocTicks({ ...docTicks, [i]: e.target.checked })} />
                <span className={cn(docTicks[i] && 'text-ink-3 line-through')}>{d}</span></label></li>))}
          </ul>
        </div>
      )}
    </div>
  );
};

const BRIEF_HEADING = /^(\d+\.\s+[A-Z][A-Z0-9 ()/,&'-]+|LAWYER BRIEF.*)$/;

const LawyerBriefModal: React.FC<{ n: NoticeDetail; open: boolean; onOpenChange: (o: boolean) => void }> = ({ n, open, onOpenChange }) => {
  const brief = n.lawyer_brief ?? '';
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard.writeText(brief); setCopied(true); setTimeout(() => setCopied(false), 1600); } catch { toast.error("Couldn't copy. Select the text and copy it manually."); }
  };
  const file = `lawyer-brief-${n.reference_number ?? 'notice'}.txt`.replace(/[^\w.-]+/g, '_');
  return (
    <Modal open={open} onOpenChange={onOpenChange} title="Lawyer brief" description="One page to hand to your lawyer, built from what was read in the notice. Nothing here is invented."
      footer={<>
        <Button variant="secondary" onClick={copy} icon={copied ? <Check className="h-4 w-4" aria-hidden /> : <Copy className="h-4 w-4" aria-hidden />}>{copied ? 'Copied' : 'Copy'}</Button>
        <Button onClick={() => downloadText(file, brief)} icon={<Download className="h-4 w-4" aria-hidden />}>Download .txt</Button>
      </>}>
      {brief ? (
        <div className="rounded-xl bg-surface-2 p-4 text-[13px] leading-6 text-ink">
          {brief.split('\n').map((line, i) => BRIEF_HEADING.test(line.trim())
            ? <p key={i} className="mt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-2 first:mt-0">{line}</p>
            : <p key={i} className="whitespace-pre-wrap break-words">{line || '\u00A0'}</p>)}
        </div>
      ) : <p className="text-sm text-ink-2">The brief is not available for this notice yet.</p>}
    </Modal>
  );
};

/* ------------------------------------------------------------------ view */

const STAGES = [
  { key: 'queued', label: 'Waiting to start' }, { key: 'parsing', label: 'Opening the notice' },
  { key: 'reading', label: 'Finding the claim, the amount and the deadline' }, { key: 'drafting', label: 'Drafting your reply' },
];

export const NoticeView: React.FC<{ id: string }> = ({ id }) => {
  const navigate = useNavigate();
  const { data: n, isLoading, isError, error, refetch } = useNotice(id);
  const retry = useRetryNotice(id);
  const update = useUpdateNotice(id);
  const del = useDeleteNotice();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [briefOpen, setBriefOpen] = useState(false);
  const fail = (e: unknown) => toast.error(toFriendlyError(e).message);
  const back = <Link to="/notices" className="inline-flex items-center gap-1 rounded text-sm font-medium text-ink-2 hover:text-ink"><ArrowLeft className="h-4 w-4" aria-hidden />All notices</Link>;
  const shell = 'mx-auto w-full max-w-[1400px] px-4 py-6 sm:px-8 sm:py-8';
  // the floating New notice / panel buttons sit at the top-right of the sheet: keep the header clear of them
  const headerClear = 'pr-28 sm:pr-[17rem]';

  if (isLoading) return <div className={cn(shell, headerClear)} aria-busy="true" aria-label="Loading notice"><SkeletonRows rows={5} /></div>;
  if (isError || !n) {
    const fe = toFriendlyError(error);
    return <div className={cn(shell, 'space-y-4')}><div className={headerClear}>{back}</div><ErrorState title={fe.status === 404 ? 'Notice not found' : 'Could not load this notice'} message={fe.message} onRetry={fe.status === 404 ? undefined : () => refetch()} /></div>;
  }

  const open = n.status !== 'closed';
  const ready = n.status === 'analyzed' || n.status === 'closed';
  const actionsDone = n.actions.length > 0 && n.actions_done.length >= n.actions.length;
  const subtitle = [n.type_label, n.issuer_name, n.reference_number && `Ref ${n.reference_number}`].filter(Boolean).join(' · ');
  const stages = n.source_name === 'Pasted text' ? STAGES.filter((s) => s.key !== 'parsing') : STAGES;

  return (
    <div className={shell}>
      <div className="mb-8">
        <div className={cn('flex items-start justify-between gap-3', headerClear)}>
          <div className="min-w-0">
            <h1 className="font-display text-[1.9rem] font-normal leading-tight text-ink sm:text-[2.2rem]">{n.title ?? 'Notice'}</h1>
            {subtitle && <p className="mt-1.5 text-[13px] text-ink-3">{subtitle}</p>}
          </div>
          <Menu.Root>
            <Menu.Trigger asChild><button type="button" aria-label="More actions" className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-ink-2 transition-colors hover:bg-surface-2 hover:text-ink"><MoreVertical className="h-4 w-4" aria-hidden /></button></Menu.Trigger>
            <Menu.Portal><Menu.Content align="end" sideOffset={6} className="z-50 w-56 rounded-xl border border-line bg-surface p-1.5 shadow-float">
              {ready && (
                <Menu.Item className="flex min-h-[40px] cursor-pointer items-center gap-2 rounded-md px-3 text-sm text-ink outline-none data-[highlighted]:bg-surface-2"
                  onSelect={() => update.mutate({ status: open ? 'closed' : 'analyzed' }, { onSuccess: () => toast.success(open ? 'Marked as replied' : 'Reopened'), onError: fail })}>
                  {open ? <CheckCircle2 className="h-4 w-4" aria-hidden /> : <Undo2 className="h-4 w-4" aria-hidden />}{open ? 'Mark as replied' : 'Reopen'}
                </Menu.Item>)}
              {ready && n.lawyer_brief && (
                <Menu.Item className="flex min-h-[40px] cursor-pointer items-center gap-2 rounded-md px-3 text-sm text-ink outline-none data-[highlighted]:bg-surface-2" onSelect={() => setBriefOpen(true)}>
                  <FileText className="h-4 w-4" aria-hidden />Lawyer brief
                </Menu.Item>)}
              <Menu.Item className="flex min-h-[40px] cursor-pointer items-center gap-2 rounded-md px-3 text-sm text-critical-ink outline-none data-[highlighted]:bg-critical-soft" onSelect={() => setConfirmDelete(true)}>
                <Trash2 className="h-4 w-4" aria-hidden />Delete notice
              </Menu.Item>
            </Menu.Content></Menu.Portal>
          </Menu.Root>
        </div>
      </div>
      <LawyerBriefModal n={n} open={briefOpen} onOpenChange={setBriefOpen} />
      <ConfirmDialog open={confirmDelete} onOpenChange={setConfirmDelete} danger loading={del.isPending} title="Delete this notice?" description="The notice, its drafts and its calendar reminder will be removed."
        confirmLabel="Delete" onConfirm={() => del.mutate(n.id, { onSuccess: () => { toast.success('Notice deleted'); navigate('/notices'); }, onError: fail })} />

      {n.status === 'processing' && (
        <div className="mx-auto mt-8 max-w-xl rounded-2xl bg-surface-2 p-7">
          <h2 className="font-display text-2xl leading-tight text-ink">Reading your notice</h2>
          <p className="mb-6 mt-2 text-sm text-ink-2">{n.stage === 'ocr' ? 'This looks like a scan, so reading it takes a little longer.' : 'This usually takes 20 to 40 seconds. You can leave this page; it keeps going.'}</p>
          <div aria-live="polite"><ProgressSteps steps={stages} current={n.stage === 'ocr' ? 'parsing' : n.stage ?? 'queued'} /></div>
        </div>
      )}

      {n.status === 'failed' && (
        <div className="mx-auto mt-8 max-w-xl space-y-3">
          <ErrorState title="We couldn't finish reading this notice" message={n.error_message ?? 'Something went wrong.'} onRetry={() => retry.mutate(undefined, { onError: fail })} retrying={retry.isPending} />
          <p className="text-sm text-ink-2">Nothing was guessed. Until this works, read the notice yourself for the reply date, and do not wait on it.</p>
          <Button variant="ghost" size="sm" icon={<Trash2 className="h-4 w-4" aria-hidden />} onClick={() => setConfirmDelete(true)}>Delete this notice</Button>
        </div>
      )}

      {ready && (
        <div className="space-y-8">
          <DeadlineStrip n={n} saving={update.isPending} onReceived={(iso) => update.mutate({ received_date: iso }, { onSuccess: () => toast.success('Reply date updated'), onError: fail })}
            onNoticeDate={(iso) => update.mutate({ notice_date: iso }, { onSuccess: () => toast.success('Notice date saved. Reply date worked out again.'), onError: fail })} />

          <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
            <div className="min-w-0 lg:order-2">
            {n.lawyer_required && (
              <div role="note" className="mb-6 flex items-start gap-3 rounded-2xl bg-critical-soft px-5 py-4 text-critical-ink">
                <Scale className="mt-0.5 h-5 w-5 shrink-0" aria-hidden />
                <div>
                  <p className="text-[15px] font-semibold">A lawyer is required for this notice</p>
                  <p className="mt-0.5 text-sm">{n.type_info?.handler_label ?? 'This kind of notice should not be answered without a lawyer.'} Take the Lawyer brief (top-right menu) with you. Use the steps below to get ready, not to reply on your own.</p>
                </div>
              </div>)}
            <ol aria-label="What to do, step by step">
              <Step n={1} title="What this is"><WhatThisIs n={n} /></Step>
              <Step n={2} title="What the law says"><WhatTheLawSays n={n} /></Step>
              <Step n={3} title="What to do now" done={actionsDone} aside={n.actions.length > 0 ? `${Math.min(n.actions_done.length, n.actions.length)} of ${n.actions.length} done` : undefined}><Checklist n={n} /></Step>
              <Step n={4} title={n.draft_kind === 'action_plan' ? 'Your action plan' : 'Your reply'} last done={n.review_status === 'lawyer_approved'} aside={n.review_status === 'lawyer_approved' ? (n.draft_kind === 'action_plan' ? 'Confirmed with lawyer' : 'Reviewed by lawyer') : 'Draft, not yet reviewed'}><ReplyEditor n={n} /></Step>
            </ol>
              <p className="mt-8 pl-12 text-xs text-ink-3">Decision support, not legal advice. Have a lawyer read your reply before you send it.</p>
            </div>
            <NoticeText n={n} className="max-h-[32rem] lg:order-1 lg:sticky lg:top-4 lg:max-h-[calc(100vh-8.5rem)]" />
          </div>
        </div>
      )}
    </div>
  );
};
