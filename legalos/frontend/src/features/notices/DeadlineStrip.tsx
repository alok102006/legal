import React from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, CalendarCheck, CalendarX2, Check, CheckCircle2, Gavel, HelpCircle, Scale, Zap } from 'lucide-react';
import { Button, Input } from '@/ui/primitives';
import { cn, formatDate } from '@/lib/utils';
import type { NoticeDetail } from './api';
import { BASIS_LABEL, countdown, dayDiff, TONE_FILL, TONE_INK, todayIso } from './lib';

/** received -> today -> reply-by (and the hearing, when there is one) on one line, with today's position as the marker that matters. */
const Timeline: React.FC<{ n: NoticeDetail }> = ({ n }) => {
  const c = countdown(n);
  const today = todayIso();
  const received = n.received_date ?? today;
  const due = n.response_deadline;
  if (!due) {
    return (
      <div>
        <p className="text-sm text-ink-2">{n.forthwith ? 'The notice asks for action immediately and gives no date.' : 'No reply date to count down to.'} Received {formatDate(received)}.</p>
        {n.hearing_date && <p className="mt-1 flex items-center gap-1.5 text-sm font-medium text-lavender-ink"><Gavel className="h-4 w-4" aria-hidden />Hearing on {formatDate(n.hearing_date)}</p>}
      </div>
    );
  }
  const hearing = n.hearing_date && n.hearing_date !== due ? n.hearing_date : null;
  const start = [received, today, due].reduce((a, b) => (b < a ? b : a));
  const end = [due, today, hearing ?? due].reduce((a, b) => (b > a ? b : a));
  const span = Math.max(1, dayDiff(start, end));
  const pos = (d: string) => Math.max(0, Math.min(100, (dayDiff(start, d) / span) * 100));
  const todayPos = pos(today);
  const dueDone = n.status === 'closed';
  const fill = dueDone ? TONE_FILL.good : TONE_FILL[c.tone];
  return (
    <div className="px-9 pb-1 pt-8" role="img" aria-label={`Received ${formatDate(received)}, today ${formatDate(today)}, reply by ${formatDate(due)}${hearing ? `, hearing ${formatDate(hearing)}` : ''}`}>
      <div className="relative h-2 rounded-full bg-line">
        <div className="absolute inset-y-0 left-0 rounded-full transition-all duration-500" style={{ width: `${todayPos}%`, background: fill }} />
        {/* received */}
        <span className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-surface-2 bg-ink-3" style={{ left: `${pos(received)}%` }} />
        {/* reply by */}
        <span className="absolute top-1/2 h-5 w-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-[3px] bg-surface-2" style={{ left: `${pos(due)}%`, borderColor: fill }} />
        {/* hearing */}
        {hearing && <span className="absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rotate-45 rounded-[3px] border-2 border-surface-2 bg-lavender-ink" style={{ left: `${pos(hearing)}%` }} />}
        {/* today */}
        <span className="absolute top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-surface-2 shadow-card" style={{ left: `${todayPos}%`, background: fill }} />
        <span className="absolute -top-6 -translate-x-1/2 whitespace-nowrap text-[11px] font-semibold uppercase tracking-[0.12em] text-ink" style={{ left: `${todayPos}%` }}>Today</span>
        {/* labels */}
        <span className={'absolute top-5 -translate-x-1/2 whitespace-nowrap text-center text-xs leading-tight text-ink-3'} style={{ left: `${pos(received)}%` }}>
          Received<br /><span className="font-medium tabular-nums text-ink-2">{formatDate(received)}</span>
        </span>
        <span className="absolute top-5 -translate-x-1/2 whitespace-nowrap text-center text-xs leading-tight text-ink-3" style={{ left: `${pos(due)}%` }}>
          Reply by<br /><span className={cn('font-semibold tabular-nums', dueDone ? 'text-ink-2' : TONE_INK[c.tone])}>{formatDate(due)}</span>
        </span>
        {hearing && (
          <span className="absolute top-14 -translate-x-1/2 whitespace-nowrap text-center text-xs leading-tight text-ink-3" style={{ left: `${pos(hearing)}%` }}>
            Hearing<br /><span className="font-semibold tabular-nums text-lavender-ink">{formatDate(hearing)}</span>
          </span>)}
      </div>
      <div className={hearing ? 'h-[4.5rem]' : 'h-10'} aria-hidden />
    </div>
  );
};

const Basis: React.FC<{ n: NoticeDetail }> = ({ n }) => {
  if (n.deadline_source === 'stated') {
    return n.deadline_verified
      ? <span className="inline-flex items-center gap-1 font-medium text-good-ink"><Check className="h-3.5 w-3.5" aria-hidden />Stated in the notice, found in the text</span>
      : <span className="inline-flex items-center gap-1 font-medium text-warn-ink"><HelpCircle className="h-3.5 w-3.5" aria-hidden />Stated in the notice, but check the original wording</span>;
  }
  if (n.deadline_source === 'statutory_default') {
    return <span className="inline-flex items-center gap-1 font-medium text-ink-2"><Scale className="h-3.5 w-3.5" aria-hidden />Counted from the law{n.deadline_rule ? `: ${n.deadline_rule}` : ''}</span>;
  }
  return <span className="inline-flex items-center gap-1 font-medium text-warn-ink"><HelpCircle className="h-3.5 w-3.5" aria-hidden />Unknown. We did not guess one.</span>;
};

/** Every date the deadline engine considered; the earliest one is the deadline. */
const BasisList: React.FC<{ n: NoticeDetail }> = ({ n }) => {
  const list = [...n.deadline_basis].sort((a, b) => a.due.localeCompare(b.due));
  if (list.length === 0) return null;
  return (
    <details className="mt-2 max-w-xl rounded-xl bg-surface px-3.5 py-2.5 shadow-card" open={list.length > 1}>
      <summary className="cursor-pointer text-xs font-semibold text-ink-2">{list.length > 1 ? `${list.length} dates considered. The earliest is the deadline.` : 'How this date was worked out'}</summary>
      <ul className="mt-2 space-y-2.5">
        {list.map((b, i) => (
          <li key={`${b.due}-${b.basis}-${i}`} className="flex items-start gap-3 text-sm">
            <span className="w-28 shrink-0 font-semibold tabular-nums text-ink">{formatDate(b.due)}</span>
            <span className="min-w-0 flex-1">
              <span className="text-xs font-medium text-ink-2">{BASIS_LABEL[b.basis] ?? b.basis}</span>
              {i === 0 && list.length > 1 && <span className="ml-2 rounded-full bg-primary px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-primary-on">earliest</span>}
              {b.verified && <Check className="ml-1.5 inline h-3.5 w-3.5 text-good-ink" aria-label="Found in the notice text" />}
              <span className="block text-ink-2">{b.explanation}</span>
              {b.citation && <span className="block text-xs text-ink-3">{b.citation}</span>}
            </span>
          </li>))}
      </ul>
    </details>
  );
};

export const DeadlineStrip: React.FC<{
  n: NoticeDetail; saving: boolean; onReceived: (iso: string) => void; onNoticeDate?: (iso: string) => void;
}> = ({ n, saving, onReceived, onNoticeDate }) => {
  const c = countdown(n);
  const open = n.status !== 'closed';
  const closed = !open;
  const overdue = open && (n.overdue || (n.days_left !== null && n.days_left < 0));
  const loud = open && (c.tone === 'critical' || c.tone === 'serious');
  const overdueBy = n.days_left !== null && n.days_left < 0 ? -n.days_left : null;
  return (
    <section aria-label="Reply deadline" className={cn('rounded-2xl bg-surface-2 p-5 sm:p-7', loud && (c.tone === 'critical' ? 'ring-1 ring-inset ring-critical/50' : 'ring-1 ring-inset ring-serious/50'))}>
      <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:gap-10">
        <div className="flex shrink-0 items-baseline gap-3 lg:w-48 lg:flex-col lg:items-start lg:gap-0">
          {closed ? (
            <span className="flex items-center gap-2 font-display text-4xl leading-none text-good-ink"><CheckCircle2 className="h-7 w-7" aria-hidden />Replied</span>
          ) : c.big !== null ? (
            <>
              <span className={cn('font-display text-7xl font-normal leading-[0.9] tabular-nums sm:text-8xl', TONE_INK[c.tone])}>{c.big}</span>
              <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-2 lg:mt-3">{c.caption}</span>
            </>
          ) : n.forthwith ? (
            <span className="font-display text-3xl leading-tight text-critical-ink">Reply immediately</span>
          ) : (
            <span className="font-display text-3xl leading-tight text-warn-ink">No deadline found</span>
          )}
        </div>
        <div className="min-w-0 flex-1"><Timeline n={n} /></div>
      </div>

      {overdue && (
        <p role="alert" className="mt-4 flex items-center gap-2 rounded-xl bg-critical-soft px-3.5 py-2.5 text-sm font-semibold text-critical-ink">
          <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden />
          {overdueBy !== null ? `Overdue by ${overdueBy} ${overdueBy === 1 ? 'day' : 'days'}.` : 'Overdue.'} Reply as soon as you can and tell your lawyer the date has passed.
        </p>)}
      {open && n.forthwith && (
        <p className="mt-4 flex items-center gap-2 rounded-xl bg-critical-soft px-3.5 py-2.5 text-sm font-semibold text-critical-ink">
          <Zap className="h-4 w-4 shrink-0" aria-hidden />Reply immediately. The notice asks for action "forthwith".
        </p>)}

      <div className="mt-5 flex flex-col gap-4 border-t border-line-strong/60 pt-5 text-sm md:flex-row md:items-start md:justify-between">
        <div className="min-w-0 space-y-1">
          {n.response_deadline && <p className="font-semibold text-ink">Reply by {new Date(`${n.response_deadline}T00:00:00`).toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}</p>}
          <p className="text-xs"><Basis n={n} /></p>
          {n.deadline_note && <p className="max-w-xl text-ink-2">{n.deadline_note}</p>}
          {n.hearing_date && <p className="flex items-center gap-1.5 text-xs font-medium text-lavender-ink"><Gavel className="h-3.5 w-3.5" aria-hidden />Hearing on {formatDate(n.hearing_date)}</p>}
          <BasisList n={n} />
          {n.notice_date && (
            <p className="flex items-center gap-1.5 pt-1 text-xs text-ink-3">
              {n.notice_date_verified
                ? <><Check className="h-3.5 w-3.5 text-good-ink" aria-hidden />Notice dated {formatDate(n.notice_date)}, found in the text</>
                : <><HelpCircle className="h-3.5 w-3.5 text-warn-ink" aria-hidden />Notice dated {formatDate(n.notice_date)}, not found in the text. Check the original.</>}
            </p>)}
          {n.date_corrections.length > 0 && <p className="max-w-xl text-xs text-ink-3">We corrected: {n.date_corrections.join('; ')}</p>}
          <p className="pt-1">
            {n.in_calendar && open
              ? <span className="inline-flex items-center gap-1.5 font-medium text-good-ink"><CalendarCheck className="h-4 w-4" aria-hidden />Added to calendar · <Link to="/compliance" className="underline">view</Link></span>
              : n.in_calendar
                ? <span className="inline-flex items-center gap-1.5 text-ink-3"><CalendarCheck className="h-4 w-4" aria-hidden />Calendar reminder completed</span>
                : <span className="inline-flex items-center gap-1.5 text-ink-3"><CalendarX2 className="h-4 w-4" aria-hidden />Not in the calendar: there is no date to remind you of</span>}
          </p>
        </div>

        <div className="flex shrink-0 flex-col gap-3 md:w-64">
          {n.needs_notice_date && onNoticeDate && (
            <div className="rounded-xl bg-warn-soft p-3.5">
              <label htmlFor="notice-on" className="block text-xs font-semibold text-warn-ink">Date on the notice</label>
              <Input id="notice-on" type="date" className="mt-1.5 h-9 bg-surface" max={todayIso()} value={n.notice_date ?? ''} disabled={saving}
                onChange={(e) => e.target.value && onNoticeDate(e.target.value)} />
              <p className="mt-2 text-xs text-warn-ink">The reply window counts from the date printed on the notice, and we could not read it. Type it in and the reply date is worked out again.</p>
            </div>)}
          <div className={cn('rounded-xl p-3.5', n.needs_received_date ? 'bg-warn-soft' : 'bg-surface shadow-card')}>
            <label htmlFor="received-on" className={cn('block text-xs font-semibold', n.needs_received_date ? 'text-warn-ink' : 'text-ink-2')}>Day you received it</label>
            <Input id="received-on" type="date" className="mt-1.5 h-9 bg-surface" max={todayIso()} value={n.received_date ?? ''} disabled={saving}
              onChange={(e) => e.target.value && onReceived(e.target.value)} />
            {n.needs_received_date
              ? (
                <>
                  <p className="mt-2 text-xs text-warn-ink">{n.notice_date ? 'The notice does not say when you got it.' : 'This notice carries no date.'} We counted from the date above. Change it if you received it on another day.</p>
                  <Button size="sm" variant="secondary" className="mt-3 w-full" loading={saving} onClick={() => n.received_date && onReceived(n.received_date)}>That date is right</Button>
                </>)
              : <p className="mt-1.5 text-xs text-ink-3">Change it and the reply date and calendar move with it.</p>}
          </div>
        </div>
      </div>
    </section>
  );
};
