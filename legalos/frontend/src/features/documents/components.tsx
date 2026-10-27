/** Chat building blocks: message rendering with citation markers, the source panel, and the composer. */
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import * as Dialog from '@radix-ui/react-dialog';
import { ArrowUp, Check, FileText, HelpCircle, Loader2, Square, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { Citation, Source, Turn } from './api';

/* ------------------------------------------------------------------ citation markers */

const MARKER = /\[(C\d+)\]/g;

/** Renders answer text; each [C1] marker becomes a small numbered chip that opens the source. */
export const AnswerText: React.FC<{ text: string; sources: Source[]; citations: Citation[]; onOpen: (marker: string) => void }> = ({ text, sources, citations, onOpen }) => {
  const known = useMemo(() => new Set(sources.map((s) => s.marker)), [sources]);
  const verifiedBy = useMemo(() => new Map(citations.map((c) => [c.marker, c.verified])), [citations]);
  const parts: React.ReactNode[] = [];
  let last = 0; let m: RegExpExecArray | null;
  text = text.replace(/(\[C\d+\])\s+(?=[.,;:!?])/g, '$1');      // "[C1] ." → "[C1]."
  MARKER.lastIndex = 0;
  while ((m = MARKER.exec(text))) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const marker = m[1];
    if (known.has(marker)) {
      const n = marker.slice(1);
      const ok = verifiedBy.get(marker) !== false;
      parts.push(
        <button key={`${marker}-${m.index}`} type="button" onClick={() => onOpen(marker)} aria-label={`Source ${n}`}
          className={cn('mx-0.5 inline-flex h-5 min-w-[1.25rem] translate-y-[-1px] items-center justify-center rounded-md border px-1 align-middle text-[11px] font-semibold leading-none transition-colors',
            ok ? 'border-primary/30 bg-primary-soft text-primary-ink hover:bg-primary hover:text-primary-on' : 'border-warn/40 bg-warn-soft text-warn-ink')}>{n}</button>,
      );
    }
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return <p className="whitespace-pre-wrap text-[15px] leading-7 text-ink">{parts}</p>;
};

/* ------------------------------------------------------------------ messages */

export const UserMessage: React.FC<{ text: string }> = ({ text }) => (
  <div className="flex justify-end">
    <div className="max-w-[85%] rounded-2xl rounded-br-md bg-surface-2 px-4 py-2.5 text-[15px] leading-7 text-ink">
      <p className="whitespace-pre-wrap">{text}</p>
    </div>
  </div>
);

const SourceChip: React.FC<{ s: Source; verified: boolean | undefined; onClick: () => void }> = ({ s, verified, onClick }) => (
  <button type="button" onClick={onClick} className="flex max-w-full items-center gap-1.5 rounded-lg border border-line bg-surface px-2.5 py-1.5 text-left text-xs text-ink-2 hover:border-line-strong hover:bg-surface-2">
    <span className="flex h-4 min-w-[1rem] items-center justify-center rounded bg-primary-soft px-1 text-[10px] font-semibold text-primary-ink" aria-hidden>{s.marker.slice(1)}</span>
    <span className="truncate font-medium text-ink">{s.document_title}</span>
    {s.page ? <span className="shrink-0 text-ink-3">p. {s.page}</span> : null}
    {verified === true && <Check className="h-3.5 w-3.5 shrink-0 text-good-ink" aria-label="Quote found in the document" />}
    {verified === false && <HelpCircle className="h-3.5 w-3.5 shrink-0 text-warn-ink" aria-label="Quote could not be matched" />}
  </button>
);

export const AssistantMessage: React.FC<{ turn: Turn; onOpen: (marker: string) => void }> = ({ turn, onOpen }) => {
  const cited = useMemo(() => {
    const byMarker = new Map(turn.citations.map((c) => [c.marker, c.verified]));
    return turn.sources.filter((s) => byMarker.has(s.marker)).map((s) => ({ s, verified: byMarker.get(s.marker) }));
  }, [turn]);
  const notFound = turn.found_in_documents === false;
  return (
    <div className="flex gap-3">
      <span className="mt-1 hidden h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary text-primary-on sm:flex" aria-hidden><FileText className="h-3.5 w-3.5" /></span>
      <div className="min-w-0 flex-1">
        <AnswerText text={turn.content} sources={turn.sources} citations={turn.citations} onOpen={onOpen} />
        {notFound && (
          <p className="mt-2 inline-flex items-center gap-1.5 rounded-lg bg-warn-soft px-2.5 py-1 text-xs font-medium text-warn-ink"><HelpCircle className="h-3.5 w-3.5" aria-hidden />Not covered by your documents</p>
        )}
        {cited.length > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {cited.map(({ s, verified }) => <SourceChip key={s.marker} s={s} verified={verified} onClick={() => onOpen(s.marker)} />)}
            {turn.confidence !== null && turn.confidence !== undefined && !notFound && (
              <span className="ml-auto text-xs text-ink-3" title="How well the quoted passages were matched in the documents">Confidence {turn.confidence}%</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export const PendingMessage: React.FC<{ stage: 'sending' | 'searching' | 'writing'; text: string }> = ({ stage, text }) => (
  <div className="flex gap-3">
    <span className="mt-1 hidden h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary text-primary-on sm:flex" aria-hidden><FileText className="h-3.5 w-3.5" /></span>
    <div className="min-w-0 flex-1" aria-live="polite">
      {text ? <p className="whitespace-pre-wrap text-[15px] leading-7 text-ink">{text}<span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-ink-3 align-middle" aria-hidden /></p>
        : <p className="flex items-center gap-2 text-sm text-ink-2"><Loader2 className="h-4 w-4 animate-spin" aria-hidden />{stage === 'searching' ? 'Searching your documents…' : stage === 'writing' ? 'Writing the answer…' : 'Sending…'}</p>}
    </div>
  </div>
);

/* ------------------------------------------------------------------ source panel */

function highlight(text: string, quote: string): React.ReactNode {
  const norm = (s: string) => s.replace(/\s+/g, ' ').trim();
  const t = norm(text); const q = norm(quote);
  if (!q) return t;
  const i = t.toLowerCase().indexOf(q.toLowerCase());
  if (i < 0) return t;
  return <>{t.slice(0, i)}<mark className="rounded bg-warn-soft px-0.5 text-ink">{t.slice(i, i + q.length)}</mark>{t.slice(i + q.length)}</>;
}

export const SourcePanel: React.FC<{ turn: Turn | null; marker: string | null; onClose: () => void }> = ({ turn, marker, onClose }) => {
  const open = !!turn && !!marker;
  const s = turn?.sources.find((x) => x.marker === marker) ?? null;
  const c = turn?.citations.find((x) => x.marker === marker) ?? null;
  const body = s && (
    <div className="space-y-4">
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-3">Source {s.marker.slice(1)}</p>
        <Link to={`/documents/${s.document_id}`} className="mt-1 block text-base font-semibold text-ink hover:underline">{s.document_title}</Link>
        <p className="text-xs text-ink-3">{[s.section, s.page ? `Page ${s.page}` : null].filter(Boolean).join(' · ')}</p>
      </div>
      {c && (
        <p className={cn('flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium', c.verified ? 'bg-good-soft text-good-ink' : 'bg-warn-soft text-warn-ink')}>
          {c.verified ? <><Check className="h-3.5 w-3.5" aria-hidden />{c.exact ? 'Quote found word for word' : 'Quote found (minor wording differences)'}</> : <><HelpCircle className="h-3.5 w-3.5" aria-hidden />This wording was not found in the passage — read the original</>}
        </p>
      )}
      <div className="rounded-2xl bg-surface-2 p-4 text-sm leading-6 text-ink-2">{highlight(s.text, c?.verified ? c.quote : '')}</div>
      <p className="text-xs text-ink-3">Found by {s.via.includes('keyword') && s.via.includes('vector') ? 'exact words and meaning' : s.via.includes('keyword') ? 'exact words' : 'meaning'}{s.via.includes('rerank') ? ', then re-checked against your question' : ''}.</p>
    </div>
  );
  // a sheet over everything on every screen size, so it never competes with the Library panel or its floating buttons
  return (
    <Dialog.Root open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-[60] bg-black/30" />
        <Dialog.Content className="fixed inset-x-0 bottom-0 z-[70] mx-auto max-h-[80vh] w-full max-w-2xl overflow-y-auto rounded-t-3xl bg-surface p-6 shadow-float" aria-label="Source" aria-describedby={undefined}>
          <div className="mb-4 flex items-center justify-between"><Dialog.Title className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-2">Where this comes from</Dialog.Title><Dialog.Close asChild><button className="rounded-full p-1.5 text-ink-2 hover:bg-surface-2" aria-label="Close source"><X className="h-4 w-4" aria-hidden /></button></Dialog.Close></div>
          {body}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
};

/* ------------------------------------------------------------------ composer */

export const Composer: React.FC<{
  onSend: (text: string) => void; onStop?: () => void; busy: boolean; disabled?: boolean; placeholder?: string; autoFocus?: boolean; scope?: React.ReactNode;
}> = ({ onSend, onStop, busy, disabled, placeholder, autoFocus, scope }) => {
  const [text, setText] = useState('');
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => { if (autoFocus) ref.current?.focus(); }, [autoFocus]);
  useEffect(() => {
    const el = ref.current; if (!el) return;
    el.style.height = '0px'; el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [text]);
  const submit = () => {
    const t = text.trim();
    if (t.length < 2 || busy || disabled) return;
    onSend(t); setText('');
  };
  return (
    <form onSubmit={(e) => { e.preventDefault(); submit(); }} className="mx-auto w-full max-w-3xl">
      {scope && <div className="mb-1.5 flex items-center gap-2 px-1 text-xs text-ink-3">{scope}</div>}
      <div className={cn('flex items-end gap-2 rounded-2xl border bg-surface p-2 pl-4 shadow-card transition-colors focus-within:border-primary', disabled ? 'border-line opacity-70' : 'border-line-strong')}>
        <label htmlFor="ask-documents" className="sr-only">Ask a question about your documents</label>
        <textarea id="ask-documents" ref={ref} value={text} onChange={(e) => setText(e.target.value)} rows={1} disabled={disabled}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); } }}
          placeholder={placeholder ?? 'Ask anything about your documents…'}
          className="max-h-[200px] min-h-[28px] flex-1 resize-none bg-transparent py-1.5 text-[15px] leading-7 text-ink outline-none placeholder:text-ink-3" />
        {busy && onStop ? (
          <button type="button" onClick={onStop} className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-ink text-app hover:opacity-90" aria-label="Stop"><Square className="h-4 w-4" aria-hidden /></button>
        ) : (
          <button type="submit" disabled={text.trim().length < 2 || busy || disabled} className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-on transition-opacity hover:bg-primary-hover disabled:opacity-40" aria-label="Send">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <ArrowUp className="h-4 w-4" aria-hidden />}
          </button>
        )}
      </div>
      <p className="mt-1.5 px-1 text-center text-[11px] text-ink-3">Answers come only from your documents, with the page quoted. Decision support, not legal advice.</p>
    </form>
  );
};
