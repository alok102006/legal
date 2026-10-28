/** Building blocks of the year planner: the 12-month strip, the "next up" hero and the obligation rows. */
import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Check, CheckCircle2, ChevronDown, Circle, ExternalLink, FileSignature, FileText, Gavel, Hourglass, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { toFriendlyError } from '@/api/client';
import { Button, Notice } from '@/ui/primitives';
import { ConfirmDialog } from '@/ui/overlays';
import { cn, formatDate, formatINR, plural } from '@/lib/utils';
import { useDeleteTask, useToggleDone, type ComplianceTask, type TaskState } from './api';

/* ------------------------------------------------------------------ dates */

export const parseDay = (iso: string) => new Date(`${iso}T00:00:00`);
export const monthKeyOf = (iso: string) => iso.slice(0, 7);
export const keyFor = (y: number, m0: number) => `${y}-${String(m0 + 1).padStart(2, '0')}`;
export const monthName = (key: string, style: 'long' | 'short' = 'long') =>
  new Date(`${key}-01T00:00:00`).toLocaleDateString('en-IN', { month: style });
export const monthTitle = (key: string) => new Date(`${key}-01T00:00:00`).toLocaleDateString('en-IN', { month: 'long', year: 'numeric' });

export interface MonthCol { key: string; short: string; year: number; isNow: boolean }

export function buildMonths(today: Date, count = 12): MonthCol[] {
  return Array.from({ length: count }, (_, i) => {
    const d = new Date(today.getFullYear(), today.getMonth() + i, 1);
    const key = keyFor(d.getFullYear(), d.getMonth());
    return { key, short: monthName(key, 'short'), year: d.getFullYear(), isNow: i === 0 };
  });
}

/** Monday of the week containing `d`. */
const weekStart = (d: Date) => { const x = new Date(d); x.setDate(x.getDate() - ((x.getDay() + 6) % 7)); x.setHours(0, 0, 0, 0); return x; };
const dayMonth = (d: Date) => d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });

export function weekLabel(start: Date, today: Date): string {
  const thisWeek = weekStart(today).getTime();
  const diff = Math.round((start.getTime() - thisWeek) / (7 * 86400000));
  if (diff === 0) return 'This week';
  if (diff === 1) return 'Next week';
  const end = new Date(start); end.setDate(end.getDate() + 6);
  return start.getMonth() === end.getMonth() ? `${start.getDate()} - ${dayMonth(end)}` : `${dayMonth(start)} - ${dayMonth(end)}`;
}

export function groupByWeek(tasks: ComplianceTask[], today: Date): { key: string; label: string; items: ComplianceTask[] }[] {
  const m = new Map<number, ComplianceTask[]>();
  tasks.forEach((t) => {
    if (!t.due_date) return;
    const k = weekStart(parseDay(t.due_date)).getTime();
    m.set(k, [...(m.get(k) ?? []), t]);
  });
  return Array.from(m.entries()).sort((a, b) => a[0] - b[0])
    .map(([k, items]) => ({ key: String(k), label: weekLabel(new Date(k), today), items }));
}

const MONTH_PERIOD = /^[A-Z][a-z]{2} \d{4}$/;
function periodText(label: string | null): string | null {
  if (!label) return null;
  if (MONTH_PERIOD.test(label)) {
    const d = new Date(`1 ${label}`);
    if (!Number.isNaN(d.getTime())) return `for ${d.toLocaleDateString('en-IN', { month: 'long', year: 'numeric' })}`;
  }
  return label;
}

/* ------------------------------------------------------------------ state styling */

const DOT: Record<TaskState, string> = { overdue: 'bg-critical', due_soon: 'bg-warn', upcoming: 'bg-primary', done: '' };
const STATE_RANK: Record<TaskState, number> = { overdue: 0, due_soon: 1, upcoming: 2, done: 3 };

export const daysText = (t: ComplianceTask) => {
  const d = t.days_left;
  if (t.state === 'done') return 'Filed';
  if (d === null) return 'No date';
  if (d < 0) return `${plural(Math.abs(d), 'day')} overdue`;
  if (d === 0) return 'Due today';
  if (d === 1) return 'Due tomorrow';
  return `Due in ${plural(d, 'day')}`;
};

/* ------------------------------------------------------------------ 12-month strip */

export const MonthStrip: React.FC<{
  months: MonthCol[]; tasks: ComplianceTask[]; focus: string; onFocus: (key: string) => void;
}> = ({ months, tasks, focus, onFocus }) => {
  const byMonth = new Map<string, ComplianceTask[]>();
  const earlier: ComplianceTask[] = [];
  tasks.forEach((t) => {
    if (!t.due_date) return;
    const k = monthKeyOf(t.due_date);
    if (k < months[0].key) { if (t.state === 'overdue') earlier.push(t); return; }
    byMonth.set(k, [...(byMonth.get(k) ?? []), t]);
  });

  return (
    <div role="group" aria-label="Next 12 months" className="flex snap-x gap-1.5 overflow-x-auto pb-1 sm:gap-2">
      {earlier.length > 0 && (
        <button onClick={() => onFocus(months[0].key)} aria-label={`${plural(earlier.length, 'overdue filing')} from earlier months`} title="Overdue from earlier months"
          className="flex min-h-[104px] w-[72px] shrink-0 snap-start flex-col rounded-xl bg-critical-soft px-2.5 pb-2 pt-2 text-left sm:w-[84px]">
          <span className="text-sm font-semibold text-critical-ink">Earlier</span>
          <span className="mt-2 flex flex-wrap content-start gap-1" aria-hidden>
            {earlier.slice(0, 12).map((t) => <span key={t.id} className="h-1.5 w-1.5 rounded-full bg-critical" />)}
            {earlier.length > 12 && <span className="text-[10px] font-medium leading-none text-critical-ink">+{earlier.length - 12}</span>}
          </span>
          <span className="mt-auto pt-2 text-[11px] font-medium text-critical-ink">{earlier.length} overdue</span>
        </button>
      )}
      {months.map((m) => {
        const list = (byMonth.get(m.key) ?? []).slice().sort((a, b) => STATE_RANK[a.state] - STATE_RANK[b.state]);
        const counts = { overdue: 0, due_soon: 0, upcoming: 0, done: 0 } as Record<TaskState, number>;
        list.forEach((t) => { counts[t.state] += 1; });
        const pending = list.length - counts.done;
        const active = focus === m.key;
        const shown = list.slice(0, 12);
        const desc = `${monthTitle(m.key)}: ${list.length === 0 ? 'nothing due' : [
          counts.overdue && `${counts.overdue} overdue`, counts.due_soon && `${counts.due_soon} due within a week`,
          counts.upcoming && `${counts.upcoming} upcoming`, counts.done && `${counts.done} filed`].filter(Boolean).join(', ')}`;
        const showYear = m.key.endsWith('-01') || m.isNow;
        return (
          <button key={m.key} onClick={() => onFocus(m.key)} aria-pressed={active} aria-label={desc} title={desc}
            className={cn(
              'relative flex min-h-[104px] w-[72px] shrink-0 snap-start flex-col rounded-xl border px-2.5 pb-2 pt-2 text-left transition-[background-color,box-shadow,border-color] sm:w-[84px] lg:min-w-[64px] lg:flex-1',
              active ? 'border-primary bg-surface shadow-raised' : 'border-transparent bg-surface-2 hover:border-line-strong',
              m.isNow && 'ring-2 ring-primary/70 ring-offset-2 ring-offset-surface',
            )}>
            <span className="flex items-baseline justify-between">
              <span className="text-sm font-semibold text-ink">{m.short}</span>
              {showYear && <span className="text-[10px] font-medium text-ink-3">{`'${String(m.year).slice(2)}`}</span>}
            </span>
            <span className="mt-2 flex flex-wrap content-start gap-1" aria-hidden>
              {shown.map((t) => t.state === 'done'
                ? <Check key={t.id} className="h-2.5 w-2.5 text-ink-3" strokeWidth={3} />
                : <span key={t.id} className={cn('h-1.5 w-1.5 rounded-full', DOT[t.state])} />)}
              {list.length > shown.length && <span className="text-[10px] font-medium leading-none text-ink-3">+{list.length - shown.length}</span>}
            </span>
            <span className="mt-auto pt-2 text-[11px] text-ink-3">
              {m.isNow && <span className="mr-1 font-semibold text-ink">Now</span>}
              {pending > 0 ? `${pending} to file` : list.length > 0 ? 'All filed' : ''}
            </span>
          </button>
        );
      })}
    </div>
  );
};

export const StripLegend: React.FC = () => (
  <ul className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-3" aria-label="Legend">
    <li className="flex items-center gap-1.5"><span className="h-1.5 w-1.5 rounded-full bg-critical" aria-hidden />Overdue</li>
    <li className="flex items-center gap-1.5"><span className="h-1.5 w-1.5 rounded-full bg-warn" aria-hidden />Due within 7 days</li>
    <li className="flex items-center gap-1.5"><span className="h-1.5 w-1.5 rounded-full bg-primary" aria-hidden />Upcoming</li>
    <li className="flex items-center gap-1.5"><Check className="h-2.5 w-2.5" strokeWidth={3} aria-hidden />Filed</li>
  </ul>
);

/* ------------------------------------------------------------------ done toggle */

export const DoneToggle: React.FC<{ task: ComplianceTask; size?: 'md' | 'lg' }> = ({ task: t, size = 'md' }) => {
  const toggle = useToggleDone();
  const done = t.state === 'done';
  const next = done ? 'pending' : 'completed';
  const run = () => toggle.mutate({ id: t.id, status: next }, {
    onSuccess: () => {
      if (next === 'completed') toast.success('Marked as filed', { action: { label: 'Undo', onClick: () => toggle.mutate({ id: t.id, status: 'pending' }) } });
    },
    onError: (e) => toast.error(toFriendlyError(e).message),
  });
  return (
    <button role="checkbox" aria-checked={done} aria-label={done ? `Filed: ${t.title}. Undo` : `Mark as filed: ${t.title}`} onClick={run}
      className={cn('group/tick -m-1 flex shrink-0 items-center justify-center rounded-full p-1 transition-colors max-sm:min-h-[44px] max-sm:min-w-[44px]', done ? 'text-good-ink' : 'text-ink-3 hover:text-good-ink')}>
      {done
        ? <CheckCircle2 className={size === 'lg' ? 'h-8 w-8' : 'h-6 w-6'} aria-hidden />
        : <Circle className={cn('transition-transform group-hover/tick:scale-105', size === 'lg' ? 'h-8 w-8' : 'h-6 w-6')} strokeWidth={1.75} aria-hidden />}
    </button>
  );
};

/* ------------------------------------------------------------------ small pieces */

const OriginTag: React.FC<{ task: ComplianceTask }> = ({ task: t }) => {
  if (t.origin) {
    const Icon = t.origin.kind === 'contract' ? FileSignature : t.origin.kind === 'notice' ? Gavel : FileText;
    return (
      <Link to={t.origin.href} onClick={(e) => e.stopPropagation()}
        className="inline-flex max-w-full items-center gap-1 rounded-full border border-line bg-surface-2 px-2 py-0.5 text-xs font-medium text-ink-2 hover:border-primary hover:text-primary-ink">
        <Icon className="h-3 w-3 shrink-0" aria-hidden /><span className="truncate">{t.origin.label}</span>
      </Link>
    );
  }
  if (t.is_custom) return <span className="rounded-full border border-line bg-surface-2 px-2 py-0.5 text-xs font-medium text-ink-2">Your reminder</span>;
  return null;
};

const VerifyingNote: React.FC = () => (
  <span className="inline-flex items-center gap-1 text-xs italic text-ink-3" title="We have not yet confirmed this date against the latest official notification.">
    <Hourglass className="h-3 w-3" aria-hidden />Date being verified
  </span>
);

export const DateChip: React.FC<{ iso: string | null; state: TaskState }> = ({ iso, state }) => {
  const d = iso ? parseDay(iso) : null;
  return (
    <div aria-hidden className={cn('flex h-14 w-12 shrink-0 flex-col items-center justify-center rounded-lg text-center font-mono leading-none',
      state === 'overdue' ? 'bg-critical-soft text-critical-ink' : state === 'due_soon' ? 'bg-warn-soft text-warn-ink'
        : state === 'done' ? 'bg-surface text-ink-3 shadow-card' : 'bg-surface text-ink shadow-card')}>
      <span className="text-[10px] font-medium uppercase tracking-wide opacity-80">{d ? d.toLocaleDateString('en-IN', { month: 'short' }) : ''}</span>
      <span className="my-0.5 text-lg font-semibold tabular-nums">{d ? d.getDate() : '-'}</span>
      <span className="text-[10px] font-medium opacity-80">{d ? d.toLocaleDateString('en-IN', { weekday: 'short' }) : ''}</span>
    </div>
  );
};

/** One line on the cost of being late: a computed estimate when the rule allows it, else the plain rule text. */
export const PenaltyLine: React.FC<{ task: ComplianceTask; clamp?: boolean }> = ({ task: t, clamp = true }) => {
  const e = t.penalty_estimate;
  if (t.state === 'overdue' && e) {
    const how = e.flat ? 'one-off fee' : `${plural(e.days_late, 'day')} late at ${formatINR(e.per_day)}/day${e.capped ? `, capped at ${formatINR(e.cap)}` : ''}`;
    return (
      <p className={cn('text-sm', clamp && 'line-clamp-2 sm:line-clamp-1')}>
        <span className="font-semibold text-critical-ink">{e.flat ? '' : 'Up to '}{formatINR(e.amount)} so far</span>
        <span className="text-ink-2"> in late fees ({how}). Interest is extra.</span>
      </p>
    );
  }
  if (!t.penalty_desc) return null;
  return <p className={cn('text-sm text-ink-2', clamp && 'line-clamp-2 sm:line-clamp-1')} title={t.penalty_desc}><span className="text-ink-3">If missed: </span>{t.penalty_desc}</p>;
};

/* ------------------------------------------------------------------ row */

export const ObligationRow: React.FC<{ task: ComplianceTask; flash?: boolean }> = ({ task: t, flash }) => {
  const del = useDeleteTask();
  const [open, setOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const done = t.state === 'done';
  const period = periodText(t.period_label);
  const sub = [t.form_name, t.authority].filter(Boolean).join(' · ');

  return (
    <li id={`task-${t.id}`} className={cn('rounded-2xl border transition-[box-shadow,background-color]', open ? 'border-line bg-surface shadow-card' : 'border-transparent bg-surface-2 hover:shadow-card', done && !open && 'opacity-60', flash && 'animate-in ring-2 ring-primary/60')}>
      <div className="flex items-start gap-3 p-3 sm:p-4">
        <DateChip iso={t.due_date} state={t.state} />
        <div className="min-w-0 flex-1">
          <button className="flex w-full items-start gap-2 text-left" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
            <span className="min-w-0 flex-1">
              <span className={cn('block font-semibold leading-snug text-ink', done && 'text-ink-2 line-through decoration-ink-3')}>
                {t.title}{period && <span className="font-normal text-ink-2"> {period}</span>}
              </span>
              {sub && <span className="block text-sm text-ink-2">{sub}</span>}
            </span>
            <ChevronDown className={cn('mt-1 h-4 w-4 shrink-0 text-ink-3 transition-transform', open && 'rotate-180')} aria-hidden />
          </button>
          {!done && <div className="mt-1"><PenaltyLine task={t} /></div>}
          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-3">
            <span className={cn('font-semibold', t.state === 'overdue' ? 'text-critical-ink' : t.state === 'due_soon' ? 'text-warn-ink' : 'text-ink-2')}>{daysText(t)}</span>
            {t.source_ref && <span className="min-w-0 truncate" title={t.source_ref}>{t.source_ref.split(' (')[0]}</span>}
            <OriginTag task={t} />
            {!t.verified && <VerifyingNote />}
          </div>
        </div>
        <DoneToggle task={t} />
      </div>

      {open && (
        <div className="space-y-3 border-t border-line px-4 pb-4 pt-3 text-sm">
          {t.description && <p className="text-ink-2">{t.description}</p>}
          {t.needs_confirmation && t.confirm_note && !done && <Notice tone="warn"><strong>Check this:</strong> {t.confirm_note}</Notice>}
          {(done || !t.penalty_estimate) ? null : <PenaltyLine task={t} clamp={false} />}
          {t.penalty_estimate?.note && !done && <p className="text-xs text-ink-3">{t.penalty_estimate.note}</p>}
          {t.penalty_desc && <p><strong className="text-ink">If you miss it: </strong><span className="text-ink-2">{t.penalty_desc}</span></p>}
          {t.source_ref && <p className="text-xs text-ink-3">Source: {t.source_ref}</p>}
          {t.file_url && (
            <a href={t.file_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm font-medium text-primary-ink hover:underline">
              File on the {t.file_where ?? 'official portal'}<ExternalLink className="h-3.5 w-3.5" aria-hidden />
            </a>
          )}
          {t.status === 'completed' && <p className="text-ink-2"><strong className="text-ink">Filed: </strong>{formatDate(t.completed_at)}{t.completion_note ? ` · ${t.completion_note}` : ''}</p>}
          {t.is_custom && !t.origin && (
            <Button size="sm" variant="ghost" icon={<Trash2 className="h-4 w-4" aria-hidden />} onClick={() => setConfirmDelete(true)}>Delete reminder</Button>
          )}
        </div>
      )}
      <ConfirmDialog open={confirmDelete} onOpenChange={setConfirmDelete} danger loading={del.isPending} title="Delete this reminder?" description={t.title} confirmLabel="Delete"
        onConfirm={() => del.mutate(t.id, { onSuccess: () => setConfirmDelete(false), onError: (e) => toast.error(toFriendlyError(e).message) })} />
    </li>
  );
};

/* ------------------------------------------------------------------ next up hero */

export const NextUpHero: React.FC<{ task: ComplianceTask | null; overdueCount: number; onSeeOverdue: () => void }> = ({ task: t, overdueCount, onSeeOverdue }) => {
  if (!t) {
    return (
      <div className="rounded-2xl bg-surface-2 p-5 sm:p-6">
        <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-2">Next up</p>
        <p className="mt-2 text-xl font-semibold text-ink">Nothing else is due in the next 12 months.</p>
        <p className="mt-1 text-sm text-ink-2">New deadlines appear here as soon as your profile or documents add them.</p>
        {overdueCount > 0 && <button onClick={onSeeOverdue} className="mt-3 text-sm font-semibold text-critical-ink underline">{plural(overdueCount, 'filing')} overdue, see below</button>}
      </div>
    );
  }
  const d = t.days_left ?? 0;
  const urgent = d <= 7;
  const period = periodText(t.period_label);
  return (
    <section aria-label="Next up" className={cn('rounded-2xl p-5 sm:p-6', urgent ? 'bg-warn-soft' : 'bg-surface-2')}>
      <div className="flex items-center justify-between gap-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-2">Next up</p>
        {overdueCount > 0 && <button onClick={onSeeOverdue} className="text-xs font-semibold text-critical-ink underline">{overdueCount} overdue, see below</button>}
      </div>
      <div className="mt-3 flex flex-col gap-4 sm:flex-row sm:items-center sm:gap-6">
        <div className="shrink-0 sm:w-40">
          {d === 0
            ? <p className="font-display text-6xl font-normal leading-none tracking-tight text-warn-ink">Today</p>
            : <p className={cn('flex items-baseline gap-2 leading-none', urgent ? 'text-warn-ink' : 'text-ink')}>
                <span className="font-display text-7xl font-normal tabular-nums tracking-tight">{d}</span><span className="text-sm font-semibold">{d === 1 ? 'day left' : 'days left'}</span>
              </p>}
          <p className="mt-2 text-sm font-medium text-ink-2">{formatDate(t.due_date)}</p>
        </div>
        <div className="min-w-0 flex-1">
          <h2 className="text-xl font-semibold leading-snug text-ink">{t.title}{period && <span className="font-normal text-ink-2"> {period}</span>}</h2>
          <p className="text-sm text-ink-2">{[t.form_name, t.authority].filter(Boolean).join(' · ')}</p>
          {t.description && <p className="mt-2 text-sm text-ink">{t.description}</p>}
          <div className="mt-1"><PenaltyLine task={t} /></div>
          <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2">
            <HeroDone task={t} />
            {t.file_url && (
              <a href={t.file_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm font-medium text-primary-ink hover:underline">
                Open the {t.file_where ?? 'portal'}<ExternalLink className="h-3.5 w-3.5" aria-hidden />
              </a>
            )}
            <OriginTag task={t} />
            {!t.verified && <VerifyingNote />}
          </div>
        </div>
      </div>
    </section>
  );
};

const HeroDone: React.FC<{ task: ComplianceTask }> = ({ task: t }) => {
  const toggle = useToggleDone();
  return (
    <Button size="sm" loading={false} disabled={toggle.isPending} icon={<CheckCircle2 className="h-4 w-4" aria-hidden />}
      onClick={() => toggle.mutate({ id: t.id, status: 'completed' }, {
        onSuccess: () => toast.success('Marked as filed', { action: { label: 'Undo', onClick: () => toggle.mutate({ id: t.id, status: 'pending' }) } }),
        onError: (e) => toast.error(toFriendlyError(e).message),
      })}>
      Mark as filed
    </Button>
  );
};
