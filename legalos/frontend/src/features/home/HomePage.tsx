import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, BellRing, BookOpen, CalendarCheck, CalendarClock, CheckCircle2, Circle, FileText, Sparkles, Store, Upload } from 'lucide-react';
import { toast } from 'sonner';
import { useSession } from '@/lib/auth/session';
import { toFriendlyError } from '@/api/client';
import { Button, Card, ErrorState, SectionTitle, Skeleton } from '@/ui/primitives';
import { cn, formatDate, plural } from '@/lib/utils';
import { useContracts } from '@/features/contracts/api';
import { useComplianceSummary } from '@/features/compliance/api';
import { useNotices } from '@/features/notices/api';
import { useVendors } from '@/features/vendors/api';
import { useDocuments } from '@/features/documents/api';
import { useActivity, useLoadSample } from '@/features/samples/api';
import { useAttention, type AttentionItem } from '@/app/useAttention';

const greeting = () => { const h = new Date().getHours(); return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening'; };
const fmtTime = (iso: string) => new Date(iso).toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit' }).toLowerCase();
const dayKey = (iso: string) => {
  const d = new Date(iso); const t = new Date(); const y = new Date(); y.setDate(t.getDate() - 1);
  return d.toDateString() === t.toDateString() ? 'Today' : d.toDateString() === y.toDateString() ? 'Yesterday' : d.toLocaleDateString('en-IN', { day: 'numeric', month: 'long' });
};
const ICON: Record<AttentionItem['kind'], React.ElementType> = { notice: BellRing, contract: FileText, compliance: CalendarCheck, document: BookOpen };
const TILE: Record<AttentionItem['level'], string> = { critical: 'bg-peach text-peach-ink', high: 'bg-warn-soft text-warn-ink', medium: 'bg-lavender text-lavender-ink' };
const dueLabel = (d: number) => (d === 0 ? 'Due today' : d === 1 ? 'Due tomorrow' : `Due in ${plural(d, 'day')}`);



/** First-run checklist: appears until the account has something in each area. */
const GettingStarted: React.FC<{ done: Record<string, boolean> }> = ({ done }) => {
  const navigate = useNavigate();
  const sample = useLoadSample();
  const steps = [
    { key: 'profile', label: 'Set up your company profile', to: '/onboarding' },
    { key: 'contract', label: 'Review your first contract', to: '/contracts?new=1', sample: 'contract' as const },
    { key: 'vendor', label: 'Check a supplier', to: '/vendors?new=1' },
    { key: 'notice', label: 'Add a legal notice (if you have one)', to: '/notices?new=1', sample: 'notice' as const },
    { key: 'document', label: 'Add a company document', to: '/documents?new=1', sample: 'document' as const },
  ];
  const remaining = steps.filter((s) => !done[s.key]);
  if (remaining.length === 0) return null;
  const pct = Math.round(((steps.length - remaining.length) / steps.length) * 100);
  return (
    <Card className="mb-8 border-primary/30">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><h2 className="text-base font-semibold text-ink">Getting started</h2><p className="text-sm text-ink-2">{pct}% done. Each step takes under a minute.</p></div>
        <div className="h-2 w-40 overflow-hidden rounded-full bg-surface-2" aria-hidden><div className="h-full rounded-full bg-primary" style={{ width: `${pct}%` }} /></div>
      </div>
      <ul className="mt-4 divide-y divide-line">
        {steps.map((s) => (
          <li key={s.key} className="flex flex-wrap items-center gap-3 py-2.5">
            {done[s.key] ? <CheckCircle2 className="h-5 w-5 shrink-0 text-good-ink" aria-hidden /> : <Circle className="h-5 w-5 shrink-0 text-ink-3" aria-hidden />}
            <span className={cn('min-w-0 flex-1 text-sm', done[s.key] ? 'text-ink-3 line-through' : 'font-medium text-ink')}>{s.label}</span>
            {!done[s.key] && (
              <span className="flex gap-2">
                {s.sample && <Button size="sm" variant="ghost" loading={sample.isPending && sample.variables === s.sample} icon={<Sparkles className="h-4 w-4" aria-hidden />}
                  onClick={() => sample.mutate(s.sample!, { onSuccess: (r) => { toast.success('Sample added. Opening it now.'); navigate(r.path); }, onError: (e) => toast.error(toFriendlyError(e).message) })}>Try a sample</Button>}
                <Link to={s.to} className="inline-flex min-h-[36px] items-center gap-1 rounded-lg border border-line-strong px-3 text-sm font-medium text-ink hover:bg-surface-2">Start <ArrowRight className="h-3.5 w-3.5" aria-hidden /></Link>
              </span>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
};

export const HomePage: React.FC = () => {
  const { user, org } = useSession();
  const contracts = useContracts();
  const compliance = useComplianceSummary();
  const notices = useNotices();
  const vendors = useVendors();
  const documents = useDocuments();
  const activity = useActivity();
  const attention = useAttention();
  const c = compliance.data;
  const firstName = user?.full_name.split(' ')[0] ?? '';
  const loading = contracts.isLoading || compliance.isLoading || notices.isLoading;

  const done = {
    profile: !!org?.onboarding_completed, contract: (contracts.data?.length ?? 0) > 0, vendor: (vendors.data?.length ?? 0) > 0,
    notice: (notices.data?.length ?? 0) > 0, document: (documents.data?.length ?? 0) > 0,
  };
  const highRisk = (contracts.data ?? []).filter((x) => x.status === 'analyzed' && x.risk_level === 'high').length;
  const openNotices = (notices.data ?? []).filter((n) => n.status === 'analyzed').length;
  const groups: { day: string; items: NonNullable<typeof activity.data> }[] = [];
  for (const a of activity.data ?? []) {
    const day = dayKey(a.created_at);
    const g = groups[groups.length - 1];
    if (g && g.day === day) g.items.push(a); else groups.push({ day, items: [a] });
  }

  return (
    <>
      <h1 className="mb-6 text-[1.75rem] font-semibold tracking-[-0.02em] text-ink">
        {greeting()}, {firstName}. <span className="font-normal text-ink-2">Here is where {org?.legal_name ?? 'your company'} stands.</span>
      </h1>

      <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
        <div className="min-w-0">
          {/* Hero */}
          <section className="relative overflow-hidden rounded-2xl bg-ink p-8 text-app sm:p-10">
            <div className="bg-noise pointer-events-none absolute inset-0" aria-hidden />
            <div className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-peach-line/25 blur-3xl" aria-hidden />
            <div className="pointer-events-none absolute -bottom-32 right-24 h-72 w-72 rounded-full bg-teal/40 blur-3xl" aria-hidden />
            <h2 className="relative max-w-md font-display text-[2rem] leading-[1.1] sm:text-[2.4rem]">Read it before you sign it.</h2>
            <p className="relative mt-3 max-w-md text-[15px] text-app/75">Upload any contract. Every clause that could hurt you, quoted from your own document, with what to ask for instead.</p>
            <div className="relative mt-6 flex flex-wrap gap-2">
              <Link to="/contracts?new=1" className="btn-raised inline-flex h-10 items-center gap-2 rounded-xl bg-app px-4 text-sm font-medium text-ink hover:bg-surface-2"><Upload className="h-4 w-4" aria-hidden />Review a contract</Link>
              <Link to="/vendors?new=1" className="inline-flex h-10 items-center gap-2 rounded-xl border border-app/20 px-4 text-sm font-medium text-app hover:bg-app/10"><Store className="h-4 w-4" aria-hidden />Check a supplier</Link>
            </div>
          </section>

          {!loading && <div className="mt-6"><GettingStarted done={done} /></div>}

          {c && !c.needs_profile && c.overdue >= 2 && (
            <div className="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-peach p-4">
              <p className="text-sm text-peach-ink"><strong>{plural(c.overdue, 'past deadline')} showing as overdue.</strong> If these were already filed, mark them in one go.</p>
              <Link to="/compliance?catchup=1" className="btn-raised inline-flex h-9 items-center rounded-xl bg-primary px-3.5 text-[13px] font-medium text-primary-on">Mark as already filed</Link>
            </div>
          )}

          {/* Attention */}
          <section aria-labelledby="attention" className="mt-8">
            <SectionTitle id="attention">Needs your attention</SectionTitle>
            {attention.isLoading && <Skeleton className="h-32 w-full rounded-2xl" />}
            {!attention.isLoading && attention.items.length === 0 && (
              <div className="flex items-center gap-4 rounded-2xl bg-surface-2 p-5"><span className="flex h-12 w-12 items-center justify-center rounded-xl bg-good-soft text-good-ink" aria-hidden><CheckCircle2 className="h-5 w-5" /></span><div><p className="font-medium text-ink">You're all caught up</p><p className="text-sm text-ink-2">No urgent notices, overdue filings or high-risk contracts right now.</p></div></div>
            )}
            {attention.items.length > 0 && (
              <ul className="overflow-hidden rounded-2xl border border-line">
                {attention.items.slice(0, 6).map((i) => { const Icon = ICON[i.kind]; return (
                  <li key={i.kind + i.id} className="border-b border-line last:border-0"><Link to={i.link} className="flex items-center gap-4 px-4 py-3.5 transition-colors hover:bg-surface-2">
                    <span className={cn('flex h-11 w-11 shrink-0 items-center justify-center rounded-xl', TILE[i.level])} aria-hidden><Icon className="h-[18px] w-[18px]" /></span>
                    <span className="min-w-0 flex-1"><span className="block truncate text-[15px] font-medium text-ink">{i.title}</span><span className="block truncate text-sm text-ink-2">{i.detail}</span></span>
                    <ArrowRight className="h-4 w-4 shrink-0 text-ink-3" aria-hidden />
                  </Link></li>); })}
              </ul>
            )}
          </section>

          {/* Activity timeline */}
          <section aria-label="Recent activity" className="mt-8">
            {activity.isLoading && <Skeleton className="h-24 w-full rounded-2xl" />}
            {activity.data && activity.data.length === 0 && <p className="text-sm text-ink-3">Nothing yet. Your actions will show up here.</p>}
            {groups.map((g) => (
              <div key={g.day} className="mb-6">
                <SectionTitle>{g.day}</SectionTitle>
                <ol className="overflow-hidden rounded-2xl border border-line">
                  {g.items.map((a) => (
                    <li key={a.id} className="grid grid-cols-[72px_1fr] items-start gap-3 border-b border-line px-4 py-3 text-sm last:border-0 sm:grid-cols-[96px_1fr]">
                      <span className="pt-0.5 text-[13px] text-ink-3">{fmtTime(a.created_at)}</span>
                      {a.link ? <Link to={a.link} className="min-w-0 text-ink hover:underline">{a.text}</Link> : <span className="min-w-0 text-ink">{a.text}</span>}
                    </li>
                  ))}
                </ol>
              </div>
            ))}
          </section>
        </div>

        {/* Right column: numbers + next deadlines */}
        <aside className="space-y-4">
          <div className="rounded-2xl bg-surface-2 p-5">
            {loading ? <Skeleton className="h-40 w-full" /> : (
              <dl className="space-y-4">
                {[
                  { v: c?.needs_profile ? '-' : c?.overdue ?? 0, l: 'overdue filings', bad: !!c?.overdue },
                  { v: c?.needs_profile ? '-' : c?.due_in_7_days ?? 0, l: 'due in 7 days', bad: false },
                  { v: highRisk, l: 'high-risk contracts', bad: highRisk > 0 },
                  { v: openNotices, l: 'open notices', bad: openNotices > 0 },
                ].map((x) => (
                  <div key={x.l} className="flex items-baseline gap-2.5">
                    <dt className={cn('font-display text-[2.1rem] leading-none', x.bad ? 'text-critical-ink' : 'text-ink')}>{x.v}</dt>
                    <dd className="text-[15px] text-ink-2">{x.l}</dd>
                  </div>
                ))}
              </dl>
            )}
          </div>
          <div className="rounded-2xl bg-surface-2 p-5">
            <div className="mb-3 flex items-center justify-between"><p className="text-[15px] font-semibold text-ink">Next deadlines</p><Link to="/compliance" className="text-xs font-medium text-ink-2 underline-offset-4 hover:underline">Calendar</Link></div>
            {compliance.isLoading && <Skeleton className="h-32 w-full" />}
            {compliance.isError && <ErrorState message={toFriendlyError(compliance.error).message} onRetry={() => compliance.refetch()} />}
            {c?.needs_profile && <p className="text-sm text-ink-2">Finish your <Link to="/onboarding" className="font-medium text-ink underline">company profile</Link> to see deadlines.</p>}
            {c && !c.needs_profile && c.next_deadlines.length === 0 && <p className="text-sm text-ink-2">No upcoming deadlines.</p>}
            {c && c.next_deadlines.length > 0 && (
              <ul className="space-y-3">
                {c.next_deadlines.slice(0, 5).map((d) => (
                  <li key={d.id}><Link to="/compliance" className="flex gap-3">
                    <CalendarClock className={cn('mt-0.5 h-4 w-4 shrink-0', d.days_left <= 7 ? 'text-warn-ink' : 'text-ink-3')} aria-hidden />
                    <span className="min-w-0 flex-1"><span className="block truncate text-sm font-medium text-ink">{d.title}</span><span className="block text-xs text-ink-3">{[formatDate(d.due_date), dueLabel(d.days_left)].join(' · ')}</span></span>
                  </Link></li>
                ))}
              </ul>
            )}
          </div>
        </aside>
      </div>
    </>
  );
};
