/** "Why these filings": the company facts that drive the calendar, each with the rules it switches on.
 *  Edit mode changes the profile live (the server re-syncs the calendar on every change). */
import React, { useState } from 'react';
import { Check, Hourglass, Pencil } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { toFriendlyError } from '@/api/client';
import { Button, ErrorState, Select, Skeleton } from '@/ui/primitives';
import { cn, plural } from '@/lib/utils';
import { EMPLOYEE_BANDS, ENTITY_TYPES, TURNOVER_BANDS, useOrg, useStates, useUpdateOrg, type Org, type OrgUpdate } from '@/features/org/api';
import { KEY, useProfileFacts, type ComplianceTask, type FactRule, type ProfileFact } from './api';

const FREQ = [{ value: 'monthly', label: 'Monthly' }, { value: 'quarterly', label: 'Quarterly (QRMP)' }];

function display(f: ProfileFact, org: Org): string {
  if (f.kind === 'registration') return f.value === 'yes' ? 'Yes' : 'No';
  switch (f.key) {
    case 'entity_type': return ENTITY_TYPES.find((e) => e.value === f.value)?.label ?? 'Not set';
    case 'state_code': return org.state_name ?? 'Not set';
    case 'turnover_band': return TURNOVER_BANDS.find((t) => t.value === f.value)?.label ?? 'Not set';
    case 'gst_filing_frequency': return FREQ.find((t) => t.value === f.value)?.label ?? 'Not set';
    case 'employee_band': return f.value ? `${f.value} employees` : 'Not set';
    default: return f.value ?? '-';
  }
}

const short = (r: FactRule) => r.form || r.title;

const RuleList: React.FC<{ fact: ProfileFact }> = ({ fact }) => {
  const on = fact.rules.filter((r) => r.applies);
  const off = fact.rules.filter((r) => !r.applies);
  if (fact.kind === 'always') return <p className="mt-1 text-xs text-ink-3">{on.map(short).join(', ')}</p>;
  if (fact.rules.length === 0) return null;
  return (
    <div className="mt-1.5 space-y-0.5 text-xs">
      {on.length > 0
        ? <p className="text-ink-2"><span className="font-semibold text-good-ink">Switches on {on.length}: </span>{on.slice(0, 5).map(short).join(', ')}{on.length > 5 ? ` +${on.length - 5} more` : ''}</p>
        : <p className="text-ink-3">Nothing switched on by this right now.</p>}
      {off.length > 0 && on.length === 0 && fact.kind === 'registration' && (
        <p className="text-ink-3">Would add: {off.slice(0, 4).map(short).join(', ')}{off.length > 4 ? ` +${off.length - 4}` : ''}</p>
      )}
      {on.some((r) => !r.verified) && <p className="flex items-center gap-1 italic text-ink-3"><Hourglass className="h-3 w-3" aria-hidden />Some dates are being verified</p>}
    </div>
  );
};

const Switch: React.FC<{ checked: boolean; onChange: (v: boolean) => void; label: string; disabled?: boolean }> = ({ checked, onChange, label, disabled }) => (
  <button role="switch" aria-checked={checked} aria-label={label} disabled={disabled} onClick={() => onChange(!checked)}
    className={cn('relative h-6 w-11 shrink-0 rounded-full transition-colors disabled:opacity-60 max-sm:my-2', checked ? 'bg-primary' : 'bg-line-strong')}>
    <span className={cn('absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform', checked && 'translate-x-5')} />
  </button>
);

export const ProfileRail: React.FC<{
  onApplied: (before: ComplianceTask[] | undefined, after: ComplianceTask[] | undefined) => void;
}> = ({ onApplied }) => {
  const org = useOrg();
  const facts = useProfileFacts();
  const states = useStates();
  const update = useUpdateOrg();
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);

  const apply = (body: OrgUpdate) => {
    const before = qc.getQueryData<ComplianceTask[]>([...KEY, 'tasks']);
    update.mutate(body, {
      onSuccess: async () => {
        await qc.invalidateQueries({ queryKey: KEY });
        onApplied(before, qc.getQueryData<ComplianceTask[]>([...KEY, 'tasks']));
      },
      onError: (e) => toast.error(toFriendlyError(e).message),
    });
  };

  const setReg = (key: string, value: boolean) => {
    const regs = { ...(org.data?.registrations ?? {}), [key]: value };
    if (key === 'gst_composition' && value) regs.gst = true;
    if (key === 'gst' && !value) regs.gst_composition = false;
    apply({ registrations: regs });
  };

  if (org.isLoading || facts.isLoading) return <div className="space-y-3 px-2"><Skeleton className="h-6 w-40" />{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-16" />)}</div>;
  if (org.isError || facts.isError || !org.data || !facts.data) {
    return <div className="px-2"><ErrorState message={toFriendlyError(org.error ?? facts.error).message} onRetry={() => { org.refetch(); facts.refetch(); }} /></div>;
  }
  const o = org.data;
  const d = facts.data;
  const busy = update.isPending;

  const control = (f: ProfileFact): React.ReactNode => {
    if (f.kind === 'registration') return <Switch checked={f.value === 'yes'} disabled={busy} label={f.label} onChange={(v) => setReg(f.key, v)} />;
    const sel = (value: string | null, opts: { value: string; label: string }[], field: keyof OrgUpdate, placeholder = 'Choose') => (
      <Select aria-label={f.label} value={value ?? ''} disabled={busy} className="h-9 w-full max-w-[210px] text-sm"
        onChange={(e) => apply({ [field]: e.target.value || null } as OrgUpdate)}>
        {!value && <option value="">{placeholder}</option>}
        {opts.map((x) => <option key={x.value} value={x.value}>{x.label}</option>)}
      </Select>
    );
    switch (f.key) {
      case 'entity_type': return sel(f.value, ENTITY_TYPES, 'entity_type');
      case 'turnover_band': return sel(f.value, TURNOVER_BANDS, 'turnover_band');
      case 'gst_filing_frequency': return sel(f.value === 'none' ? null : f.value, FREQ, 'gst_filing_frequency');
      case 'employee_band': return sel(f.value, EMPLOYEE_BANDS.map((b) => ({ value: b, label: `${b} employees` })), 'employee_band');
      case 'state_code': return sel(o.state_code, (states.data ?? []).map((s) => ({ value: s.code, label: s.name })), 'state_code');
      default: return null;
    }
  };

  return (
    <div className="px-2 pb-2">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs text-ink-2">{d.rules_applicable} of {d.rules_total} rules apply to {o.trade_name || o.legal_name}.</p>
        </div>
        <Button size="sm" variant={editing ? 'primary' : 'secondary'} onClick={() => setEditing((e) => !e)}
          icon={editing ? <Check className="h-4 w-4" aria-hidden /> : <Pencil className="h-4 w-4" aria-hidden />}>
          {editing ? 'Done' : 'Edit profile'}
        </Button>
      </div>
      {editing && <p className="mt-3 rounded-lg bg-primary-soft px-3 py-2 text-xs text-primary-ink">Change a fact and your calendar updates straight away. Filings you already marked as done are kept.</p>}

      <ul className="mt-4 divide-y divide-line">
        {d.facts.map((f) => (
          <li key={f.key} className="py-3">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="text-xs font-medium text-ink-3">{f.label}</p>
                {!editing && f.kind !== 'always' && <p className="text-sm font-semibold text-ink">{display(f, o)}</p>}
              </div>
              {editing && f.kind !== 'always' && <div className="flex min-w-0 flex-1 justify-end">{control(f)}</div>}
            </div>
            {f.hint && <p className="mt-1 text-xs text-ink-3">{f.hint}</p>}
            <RuleList fact={f} />
          </li>
        ))}
      </ul>
      {busy && <p role="status" className="mt-2 text-xs text-ink-3">Updating your calendar…</p>}
      <p className="mt-3 text-xs text-ink-3">{plural(d.rules_total - d.rules_applicable, 'rule')} switched off for your profile. Standard due dates; confirm with your CA.</p>
    </div>
  );
};
