import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Check, ChevronRight, Copy, Download, RefreshCw, RotateCcw, Save, ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';
import { toFriendlyError } from '@/api/client';
import { Button, Input, Notice } from '@/ui/primitives';
import { cn } from '@/lib/utils';
import { useRegenerateDraft, useSaveDraft, useUpdateNotice, type NoticeDetail, type ReplyDraft } from './api';

const BLANK = /(\[(?:CONFIRM|FILL|ADD)[^\]]{0,200}\])/g;
const blankLabel = (b: string) => b.replace(/^\[(?:CONFIRM|FILL|ADD):?\s*/, '').replace(/\]$/, '').trim() || 'Fill in';
const uniqueBlanks = (t: string) => Array.from(new Set(t.match(BLANK) ?? []));

const REVIEW = [
  { key: 'draft', label: 'Draft' },
  { key: 'ready_for_lawyer', label: 'With your lawyer' },
  { key: 'lawyer_approved', label: 'Reviewed by lawyer' },
] as const;

const download = (name: string, text: string) => {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url; a.download = name; a.click();
  URL.revokeObjectURL(url);
};

const textLayer = 'whitespace-pre-wrap break-words p-5 font-serif text-[15px] leading-7 sm:p-8';

export const ReplyEditor: React.FC<{ n: NoticeDetail }> = ({ n }) => {
  const save = useSaveDraft(n.id);
  const regen = useRegenerateDraft(n.id);
  const update = useUpdateNotice(n.id);
  const [versionId, setVersionId] = useState<string | null>(null);
  const draft: ReplyDraft | undefined = useMemo(() => n.drafts.find((d) => d.id === versionId) ?? n.drafts[0], [n.drafts, versionId]);
  const [text, setText] = useState(draft?.reply_text ?? '');
  const [instr, setInstr] = useState('');
  const [copied, setCopied] = useState(false);
  const [cursor, setCursor] = useState(0);
  const taRef = useRef<HTMLTextAreaElement>(null);
  const backRef = useRef<HTMLDivElement>(null);

  useEffect(() => { setText(draft?.reply_text ?? ''); setCursor(0); }, [draft?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!draft) return <p className="text-sm text-ink-2">No draft was produced for this notice.</p>;

  const fail = (e: unknown) => toast.error(toFriendlyError(e).message);
  const dirty = text !== draft.reply_text;
  const blanks = uniqueBlanks(text);
  const approved = n.review_status === 'lawyer_approved';
  const open = n.status !== 'closed';
  const reviewIdx = REVIEW.findIndex((s) => s.key === n.review_status);
  const canSave = dirty && text.trim().length >= 20;
  const isLatest = draft.id === n.drafts[0]?.id;

  const focusBlank = (i: number) => {
    const ta = taRef.current;
    const b = blanks[i];
    if (!ta || !b) return;
    const at = text.indexOf(b);
    if (at < 0) return;
    ta.focus({ preventScroll: true });
    ta.setSelectionRange(at, at + b.length);
    backRef.current?.querySelector(`[data-blank="${i}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    setCursor((i + 1) % blanks.length);
  };

  const saveNow = () => save.mutate(text, { onSuccess: () => { setVersionId(null); toast.success('Saved as a new version'); }, onError: fail });
  const switchVersion = (id: string) => {
    if (dirty && !window.confirm('You have unsaved changes in this version. Discard them?')) return;
    setVersionId(id);
  };
  const copy = async () => {
    try { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1600); } catch { toast.error("Couldn't copy. Select the text and copy it manually."); }
  };
  const fileName = `${approved ? 'reply' : 'DRAFT-reply'}-${n.reference_number ?? 'notice'}.txt`.replace(/[^\w.-]+/g, '_');

  return (
    <div className="space-y-4">
      {/* blanks */}
      {blanks.length > 0 ? (
        <div className="rounded-xl bg-warn-soft p-3.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-semibold text-warn-ink">{blanks.length} blank{blanks.length === 1 ? '' : 's'} only you can fill in</p>
            <Button size="sm" variant="secondary" onClick={() => focusBlank(cursor % blanks.length)} icon={<ChevronRight className="h-4 w-4" aria-hidden />}>Next blank</Button>
          </div>
          <p className="mt-0.5 text-xs text-warn-ink">We did not guess these facts. Click one to jump to it in the letter, then type over it.</p>
          <ul className="mt-2.5 flex flex-wrap gap-1.5">
            {blanks.map((b, i) => (
              <li key={b}><button type="button" onClick={() => focusBlank(i)} title={blankLabel(b)}
                className="max-w-[18rem] truncate rounded-full border border-warn bg-surface px-3 py-1 text-xs font-medium text-ink hover:bg-surface-2">{blankLabel(b)}</button></li>))}
          </ul>
        </div>
      ) : <Notice tone="good">No blanks left in this version.</Notice>}

      {/* editor */}
      <div className="rounded-2xl border border-line-strong bg-surface shadow-card transition-shadow focus-within:border-primary focus-within:shadow-[0_0_0_3px_var(--primary-soft)]">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-2.5">
          <div className="flex items-center gap-2 text-sm">
            {n.drafts.length > 1 ? (
              <select aria-label="Draft version" value={draft.id} onChange={(e) => switchVersion(e.target.value)} className="h-9 rounded-lg border border-line-strong bg-surface px-2 text-sm text-ink">
                {n.drafts.map((d) => <option key={d.id} value={d.id}>Version {d.version} · {d.author === 'ai' ? 'AI draft' : 'your edit'}</option>)}
              </select>
            ) : <span className="font-medium text-ink">Version {draft.version} · AI draft</span>}
            {!isLatest && <span className="text-xs text-ink-3">older version</span>}
            {dirty && <span className="text-xs font-medium text-warn-ink">Unsaved changes</span>}
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            <Button size="sm" variant="ghost" onClick={copy} icon={copied ? <Check className="h-4 w-4" aria-hidden /> : <Copy className="h-4 w-4" aria-hidden />}>{copied ? 'Copied' : 'Copy'}</Button>
            <Button size="sm" variant="ghost" onClick={() => download(fileName, text)} icon={<Download className="h-4 w-4" aria-hidden />}>Download</Button>
            {dirty && <Button size="sm" variant="ghost" onClick={() => setText(draft.reply_text)} icon={<RotateCcw className="h-4 w-4" aria-hidden />}>Discard</Button>}
            <Button size="sm" disabled={!canSave} loading={save.isPending} onClick={saveNow} icon={<Save className="h-4 w-4" aria-hidden />}>Save version</Button>
          </div>
        </div>

        <div className="relative min-h-[26rem]">
          <div ref={backRef} aria-hidden className={cn(textLayer, 'pointer-events-none min-h-[26rem] text-transparent')}>
            {text.split(BLANK).map((p, i) => {
              if (i % 2 === 0) return <React.Fragment key={i}>{p}</React.Fragment>;
              return <mark key={i} data-blank={blanks.indexOf(p)} className="rounded bg-warn-soft text-transparent shadow-[0_0_0_2px_var(--warn-soft),0_0_0_3px_var(--warn)]">{p}</mark>;
            })}
            {'\n '}
          </div>
          <textarea ref={taRef} aria-label="Reply letter" value={text} spellCheck={false}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 's') { e.preventDefault(); if (canSave && !save.isPending) saveNow(); } }}
            className={cn(textLayer, 'absolute inset-0 block h-full w-full resize-none overflow-hidden border-0 bg-transparent text-ink caret-primary focus:outline-none focus-visible:outline-none')} />
        </div>
      </div>

      {draft.points_to_confirm.length > 0 && (
        <details className="rounded-xl border border-line bg-surface px-4 py-3">
          <summary className="cursor-pointer text-sm font-medium text-ink">Check these facts before you send ({draft.points_to_confirm.length})</summary>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink-2">{draft.points_to_confirm.map((p) => <li key={p}>{p}</li>)}</ul>
        </details>
      )}

      {/* redraft */}
      <div className="flex flex-wrap items-end gap-2">
        <div className="min-w-[200px] flex-1">
          <label htmlFor="redraft" className="mb-1 block text-xs font-medium text-ink-2">Not quite right? Say how to change it</label>
          <Input id="redraft" value={instr} onChange={(e) => setInstr(e.target.value)} placeholder="e.g. make it firmer, or shorter" maxLength={300} disabled={dirty} />
        </div>
        <Button variant="secondary" loading={regen.isPending} disabled={dirty} icon={<RefreshCw className="h-4 w-4" aria-hidden />}
          onClick={() => regen.mutate(instr.trim() || undefined, { onSuccess: () => { setInstr(''); setVersionId(null); toast.success('New draft created'); }, onError: fail })}>Redraft</Button>
        {dirty && <p className="w-full text-xs text-ink-3">Save or discard your edits before asking for a new draft.</p>}
      </div>

      {/* lawyer gate */}
      <div className="rounded-xl border border-line bg-surface-2 p-4">
        <ol className="mb-3 flex flex-wrap gap-2" aria-label="Review status">
          {REVIEW.map((s, i) => (
            <li key={s.key} aria-current={i === reviewIdx ? 'step' : undefined}
              className={cn('flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs', i === reviewIdx ? 'border-primary bg-primary-soft font-semibold text-primary-ink' : i < reviewIdx ? 'border-good text-good-ink' : 'border-line-strong text-ink-3')}>
              {i < reviewIdx || (approved && i === reviewIdx) ? <Check className="h-3.5 w-3.5" aria-hidden /> : null}{s.label}
            </li>))}
        </ol>
        {!approved ? (
          <>
            <p className="mb-3 text-sm text-ink-2">Do not send this until a lawyer or advocate has read it and every blank is filled. Editing starts the review again.</p>
            <div className="flex flex-wrap gap-2">
              {n.review_status === 'draft' && <Button variant="secondary" loading={update.isPending} disabled={dirty} onClick={() => update.mutate({ review_status: 'ready_for_lawyer' }, { onError: fail })}>I have sent it to my lawyer</Button>}
              <Button icon={<ShieldCheck className="h-4 w-4" aria-hidden />} loading={update.isPending} disabled={blanks.length > 0 || dirty || !isLatest}
                onClick={() => update.mutate({ review_status: 'lawyer_approved' }, { onSuccess: () => toast.success('Marked as reviewed by your lawyer'), onError: fail })}>Mark as reviewed by lawyer</Button>
            </div>
            {(blanks.length > 0 || dirty || !isLatest) && <p className="mt-2 text-xs text-ink-3">{dirty ? 'Save your edits first.' : !isLatest ? 'Open the latest version to approve it.' : 'Fill in the blanks to unlock this.'}</p>}
          </>
        ) : (
          <div className="space-y-3">
            <Notice tone="good">Reviewed by your lawyer. This version is final and ready to send.</Notice>
            {open && <Button variant="secondary" loading={update.isPending} icon={<Check className="h-4 w-4" aria-hidden />}
              onClick={() => update.mutate({ status: 'closed' }, { onSuccess: () => toast.success('Marked as replied. The calendar reminder is done.'), onError: fail })}>I have sent it. Mark as replied</Button>}
          </div>
        )}
      </div>
    </div>
  );
};
