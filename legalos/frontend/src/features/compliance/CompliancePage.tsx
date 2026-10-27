import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { CalendarClock, CalendarPlus, CheckCircle2, ChevronDown, Hourglass, RefreshCw, SlidersHorizontal } from 'lucide-react';
import { toast } from 'sonner';
import { toFriendlyError } from '@/api/client';
import { Button, EmptyState, ErrorState, Field, Input, Select, Skeleton, Textarea } from '@/ui/primitives';
import { ConfirmDialog, Modal } from '@/ui/overlays';
import { SidePanel } from '@/ui/sidepanel';
import { useNewParam } from '@/ui/workspace';
import { cn, formatDateTime, formatINR, plural } from '@/lib/utils';
import {
  useBulkComplete, useComplianceSummary, useComplianceTasks, useCreateTask, useRulesOverview, useSyncCalendar, type ComplianceTask,
} from './api';
import { buildMonths, groupByWeek, monthKeyOf, monthTitle, MonthStrip, NextUpHero, ObligationRow, StripLegend } from './planner';
import { ProfileRail } from './ProfileRail';

const CATEGORIES = [
  { value: 'tax', label: 'Tax' }, { value: 'corporate', label: 'Company law' }, { value: 'labor', label: 'Labour' },
  { value: 'license', label: 'Licences' }, { value: 'other', label: 'Other' },
];
const categoryLabel = (v: string) => CATEGORIES.find((c) => c.value === v)?.label ?? v;

/* ------------------------------------------------------------------ add reminder */

const AddReminderDialog: React.FC<{ open: boolean; onClose: () => void }> = ({ open, onClose }) => {
  const create = useCreateTask();
  const [form, setForm] = useState({ title: '', due_date: '', category: 'other', description: '' });
  const valid = form.title.trim().length >= 2 && !!form.due_date;
  const err = create.isError ? toFriendlyError(create.error).message : null;
  return (
    <Modal open={open} onOpenChange={(o) => { if (!o) onClose(); }} title="Add your own reminder" description="For anything we don't track yet, like a licence renewal or a board meeting."
      footer={<>
        <Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button disabled={!valid} loading={create.isPending} onClick={() => create.mutate({ ...form, description: form.description || undefined }, {
          onSuccess: () => { toast.success('Reminder added'); setForm({ title: '', due_date: '', category: 'other', description: '' }); onClose(); },
        })}>Add reminder</Button>
      </>}>
      <div className="space-y-4">
        {err && <ErrorState message={err} />}
        <Field label="What is it?" required>{({ id }) => <Input id={id} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="e.g. Renew FSSAI licence" />}</Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Due date" required>{({ id }) => <Input id={id} type="date" value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} />}</Field>
          <Field label="Type">{({ id }) => (
            <Select id={id} value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
              {CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
            </Select>)}
          </Field>
        </div>
        <Field label="Notes (optional)">{({ id }) => <Textarea id={id} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />}</Field>
      </div>
    </Modal>
  );
};

/* ------------------------------------------------------------------ overdue group */

const OverdueGroup = React.forwardRef<HTMLElement, { tasks: ComplianceTask[]; flash: Set<string> }>(function OverdueGroup({ tasks, flash }, ref) {
  const bulk = useBulkComplete();
  const [confirm, setConfirm] = useState(false);
  const [all, setAll] = useState(false);
  const priced = tasks.filter((t) => t.penalty_estimate && !t.penalty_estimate.flat);
  const fixed = tasks.filter((t) => t.penalty_estimate?.flat);
  const total = tasks.reduce((n, t) => n + (t.penalty_estimate?.amount ?? 0), 0);
  const unpriced = tasks.length - priced.length - fixed.length;
  const shown = all ? tasks : tasks.slice(0, 4);
  return (
    <section ref={ref} aria-label="Overdue" className="rounded-2xl border border-critical/40 bg-critical-soft/40 p-3 sm:p-4">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1 px-1">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-critical-ink">Overdue · {tasks.length}</h2>
          {total > 0
            ? <p className="mt-0.5 text-sm text-ink-2">
                May have cost up to <strong className="text-ink">{formatINR(total)}</strong> in late fees so far
                {unpriced > 0 ? `, not counting ${plural(unpriced, 'filing')} whose penalty is not a daily fee.` : '.'}
              </p>
            : <p className="mt-0.5 text-sm text-ink-2">File these first. Each one shows what missing it can cost.</p>}
        </div>
        {tasks.length >= 2 && (
          <Button size="sm" variant="secondary" onClick={() => setConfirm(true)}>Already filed these?</Button>
        )}
      </div>
      <ul className="mt-3 space-y-2">{shown.map((t) => <ObligationRow key={t.id} task={t} flash={flash.has(t.id)} />)}</ul>
      {tasks.length > 4 && (
        <button onClick={() => setAll((a) => !a)} className="mt-2 w-full rounded-lg py-2 text-sm font-medium text-critical-ink hover:bg-critical-soft">
          {all ? 'Show fewer' : `Show ${tasks.length - 4} more overdue`}
        </button>
      )}
      <ConfirmDialog open={confirm} onOpenChange={setConfirm} loading={bulk.isPending}
        title={`Mark ${tasks.length} items as already filed?`}
        description="Only do this if these returns and payments were really filed. You can undo any single item later."
        confirmLabel="Yes, they were filed"
        onConfirm={() => bulk.mutate(tasks.map((t) => t.id), {
          onSuccess: (r) => { toast.success(`${r.completed} items marked as filed`); setConfirm(false); },
          onError: (e) => toast.error(toFriendlyError(e).message),
        })} />
    </section>
  );
});

/* ------------------------------------------------------------------ how this is built */

const HowBuilt: React.FC<{ summary: ReturnType<typeof useComplianceSummary>['data'] }> = ({ summary: s }) => {
  const [open, setOpen] = useState(false);
  const rules = useRulesOverview(open);
  const unverified = rules.data?.applicable.filter((r) => !r.verified).length ?? 0;
  return (
    <details className="group rounded-2xl bg-surface-2" onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}>
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm font-medium text-ink [&::-webkit-details-marker]:hidden">
        <span>How this is built</span>
        <ChevronDown className="h-4 w-4 text-ink-3 transition-transform group-open:rotate-180" aria-hidden />
      </summary>
      <div className="space-y-4 border-t border-line px-4 pb-4 pt-3 text-sm">
        <p className="text-ink-2">
          A fixed rules engine, no AI guesswork. {s ? <>It holds <strong className="text-ink">{s.rules_total} rules</strong> from <strong className="text-ink">{s.sources_total} legal sources</strong>; <strong className="text-ink">{s.rules_applicable}</strong> apply to your profile. </> : null}
          Rules version {s?.rules_version ?? '-'}{s?.last_synced ? `, calendar last updated ${formatDateTime(s.last_synced)}` : ''}.
        </p>
        <p className="text-xs text-ink-3">These are the standard statutory due dates. The government sometimes extends them by notification, so confirm with your CA before relying on a date. This is decision support, not legal advice.</p>
        {rules.isLoading && <Skeleton className="h-40 w-full" />}
        {rules.isError && <ErrorState message={toFriendlyError(rules.error).message} onRetry={() => rules.refetch()} />}
        {rules.data && (
          <>
            <ul className="space-y-2">
              {rules.data.applicable.map((r) => (
                <li key={r.id} className="rounded-lg bg-surface p-3">
                  <p className="flex flex-wrap items-center gap-2 font-medium text-ink">
                    {r.title}<span className="rounded-full bg-surface-2 px-2 py-0.5 text-xs font-medium text-ink-2">{categoryLabel(r.category)}</span>
                    {!r.verified && <span className="inline-flex items-center gap-1 text-xs font-normal italic text-ink-3"><Hourglass className="h-3 w-3" aria-hidden />being verified</span>}
                  </p>
                  <p className="mt-0.5 text-ink-2">{r.reason}</p>
                  <p className="mt-0.5 text-xs text-ink-3">Source: {r.source}</p>
                </li>
              ))}
            </ul>
            {unverified > 0 && <p className="text-xs text-ink-3">{plural(unverified, 'rule')} above still being verified against the latest notification.</p>}
            <details className="rounded-lg bg-surface p-3">
              <summary className="cursor-pointer text-sm font-medium text-ink">{rules.data.not_applicable.length} rules switched off for you, and why</summary>
              <ul className="mt-2 space-y-1.5 text-sm">{rules.data.not_applicable.map((r) => <li key={r.id}><span className="font-medium text-ink">{r.title}</span> <span className="text-ink-3">· {r.reason}</span></li>)}</ul>
            </details>
            <div>
              <p className="mb-1.5 font-medium text-ink">Not covered yet</p>
              <ul className="space-y-1.5 text-sm">{rules.data.not_covered.map((r) => <li key={r.title}><span className="font-medium text-ink">{r.title}</span> <span className="text-ink-3">· {r.reason}</span></li>)}</ul>
            </div>
          </>
        )}
      </div>
    </details>
  );
};

/* ------------------------------------------------------------------ page */

export const CompliancePage: React.FC = () => {
  const summary = useComplianceSummary();
  const tasksQ = useComplianceTasks();
  const sync = useSyncCalendar();
  const [adding, setAdding] = useNewParam();
  const [focusKey, setFocusKey] = useState<string | null>(null);
  const [flash, setFlash] = useState<Set<string>>(new Set());
  const overdueRef = useRef<HTMLElement>(null);
  const flashTimer = useRef<number>();
  useEffect(() => () => window.clearTimeout(flashTimer.current), []);

  const s = summary.data;
  const today = useMemo(() => {
    const d = s?.today ? new Date(`${s.today}T00:00:00`) : new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  }, [s?.today]);
  const months = useMemo(() => buildMonths(today), [today]);
  const focus = focusKey ?? months[0].key;
  const tasks = tasksQ.data ?? [];

  const overdue = useMemo(() => tasks.filter((t) => t.state === 'overdue'), [tasks]);
  const nextUp = useMemo(() => tasks.find((t) => t.state === 'due_soon' || t.state === 'upcoming') ?? null, [tasks]);
  const monthTasks = useMemo(() => tasks.filter((t) => t.due_date && monthKeyOf(t.due_date) === focus && t.state !== 'overdue'), [tasks, focus]);
  const weeks = useMemo(() => groupByWeek(monthTasks, today), [monthTasks, today]);
  const nextBusy = useMemo(() => months.find((m) => m.key > focus && tasks.some((t) => t.due_date && monthKeyOf(t.due_date) === m.key)), [months, tasks, focus]);

  const onApplied = (before?: ComplianceTask[], after?: ComplianceTask[]) => {
    if (!before || !after) return;
    const had = new Set(before.map((t) => t.id));
    const now = new Set(after.map((t) => t.id));
    const added = after.filter((t) => !had.has(t.id));
    const removed = before.filter((t) => !now.has(t.id)).length;
    setFlash(new Set(added.map((t) => t.id)));
    window.clearTimeout(flashTimer.current);
    flashTimer.current = window.setTimeout(() => setFlash(new Set()), 5000);
    toast.success(added.length || removed
      ? `Calendar updated: ${added.length} filing${added.length === 1 ? '' : 's'} added, ${removed} removed`
      : 'Profile saved. No change to your calendar.');
  };

  if (s?.needs_profile) {
    return (
      <div className="flex h-full items-center justify-center overflow-y-auto p-6">
        <EmptyState icon={<CalendarClock className="h-6 w-6" />} title="Tell us about your company first"
          description="The deadlines that apply depend on your type of business, state, size and registrations."
          action={<Link to="/onboarding" className="inline-flex min-h-[44px] items-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-on hover:bg-primary-hover">Set up your company</Link>} />
      </div>
    );
  }

  const stats = s ? [
    s.overdue > 0 && { text: `${s.overdue} overdue`, tone: 'text-critical-ink' },
    { text: `${s.due_in_7_days} due this week`, tone: s.due_in_7_days ? 'text-warn-ink' : 'text-ink-2' },
    { text: `${s.due_in_30_days} in the next 30 days`, tone: 'text-ink-2' },
    s.completed_last_30_days > 0 && { text: `${s.completed_last_30_days} filed in the last 30 days`, tone: 'text-good-ink' },
  ].filter(Boolean) as { text: string; tone: string }[] : [];

  return (
    <div className="relative h-full overflow-hidden">
      <SidePanel storageKey="compliance-why" title="Why these filings" icon={SlidersHorizontal}
        actions={<Button size="sm" icon={<CalendarPlus className="h-4 w-4" aria-hidden />} onClick={() => setAdding(true)}>Add reminder</Button>}>
        <ProfileRail onApplied={onApplied} />
      </SidePanel>

      <div className="h-full overflow-y-auto">
        <div className="mx-auto w-full max-w-6xl space-y-5 px-6 pb-20 pt-16 sm:px-10 md:pt-6 xl:px-14">
          <header className="md:pr-56">
            <div className="flex items-center gap-1.5">
              <h1 className="text-xl font-semibold text-ink">Compliance planner</h1>
              <Button variant="ghost" size="sm" aria-label="Refresh calendar from profile" title="Rebuild the calendar from your profile" disabled={sync.isPending}
                className="!h-8 !w-8 !min-h-0 !px-0"
                icon={<RefreshCw className={cn('h-4 w-4', sync.isPending && 'animate-spin')} aria-hidden />}
                onClick={() => sync.mutate(undefined, { onSuccess: (r) => toast.success(r.created || r.removed ? `Calendar updated: ${r.created} added, ${r.removed} removed` : 'Calendar is up to date'), onError: (e) => toast.error(toFriendlyError(e).message) })} />
            </div>
            <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-sm text-ink-2">
              {summary.isLoading ? <Skeleton className="h-5 w-72" /> : stats.map((x, i) => (
                <React.Fragment key={x.text}>{i > 0 && <span aria-hidden className="text-ink-3">·</span>}<span className={cn('font-medium', x.tone)}>{x.text}</span></React.Fragment>
              ))}
            </p>
          </header>

          <section aria-label="The next 12 months">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-2">The next 12 months</p>
              <StripLegend />
            </div>
            {tasksQ.isLoading
              ? <div className="flex gap-2">{Array.from({ length: 12 }, (_, i) => <Skeleton key={i} className="h-[104px] min-w-[72px] flex-1" />)}</div>
              : <MonthStrip months={months} tasks={tasks} focus={focus} onFocus={setFocusKey} />}
          </section>

          {tasksQ.isError && <ErrorState message={toFriendlyError(tasksQ.error).message} onRetry={() => tasksQ.refetch()} />}
          {tasksQ.isLoading && <><Skeleton className="h-40 w-full" /><Skeleton className="h-24 w-full" /><Skeleton className="h-24 w-full" /></>}

          {tasksQ.data && (
            <>
              <NextUpHero task={nextUp} overdueCount={overdue.length} onSeeOverdue={() => overdueRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })} />

              {overdue.length > 0 && <OverdueGroup ref={overdueRef} tasks={overdue} flash={flash} />}

              <section aria-label={monthTitle(focus)}>
                <h2 className="mb-3 flex items-baseline gap-2 text-lg font-semibold text-ink">
                  {monthTitle(focus)}
                  <span className="text-sm font-normal text-ink-3">{monthTasks.length === 0 ? 'nothing due' : plural(monthTasks.length, 'filing')}</span>
                </h2>
                {weeks.length === 0 && (
                  <EmptyState icon={<CheckCircle2 className="h-6 w-6" />} title={`Nothing due in ${monthTitle(focus).split(' ')[0]}`}
                    description="A quiet month. Use it to get ahead."
                    action={nextBusy ? <Button variant="secondary" size="sm" onClick={() => setFocusKey(nextBusy.key)}>Jump to {monthTitle(nextBusy.key).split(' ')[0]}</Button> : undefined} />
                )}
                <div className="space-y-5">
                  {weeks.map((w) => (
                    <div key={w.key}>
                      <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-3">{w.label}</h3>
                      <ul className="space-y-2">{w.items.map((t) => <ObligationRow key={t.id} task={t} flash={flash.has(t.id)} />)}</ul>
                    </div>
                  ))}
                </div>
              </section>

              <HowBuilt summary={s} />
            </>
          )}
        </div>
      </div>

      <AddReminderDialog open={adding} onClose={() => setAdding(false)} />
    </div>
  );
};
