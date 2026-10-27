import React from 'react';
import { Link } from 'react-router-dom';
import { CalendarCheck, CalendarX2, Check, CheckCircle2, HelpCircle, Scale } from 'lucide-react';
import { Button, Input } from '@/ui/primitives';
import { cn, formatDate } from '@/lib/utils';
import type { NoticeDetail } from './api';
import { countdown, dayDiff, TONE_FILL, TONE_INK, todayIso } from './lib';

/** received -> today -> reply-by on one line, with today's position as the marker that matters. */
const Timeline: React.FC<{ n: NoticeDetail }> = ({ n }) => {
  const c = countdown(n);
  const today = todayIso();
  const received = n.received_date ?? today;
  const due = n.response_deadline;
  if (!due) {
    return <p className="text-sm text-ink-2">No reply date to count down to. Received {formatDate(received)}.</p>;
  }
  const start = received < today ? received : today;
  const end = due > today ? due : today;
  const span = Math.max(1, dayDiff(start, end));
  const pos = (d: string) => Math.max(0, Math.min(100, (dayDiff(start, d) / span) * 100));
  const todayPos = pos(today);
  const dueDone = n.status === 'closed';
  const fill = dueDone ? TONE_FILL.good : TONE_FILL[c.tone];
    return (
    <div className="px-9 pb-1 pt-7" role="img" aria-label={`Received ${formatDate(received)}, today ${formatDate(today)}, reply by ${formatDate(due)}`}>
      <div className="relative h-2 rounded-full bg-surface-2">
        <div className="absolute inset-y-0 left-0 rounded-full transition-all duration-500" style={{ width: `${todayPos}%`, background: fill }} />
        {/* received */}
        <span className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-surface bg-ink-3" style={{ left: `${pos(received)}%` }} />
        {/* reply by */}
        <span className="absolute top-1/2 h-5 w-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-[3px] bg-surface" style={{ left: `${pos(due)}%`, borderColor: fill }} />
        {/* today */}
        <span className="absolute top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-surface shadow" style={{ left: `${todayPos}%`, background: fill }} />
        <span className="absolute -top-6 -translate-x-1/2 whitespace-nowrap text-xs font-semibold text-ink" style={{ left: `${todayPos}%` }}>Today</span>
        {/* labels */}
        <span className={'absolute top-5 -translate-x-1/2 whitespace-nowrap text-center text-xs leading-tight text-ink-3'} style={{ left: `${pos(received)}%` }}>
          Received<br /><span className="font-medium text-ink-2">{formatDate(received)}</span>
        </span>
        <span className="absolute top-5 -translate-x-1/2 whitespace-nowrap text-center text-xs leading-tight text-ink-3" style={{ left: `${pos(due)}%` }}>
          Reply by<br /><span className={cn('font-semibold', dueDone ? 'text-ink-2' : TONE_INK[c.tone])}>{formatDate(due)}</span>
        </span>
      </div>
      <div className="h-10" aria-hidden />
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

export const DeadlineStrip: React.FC<{ n: NoticeDetail; saving: boolean; onReceived: (iso: string) => void }> = ({ n, saving, onReceived }) => {
  const c = countdown(n);
  const open = n.status !== 'closed';
  const closed = !open;
  const loud = open && (c.tone === 'critical' || c.tone === 'serious');
  return (
    <section aria-label="Reply deadline" className={cn('rounded-2xl border bg-surface p-5 shadow-card sm:p-6', loud ? (c.tone === 'critical' ? 'border-critical' : 'border-serious') : 'border-line')}>
      <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:gap-10">
        <div className="flex shrink-0 items-baseline gap-3 lg:w-48 lg:flex-col lg:items-start lg:gap-0">
          {closed ? (
            <span className="flex items-center gap-2 text-2xl font-bold text-good-ink"><CheckCircle2 className="h-7 w-7" aria-hidden />Replied</span>
          ) : c.big !== null ? (
            <>
              <span className={cn('text-6xl font-bold leading-none tabular-nums sm:text-7xl', TONE_INK[c.tone])}>{c.big}</span>
              <span className="text-base font-medium text-ink-2">{c.caption}</span>
            </>
          ) : (
            <span className="text-2xl font-bold text-warn-ink">No deadline found</span>
          )}
        </div>
        <div className="min-w-0 flex-1"><Timeline n={n} /></div>
      </div>

      <div className="mt-4 flex flex-col gap-3 border-t border-line pt-4 text-sm md:flex-row md:items-start md:justify-between">
        <div className="min-w-0 space-y-1">
          {n.response_deadline && <p className="font-semibold text-ink">Reply by {new Date(`${n.response_deadline}T00:00:00`).toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}</p>}
          <p className="text-xs"><Basis n={n} /></p>
          {n.deadline_note && <p className="max-w-xl text-ink-2">{n.deadline_note}</p>}
          <p className="pt-1">
            {n.in_calendar && open
              ? <span className="inline-flex items-center gap-1.5 font-medium text-good-ink"><CalendarCheck className="h-4 w-4" aria-hidden />Added to calendar · <Link to="/compliance" className="underline">view</Link></span>
              : n.in_calendar
                ? <span className="inline-flex items-center gap-1.5 text-ink-3"><CalendarCheck className="h-4 w-4" aria-hidden />Calendar reminder completed</span>
                : <span className="inline-flex items-center gap-1.5 text-ink-3"><CalendarX2 className="h-4 w-4" aria-hidden />Not in the calendar: there is no date to remind you of</span>}
          </p>
        </div>

        <div className={cn('shrink-0 rounded-xl p-3 md:w-64', n.needs_received_date ? 'bg-warn-soft' : 'bg-surface-2')}>
          <label htmlFor="received-on" className={cn('block text-xs font-semibold', n.needs_received_date ? 'text-warn-ink' : 'text-ink-2')}>Day you received it</label>
          <Input id="received-on" type="date" className="mt-1 h-9 bg-surface" max={todayIso()} value={n.received_date ?? ''} disabled={saving}
            onChange={(e) => e.target.value && onReceived(e.target.value)} />
          {n.needs_received_date
            ? (
              <>
                <p className="mt-2 text-xs text-warn-ink">{n.notice_date ? 'The notice does not say when you got it.' : 'This notice carries no date.'} We counted from the date above. Change it if you received it on another day.</p>
                <Button size="sm" variant="secondary" className="mt-2 w-full" loading={saving} onClick={() => n.received_date && onReceived(n.received_date)}>That date is right</Button>
              </>)
            : <p className="mt-1.5 text-xs text-ink-3">Change it and the reply date and calendar move with it.</p>}
        </div>
      </div>
    </section>
  );
};
