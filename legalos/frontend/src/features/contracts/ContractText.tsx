import React, { memo, useEffect, useMemo, useRef } from 'react';
import { cn } from '@/lib/utils';
import { SEVERITY_ORDER, type Severity } from '@/ui/risk';
import { SEV_STYLE } from './components';
import type { Finding, Segment } from './api';

/* The reading surface: the contract text as a calm document, with the clauses the AI flagged marked inline. */

export interface TextFocus {
  segmentId: string | null;
  findingId: string | null;
  quote: string | null;       // passage to flash when the jump came from a chat citation
  nonce: number;
}

interface Mark { start: number; end: number; findingId: string | null; sev: Severity | 'flash' }

const escapeRegExp = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/** Whitespace/quote-style tolerant search for a quoted passage inside clause text. */
function findRange(text: string, quote: string): [number, number] | null {
  const words = quote.trim().split(/\s+/).filter(Boolean);
  if (words.length < 3) return null;
  const toPattern = (ws: string[]) => ws
    .map((w) => escapeRegExp(w).replace(/['‘’]/g, "['‘’]").replace(/["“”]/g, '["“”]'))
    .join('\\s+');
  for (const attempt of [words, words.slice(0, Math.max(4, Math.ceil(words.length / 2)))]) {
    try {
      const m = new RegExp(toPattern(attempt), 'i').exec(text);
      if (m) return [m.index, m.index + m[0].length];
    } catch { /* invalid pattern: try the next shorter attempt */ }
  }
  return null;
}

const MARK_STYLE: Record<Severity | 'flash', { base: string; active: string }> = {
  critical: { base: `${SEV_STYLE.critical.mark} ${SEV_STYLE.critical.markBar}`, active: SEV_STYLE.critical.markActive },
  high: { base: `${SEV_STYLE.high.mark} ${SEV_STYLE.high.markBar}`, active: SEV_STYLE.high.markActive },
  medium: { base: `${SEV_STYLE.medium.mark} ${SEV_STYLE.medium.markBar}`, active: SEV_STYLE.medium.markActive },
  low: { base: `${SEV_STYLE.low.mark} ${SEV_STYLE.low.markBar}`, active: SEV_STYLE.low.markActive },
  flash: { base: 'bg-primary-soft border-primary ring-1 ring-primary/30', active: 'bg-primary-soft' },
};

const sevRank = (s: Severity) => SEVERITY_ORDER.indexOf(s);

function pulse(el: Element | null | undefined) {
  if (!el || typeof (el as HTMLElement).animate !== 'function') return;
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return;
  try {
    (el as HTMLElement).animate(
      [{ boxShadow: '0 0 0 0 color-mix(in srgb, var(--ink-3) 55%, transparent)' }, { boxShadow: '0 0 0 10px color-mix(in srgb, var(--ink-3) 0%, transparent)' }],
      { duration: 850, iterations: 2, easing: 'ease-out' },
    );
  } catch { /* cosmetic only */ }
}

/** Lines -> paragraphs. PDFs wrap lines at the page width, so those are re-joined into sentences. */
function paragraphRanges(text: string, joinWrapped: boolean, from = 0): [number, number][] {
  const lines: [number, number][] = [];
  let pos = from;
  for (const ln of text.slice(from).split('\n')) {
    if (ln.trim()) lines.push([pos, pos + ln.length]);
    pos += ln.length + 1;
  }
  if (!joinWrapped) return lines;
  const out: [number, number][] = [];
  for (const [a, b] of lines) {
    const prev = out[out.length - 1];
    const prevText = prev ? text.slice(prev[0], prev[1]).trimEnd() : '';
    const startsItem = /^(\(?([a-z]|[ivx]{1,4}|\d{1,2})\)|\d{1,2}(\.\d{1,2})+[.)]?\s|\d{1,2}[.)]\s|[-•*]\s)/i.test(text.slice(a, b).trimStart());
    if (!prev || /[.:;!?]["”’)]?$/.test(prevText) || startsItem) out.push([a, b]);
    else prev[1] = b;
  }
  return out;
}

const Paragraph: React.FC<{ text: string; range: [number, number]; marks: Mark[]; activeId: string | null; onMark: (id: string | null) => void }> = ({ text, range: [a, b], marks, activeId, onMark }) => {
  const nodes: React.ReactNode[] = [];
  let pos = a;
  for (const m of marks) {
    if (m.end <= a || m.start >= b) continue;
    const s = Math.max(m.start, a);
    const e = Math.min(m.end, b);
    if (s > pos) nodes.push(text.slice(pos, s));
    nodes.push(
      <mark
        key={`${m.findingId ?? 'flash'}-${s}`}
        data-finding={m.findingId ?? 'flash'}
        role={m.findingId ? 'button' : undefined}
        tabIndex={m.findingId ? 0 : undefined}
        onClick={m.findingId ? () => onMark(m.findingId) : undefined}
        onKeyDown={m.findingId ? (ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); onMark(m.findingId); } } : undefined}
        className={cn('rounded-[4px] border-l-2 px-1 py-px text-ink transition-colors [box-decoration-break:clone]', m.findingId && 'cursor-pointer', m.findingId && m.findingId === activeId ? MARK_STYLE[m.sev].active : MARK_STYLE[m.sev].base, m.findingId && m.findingId === activeId && MARK_STYLE[m.sev].base.split(' ')[1])}
      >{text.slice(s, e)}</mark>,
    );
    pos = e;
  }
  if (pos < b) nodes.push(text.slice(pos, b));
  return <p className="mt-2.5">{nodes}</p>;
};

const SegmentBlock = memo(function SegmentBlock({ seg, findings, flash, activeId, joinWrapped, pageMark, dim, onMark, register }: {
  seg: Segment;
  findings: Finding[];
  flash: string | null;
  activeId: string | null;
  joinWrapped: boolean;
  pageMark: number | null;
  dim: boolean;
  onMark: (id: string | null) => void;
  register: (id: string, el: HTMLElement | null) => void;
}) {
  const marks = useMemo(() => {
    const cand: (Mark & { prio: number })[] = [];
    if (flash) {
      const r = findRange(seg.text, flash);
      if (r) cand.push({ start: r[0], end: r[1], findingId: null, sev: 'flash', prio: -1 });
    }
    for (const f of findings) {
      if (!f.quote || !f.verified) continue;
      const r = findRange(seg.text, f.quote);
      if (r) cand.push({ start: r[0], end: r[1], findingId: f.id, sev: f.severity, prio: sevRank(f.severity) });
    }
    cand.sort((x, y) => x.prio - y.prio);
    const kept: Mark[] = [];
    for (const c of cand) if (!kept.some((k) => c.start < k.end && c.end > k.start)) kept.push(c);
    return kept.sort((x, y) => x.start - y.start);
  }, [seg.text, findings, flash]);

  const top = findings.length ? findings.reduce((a, b) => (sevRank(b.severity) < sevRank(a.severity) ? b : a)).severity : null;
  const nl = seg.text.indexOf('\n');
  const first = (nl === -1 ? '' : seg.text.slice(0, nl)).trim();
  const headed = nl !== -1 && first.length > 0 && first.length <= 110 && !/[.;,]$/.test(first);
  const body = useMemo(() => paragraphRanges(seg.text, joinWrapped, headed ? nl + 1 : 0), [seg.text, joinWrapped, headed, nl]);

  return (
    <>
      {pageMark !== null && (
        <div className="my-8 flex items-center gap-3 font-sans text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-3 first:mt-0" aria-label={`Page ${pageMark}`}>
          <span className="h-px flex-1 bg-line" /><span>Page {pageMark}</span><span className="h-px flex-1 bg-line" />
        </div>
      )}
      <section
        id={`seg-${seg.seg_id}`}
        ref={(el) => register(seg.seg_id, el)}
        aria-label={seg.heading}
        className={cn(
          '-ml-4 mb-5 rounded-r-lg border-l-2 py-1 pl-4 transition-colors',
          top ? SEV_STYLE[top].bar : 'border-transparent',
          top && marks.length === 0 && 'bg-surface-2',
          dim && 'opacity-60',
        )}
      >
        {headed && <h3 className="font-serif text-[1.05rem] font-semibold leading-snug text-ink">{first}</h3>}
        {body.map((r) => <Paragraph key={r[0]} text={seg.text} range={r} marks={marks} activeId={activeId} onMark={onMark} />)}
      </section>
    </>
  );
});

export const ContractText: React.FC<{
  segments: Segment[];
  findings: Finding[];                 // all findings; only open ones anchored to a clause are drawn
  hasPages: boolean;
  reviewedSegments: number | null;     // set when a long contract was only partly read
  focus: TextFocus | null;
  activeId?: string | null;            // the finding currently selected in the rail: its highlight reads stronger
  onMark: (findingId: string | null) => void;
}> = ({ segments, findings, hasPages, reviewedSegments, focus, activeId = null, onMark }) => {
  const refs = useRef<Record<string, HTMLElement | null>>({});
  const register = useRef((id: string, el: HTMLElement | null) => { refs.current[id] = el; }).current;

  const bySegment = useMemo(() => {
    const m = new Map<string, Finding[]>();
    for (const f of findings) {
      if (f.status !== 'open' || !f.segment_id || f.source === 'missing') continue;
      const arr = m.get(f.segment_id) ?? [];
      arr.push(f);
      m.set(f.segment_id, arr);
    }
    return m;
  }, [findings]);

  useEffect(() => {
    if (!focus) return;
    const seg = focus.segmentId ? refs.current[focus.segmentId] : null;
    const mark = focus.findingId
      ? seg?.querySelector(`mark[data-finding="${CSS.escape(focus.findingId)}"]`)
      : seg?.querySelector('mark[data-finding="flash"]');
    const target = (mark ?? seg) as HTMLElement | null;
    if (!target) return;
    target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    pulse(mark ?? seg);
  }, [focus]);

  const empty: Finding[] = useMemo(() => [], []);
  let prevPage: number | null = null;

  return (
    <article className="mx-auto w-full max-w-[44rem] rounded-2xl border border-line bg-surface px-6 py-8 font-serif text-[15px] leading-7 text-ink shadow-card sm:px-14 sm:py-14" aria-label="Contract text">
      {segments.map((s, i) => {
        const pm = hasPages && s.page_start && s.page_start !== prevPage ? s.page_start : null;
        if (hasPages && s.page_start) prevPage = s.page_start;
        const cut = reviewedSegments !== null && i === reviewedSegments;
        return (
          <React.Fragment key={s.seg_id}>
            {cut && (
              <div className="my-8 rounded-lg border border-dashed border-line-strong bg-surface-2 px-4 py-3 text-center font-sans text-sm text-ink-2" role="note">
                Nothing below this line was reviewed. The contract is longer than we can read in one pass.
              </div>
            )}
            <SegmentBlock
              seg={s}
              findings={bySegment.get(s.seg_id) ?? empty}
              flash={focus && focus.segmentId === s.seg_id && !focus.findingId ? focus.quote : null}
              activeId={activeId}
              joinWrapped={hasPages}
              pageMark={pm}
              dim={reviewedSegments !== null && i >= reviewedSegments}
              onMark={onMark}
              register={register}
            />
          </React.Fragment>
        );
      })}
    </article>
  );
};
