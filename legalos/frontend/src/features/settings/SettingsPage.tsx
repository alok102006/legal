import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import * as Dialog from '@radix-ui/react-dialog';
import { Building2, CircleUserRound, Cpu, LogOut, Pencil, X } from 'lucide-react';
import { toFriendlyError } from '@/api/client';
import { useHealth } from '@/api/health';
import { useSession } from '@/lib/auth/session';
import { cn } from '@/lib/utils';
import { Badge, Button, ErrorState, Skeleton } from '@/ui/primitives';
import { ENTITY_TYPES, MSME_OPTIONS, REGISTRATIONS, TURNOVER_BANDS, useOrg } from '@/features/org/api';

type Section = 'company' | 'system' | 'account';

const NAV: { group: string; items: { key: Section; label: string; icon: React.ElementType }[] }[] = [
  { group: 'Settings', items: [{ key: 'company', label: 'Company', icon: Building2 }, { key: 'system', label: 'System', icon: Cpu }] },
  { group: 'Account', items: [{ key: 'account', label: 'Account', icon: CircleUserRound }] },
];

const Row: React.FC<{ label: string; value: React.ReactNode }> = ({ label, value }) => (
  <div className="flex items-start justify-between gap-6 border-b border-line py-3 last:border-0">
    <dt className="text-sm text-ink-2">{label}</dt>
    <dd className="text-right text-sm font-medium text-ink">{value || <span className="text-ink-3">Not set</span>}</dd>
  </div>
);

const Company: React.FC = () => {
  const { data: org, isLoading, isError, error, refetch } = useOrg();
  return (
    <>
      <div className="mb-6 flex items-start justify-between gap-4 pr-10">
        <h2 className="font-display text-[2rem] leading-none text-ink">Company</h2>
        <Link to="/onboarding" className="inline-flex h-9 items-center gap-2 rounded-xl border border-line-strong bg-surface px-3.5 text-[13px] font-medium text-ink btn-quiet"><Pencil className="h-3.5 w-3.5" aria-hidden />Edit profile</Link>
      </div>
      {isLoading && <Skeleton className="h-64 w-full" />}
      {isError && <ErrorState message={toFriendlyError(error).message} onRetry={() => refetch()} />}
      {org && (
        <dl className="rounded-2xl bg-surface-2 px-5 py-1">
          <Row label="Company" value={org.legal_name} />
          <Row label="Type" value={ENTITY_TYPES.find((e) => e.value === org.entity_type)?.label} />
          <Row label="State" value={org.state_name} />
          <Row label="GSTIN" value={org.gstin && <span className="font-mono">{org.gstin}</span>} />
          <Row label="PAN" value={org.pan && <span className="font-mono">{org.pan}</span>} />
          <Row label="Industry" value={org.industry} />
          <Row label="Employees" value={org.employee_band} />
          <Row label="Turnover" value={TURNOVER_BANDS.find((t) => t.value === org.turnover_band)?.label} />
          <Row label="MSME status" value={MSME_OPTIONS.find((m) => m.value === org.msme_category)?.label} />
          <Row label="Registrations" value={REGISTRATIONS.filter((r) => org.registrations?.[r.key]).map((r) => r.label).join(', ')} />
        </dl>
      )}
    </>
  );
};

const System: React.FC = () => {
  const { data: health } = useHealth();
  const Line: React.FC<{ label: React.ReactNode; ok: boolean; okText?: string; badText?: string; tone?: 'critical' | 'warn' }> = ({ label, ok, okText = 'Working', badText = 'Down', tone = 'critical' }) => (
    <div className="flex items-center justify-between gap-4 border-b border-line py-3.5 last:border-0">
      <span className="text-sm text-ink">{label}</span>
      {ok ? <Badge tone="good">{okText}</Badge> : <Badge tone={tone}>{badText}</Badge>}
    </div>
  );
  return (
    <>
      <h2 className="mb-6 font-display text-[2rem] leading-none text-ink">System</h2>
      {!health ? <Skeleton className="h-40 w-full" /> : (
        <div className="rounded-2xl bg-surface-2 px-5 py-1">
          <Line label="Database" ok={health.checks.database.ok} />
          <Line label="Document search" ok={health.checks.vector_store.ok} />
          <Line label={<>AI analysis{health.checks.llm.model ? <span className="text-ink-3"> · {health.checks.llm.model}</span> : null}</>} ok={health.checks.llm.ok} badText={health.checks.llm.message ?? 'Unavailable'} />
          <Line label="GST registry lookups" ok={!!health.checks.registry.live} okText="Live" badText="Offline checks only" tone="warn" />
        </div>
      )}
      <p className="mt-4 text-xs text-ink-3">AI output is decision support, not legal advice. Every finding shows the text or rule it rests on.</p>
    </>
  );
};

const Account: React.FC = () => {
  const { user, logout } = useSession();
  if (!user) return null;
  const initials = user.full_name.split(' ').map((p) => p[0]).slice(0, 2).join('').toUpperCase();
  return (
    <>
      <h2 className="mb-6 font-display text-[2rem] leading-none text-ink">Account</h2>
      <div className="flex items-center gap-4 rounded-2xl bg-surface-2 p-5">
        <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-peach text-base font-semibold text-peach-ink" aria-hidden>{initials}</span>
        <span className="min-w-0"><span className="block truncate text-[15px] font-semibold text-ink">{user.full_name}</span><span className="block truncate text-sm text-ink-2">{user.is_demo ? 'Sample company account' : user.email}</span></span>
      </div>
      <Button variant="secondary" className="mt-5" icon={<LogOut className="h-4 w-4" aria-hidden />} onClick={logout}>Sign out</Button>
    </>
  );
};

/** Settings opens as a modal over whatever the user was looking at, like the reference app. */
export const SettingsPage: React.FC = () => {
  const navigate = useNavigate();
  const [section, setSection] = useState<Section>('company');
  const location = useLocation();
  const close = () => { if ((location.state as { background?: unknown } | null)?.background) navigate(-1); else navigate('/', { replace: true }); };
  return (
    <Dialog.Root open onOpenChange={(o) => { if (!o) close(); }}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/30" />
        <Dialog.Content aria-describedby={undefined}
          className="fixed left-1/2 top-1/2 z-50 flex h-[min(620px,calc(100vh-2rem))] w-[calc(100vw-1.5rem)] max-w-[840px] -translate-x-1/2 -translate-y-1/2 overflow-hidden rounded-3xl bg-surface shadow-float animate-scale-in [--origin:top_right] max-sm:flex-col">
          <Dialog.Title className="sr-only">Settings</Dialog.Title>
          <aside className="flex w-full shrink-0 flex-col bg-surface-2/70 p-4 sm:w-[220px] sm:p-5">
            {NAV.map((g) => (
              <div key={g.group} className="mb-5">
                <p className="mb-2 px-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-2">{g.group}</p>
                <div className="space-y-0.5">
                  {g.items.map((i) => (
                    <button key={i.key} onClick={() => setSection(i.key)} aria-current={section === i.key || undefined}
                      className={cn('flex h-9 w-full items-center gap-2.5 rounded-xl px-2 text-[14px] font-medium transition-colors', section === i.key ? 'bg-surface text-ink shadow-card' : 'text-ink hover:bg-surface')}>
                      <i.icon className="h-4 w-4 text-ink-2" strokeWidth={1.9} aria-hidden />{i.label}
                    </button>
                  ))}
                </div>
              </div>
            ))}
            <p className="mt-auto px-2 text-[11px] text-ink-3">LegalOS v0.9 · review build</p>
          </aside>
          <div className="relative min-w-0 flex-1 overflow-y-auto p-6 sm:p-8">
            <Dialog.Close asChild>
              <button className="absolute right-5 top-7 flex h-8 w-8 items-center justify-center rounded-lg text-ink-3 hover:bg-surface-2 hover:text-ink" aria-label="Close"><X className="h-4 w-4" aria-hidden /></button>
            </Dialog.Close>
            {section === 'company' && <Company />}
            {section === 'system' && <System />}
            {section === 'account' && <Account />}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
};
