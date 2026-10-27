import React, { useMemo } from 'react';
import { FileText, ScanText } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { KeyQuote, NoticeDetail } from './api';

const KINDS: Record<KeyQuote['kind'], { label: string; mark: string; dot: string }> = {
  deadline: { label: 'Deadline', mark: 'bg-warn-soft decoration-warn', dot: 'bg-warn' },
  amount: { label: 'Amount', mark: 'bg-primary-soft decoration-primary', dot: 'bg-primary' },
  demand: { label: 'What they demand', mark: 'bg-critical-soft decoration-critical', dot: 'bg-critical' },
};

const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/** Finds the quote in the text ignoring line breaks, spacing and curly-vs-straight quotes. */
function locate(text: string, quote: string): [number, number] | null {
  const tokens = quote.trim().split(/\s+/).filter(Boolean);
  if (!tokens.length) return null;
  const pattern = tokens.map((t) => escapeRe(t).replace(/['‘’]/g, "['‘’]").replace(/["“”]/g, '["“”]')).join('\\s+');
  try {
    const m = new RegExp(pattern, 'i').exec(text);
    return m ? [m.index, m.index + m[0].length] : null;
  } catch {
    return null;
  }
}

interface Span { kind: KeyQuote['kind']; start: number; end: number }

export const NoticeText: React.FC<{ n: NoticeDetail; className?: string }> = ({ n, className }) => {
  const text = n.raw_text ?? '';
  const { spans, unplaced } = useMemo(() => {
    const found: Span[] = [];
    const missing: KeyQuote[] = [];
    for (const q of n.key_quotes) {
      const at = locate(text, q.text);
      if (at) found.push({ kind: q.kind, start: at[0], end: at[1] });
      else if (q.verified) missing.push(q);
    }
    found.sort((a, b) => a.start - b.start);
    const clean: Span[] = [];
    for (const s of found) if (!clean.length || s.start >= clean[clean.length - 1].end) clean.push(s);
    return { spans: clean, unplaced: missing };
  }, [n.key_quotes, text]);

  const pieces: React.ReactNode[] = [];
  let cursor = 0;
  spans.forEach((s) => {
    if (s.start > cursor) pieces.push(text.slice(cursor, s.start));
    pieces.push(<mark key={s.kind} id={`quote-${s.kind}`} className={cn('scroll-mt-24 rounded px-0.5 text-ink underline decoration-2 underline-offset-4', KINDS[s.kind].mark)}>{text.slice(s.start, s.end)}</mark>);
    cursor = s.end;
  });
  pieces.push(text.slice(cursor));

  const jump = (kind: string) => document.getElementById(`quote-${kind}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });

  return (
    <section aria-label="The notice" className={cn('flex min-h-0 flex-col rounded-2xl border border-line bg-surface shadow-card', className)}>
      <header className="border-b border-line px-5 py-3">
        <div className="flex items-center justify-between gap-3">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-ink"><FileText className="h-4 w-4 text-ink-3" aria-hidden />The notice</h2>
          {n.source_name && <span className="min-w-0 truncate text-xs text-ink-3">{n.source_name}</span>}
        </div>
        {spans.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5" aria-label="Jump to the key sentences">
            {spans.map((s) => (
              <button key={s.kind} type="button" onClick={() => jump(s.kind)} className="inline-flex min-h-[28px] items-center gap-1.5 rounded-full border border-line-strong px-2.5 text-xs font-medium text-ink-2 hover:bg-surface-2">
                <span className={cn('h-2 w-2 rounded-full', KINDS[s.kind].dot)} aria-hidden />{KINDS[s.kind].label}
              </button>
            ))}
          </div>
        )}
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
        {n.ocr_used && <p className="mb-3 flex items-start gap-1.5 rounded-lg bg-warn-soft p-2.5 text-xs text-warn-ink"><ScanText className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />Read from a scan. Please check names, dates and amounts against the original.</p>}
        {unplaced.map((q) => (
          <figure key={q.kind} className="mb-3 border-l-4 border-line-strong pl-3">
            <figcaption className="text-xs font-semibold text-ink-3">{KINDS[q.kind].label}</figcaption>
            <blockquote className="text-sm italic text-ink">&ldquo;{q.text}&rdquo;</blockquote>
          </figure>
        ))}
        {text ? <div className="whitespace-pre-wrap break-words font-serif text-[15px] leading-7 text-ink">{pieces}</div> : <p className="text-sm text-ink-2">The text of this notice is not available.</p>}
      </div>
    </section>
  );
};
