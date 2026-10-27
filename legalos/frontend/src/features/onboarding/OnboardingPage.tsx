import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, ArrowRight, CheckCircle2, Search } from 'lucide-react';
import { toast } from 'sonner';
import { toFriendlyError } from '@/api/client';
import { useSession } from '@/lib/auth/session';
import { Button, Card, ErrorState, Field, Input, Notice, Select } from '@/ui/primitives';
import {
  EMPLOYEE_BANDS, ENTITY_TYPES, MSME_OPTIONS, REGISTRATIONS, TURNOVER_BANDS, entityLabel,
  useGstinCheck, useOrg, useStates, useUpdateOrg, type GstinCheck, type OrgUpdate,
} from '@/features/org/api';

interface Form {
  legal_name: string;
  entity_type: string;
  state_code: string;
  gstin: string;
  industry: string;
  employee_band: string;
  turnover_band: string;
  msme_category: string;
  udyam_number: string;
  gst_filing_frequency: string;
  registrations: Record<string, boolean>;
}

const EMPTY: Form = {
  legal_name: '', entity_type: '', state_code: '', gstin: '', industry: '', employee_band: '', turnover_band: '',
  msme_category: '', udyam_number: '', gst_filing_frequency: '', registrations: {},
};

const INDUSTRIES = ['Manufacturing', 'Trading / Distribution', 'IT / Software services', 'Professional services', 'Retail', 'Construction / Real estate', 'Healthcare', 'Education', 'Food & hospitality', 'Logistics / Transport', 'Agriculture', 'Other'];

export const OnboardingPage: React.FC = () => {
  const { data: org, isLoading, isError, refetch } = useOrg();
  const { data: states } = useStates();
  const update = useUpdateOrg();
  const gstinCheck = useGstinCheck();
  const { refresh } = useSession();
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [form, setForm] = useState<Form>(EMPTY);
  const [gstinInfo, setGstinInfo] = useState<GstinCheck | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!org) return;
    setForm((f) => ({
      ...f,
      legal_name: org.legal_name, entity_type: org.entity_type ?? '', state_code: org.state_code ?? '',
      gstin: org.gstin ?? '', industry: org.industry ?? '', employee_band: org.employee_band ?? '',
      turnover_band: org.turnover_band ?? '', msme_category: org.msme_category ?? '', udyam_number: org.udyam_number ?? '',
      gst_filing_frequency: org.gst_filing_frequency ?? '', registrations: org.registrations ?? {},
    }));
  }, [org]);

  const set = <K extends keyof Form>(k: K, v: Form[K]) => setForm((f) => ({ ...f, [k]: v }));

  const checkGstin = async () => {
    setError(null);
    try {
      const info = await gstinCheck.mutateAsync(form.gstin);
      setGstinInfo(info);
      if (info.valid) {
        setForm((f) => ({
          ...f,
          gstin: info.gstin,
          state_code: f.state_code || info.state_code || '',
          entity_type: f.entity_type || info.entity_hint || '',
          registrations: { ...f.registrations, gst: true },
        }));
      }
    } catch (e) {
      setError(toFriendlyError(e).message);
    }
  };

  const step1Valid = form.legal_name.trim().length >= 2 && !!form.entity_type && !!form.state_code;
  const step2Valid = !!form.employee_band && !!form.turnover_band && !!form.msme_category;

  const finish = async () => {
    setError(null);
    const body: OrgUpdate = {
      legal_name: form.legal_name.trim(), entity_type: form.entity_type, state_code: form.state_code,
      industry: form.industry || null, employee_band: form.employee_band, turnover_band: form.turnover_band,
      msme_category: form.msme_category, gst_filing_frequency: form.gst_filing_frequency || null,
      registrations: form.registrations,
    };
    if (form.gstin.trim()) body.gstin = form.gstin.trim();
    if (form.udyam_number.trim()) body.udyam_number = form.udyam_number.trim();
    try {
      await update.mutateAsync(body);
      await refresh();
      toast.success('Your company profile is saved.');
      navigate('/', { replace: true });
    } catch (e) {
      setError(toFriendlyError(e).message);
      setStep(1);
    }
  };

  if (isLoading) return <div className="p-10 text-center text-ink-2">Loading…</div>;
  if (isError) return <div className="mx-auto max-w-lg p-6"><ErrorState message="We couldn't load your company profile." onRetry={() => refetch()} /></div>;

  return (
    <div className="mx-auto flex min-h-screen max-w-2xl flex-col px-4 py-8 sm:py-12">
      <h1 className="text-2xl font-bold text-ink">Tell us about your company</h1>
      <p className="mt-1 text-sm text-ink-2">
        This decides which compliance deadlines and contract rules apply to you. You can change it later in Settings.
      </p>

      <div className="my-6" aria-label={`Step ${step} of 3`}>
        <div className="flex gap-2" aria-hidden>
          {[1, 2, 3].map((n) => <div key={n} className={`h-1.5 flex-1 rounded-full ${n <= step ? 'bg-primary' : 'bg-surface-2'}`} />)}
        </div>
        <p className="mt-2 text-xs font-medium text-ink-3">Step {step} of 3 · {['About your company', 'Size and registrations', 'Review'][step - 1]}</p>
      </div>

      <Card className="space-y-5">
        {error && <ErrorState title="Couldn't save" message={error} />}

        {step === 1 && (
          <>
            <Field label="Company name" required>
              {({ id }) => <Input id={id} value={form.legal_name} onChange={(e) => set('legal_name', e.target.value)} />}
            </Field>
            <div className="grid gap-5 sm:grid-cols-2">
              <Field label="Type of business" required>
                {({ id }) => (
                  <Select id={id} value={form.entity_type} onChange={(e) => set('entity_type', e.target.value)}>
                    <option value="">Choose…</option>
                    {ENTITY_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                  </Select>
                )}
              </Field>
              <Field label="State of registered office" required>
                {({ id }) => (
                  <Select id={id} value={form.state_code} onChange={(e) => set('state_code', e.target.value)}>
                    <option value="">Choose…</option>
                    {(states ?? []).map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
                  </Select>
                )}
              </Field>
            </div>
            <Field label="GSTIN (optional)" hint="We check the format and fill in your state and PAN. Nothing is sent to the GST portal.">
              {({ id, describedBy }) => (
                <div className="flex gap-2">
                  <Input id={id} aria-describedby={describedBy} value={form.gstin} placeholder="15-character GSTIN"
                    onChange={(e) => { set('gstin', e.target.value.toUpperCase()); setGstinInfo(null); }} className="font-mono uppercase" maxLength={15} />
                  <Button variant="secondary" onClick={checkGstin} loading={gstinCheck.isPending} disabled={form.gstin.length < 15} icon={<Search className="h-4 w-4" aria-hidden />}>
                    Check
                  </Button>
                </div>
              )}
            </Field>
            {gstinInfo && (
              gstinInfo.valid ? (
                <Notice tone="good" title="GSTIN format is valid">
                  State: {gstinInfo.state_name} · PAN: {gstinInfo.pan} · Holder type: {gstinInfo.holder_type}. {gstinInfo.note}
                </Notice>
              ) : (
                <Notice tone="warn" title="This GSTIN doesn't look right">{gstinInfo.error}</Notice>
              )
            )}
            <Field label="What does your business do?">
              {({ id }) => (
                <Select id={id} value={form.industry} onChange={(e) => set('industry', e.target.value)}>
                  <option value="">Choose…</option>
                  {INDUSTRIES.map((i) => <option key={i} value={i}>{i}</option>)}
                </Select>
              )}
            </Field>
          </>
        )}

        {step === 2 && (
          <>
            <div className="grid gap-5 sm:grid-cols-2">
              <Field label="Number of employees" required>
                {({ id }) => (
                  <Select id={id} value={form.employee_band} onChange={(e) => set('employee_band', e.target.value)}>
                    <option value="">Choose…</option>
                    {EMPLOYEE_BANDS.map((b) => <option key={b} value={b}>{b}</option>)}
                  </Select>
                )}
              </Field>
              <Field label="Yearly turnover" required>
                {({ id }) => (
                  <Select id={id} value={form.turnover_band} onChange={(e) => set('turnover_band', e.target.value)}>
                    <option value="">Choose…</option>
                    {TURNOVER_BANDS.map((b) => <option key={b.value} value={b.value}>{b.label}</option>)}
                  </Select>
                )}
              </Field>
            </div>
            <div className="grid gap-5 sm:grid-cols-2">
              <Field label="MSME (Udyam) status" required hint="Matters for payment-time rules in your contracts.">
                {({ id, describedBy }) => (
                  <Select id={id} aria-describedby={describedBy} value={form.msme_category} onChange={(e) => set('msme_category', e.target.value)}>
                    <option value="">Choose…</option>
                    {MSME_OPTIONS.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
                  </Select>
                )}
              </Field>
              {['micro', 'small', 'medium'].includes(form.msme_category) && (
                <Field label="Udyam number (optional)" hint="Format: UDYAM-MH-26-0012345">
                  {({ id, describedBy }) => <Input id={id} aria-describedby={describedBy} value={form.udyam_number} onChange={(e) => set('udyam_number', e.target.value.toUpperCase())} className="font-mono" />}
                </Field>
              )}
            </div>
            <Field label="How do you file GST returns?">
              {({ id }) => (
                <Select id={id} value={form.gst_filing_frequency} onChange={(e) => set('gst_filing_frequency', e.target.value)}>
                  <option value="">Not sure / not registered</option>
                  <option value="monthly">Monthly</option>
                  <option value="quarterly">Quarterly (QRMP)</option>
                  <option value="none">Not registered for GST</option>
                </Select>
              )}
            </Field>
            <fieldset>
              <legend className="mb-2 text-sm font-medium text-ink">Which registrations does your company have?</legend>
              <div className="grid gap-2 sm:grid-cols-2">
                {REGISTRATIONS.map((r) => (
                  <label key={r.key} className="flex min-h-[44px] cursor-pointer items-start gap-3 rounded-lg border border-line p-3 hover:bg-surface-2">
                    <input type="checkbox" className="mt-1 h-4 w-4 accent-[var(--primary)]" checked={!!form.registrations[r.key]}
                      onChange={(e) => set('registrations', { ...form.registrations, [r.key]: e.target.checked })} />
                    <span>
                      <span className="block text-sm font-medium text-ink">{r.label}</span>
                      <span className="block text-xs text-ink-3">{r.hint}</span>
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>
          </>
        )}

        {step === 3 && (
          <div className="space-y-4">
            <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
              {[
                ['Company', form.legal_name],
                ['Type', entityLabel(form.entity_type)],
                ['State', states?.find((s) => s.code === form.state_code)?.name ?? '-'],
                ['GSTIN', form.gstin || 'Not provided'],
                ['Employees', form.employee_band || '-'],
                ['Turnover', TURNOVER_BANDS.find((t) => t.value === form.turnover_band)?.label ?? '-'],
                ['MSME status', MSME_OPTIONS.find((m) => m.value === form.msme_category)?.label ?? '-'],
                ['Registrations', REGISTRATIONS.filter((r) => form.registrations[r.key]).map((r) => r.label).join(', ') || 'None selected'],
              ].map(([k, v]) => (
                <div key={k}><dt className="text-ink-3">{k}</dt><dd className="font-medium text-ink">{v}</dd></div>
              ))}
            </dl>
            <Notice tone="info">We use this only to decide which rules and deadlines apply to you. Contracts and documents you upload stay inside your company's account.</Notice>
          </div>
        )}

        <div className="flex items-center justify-between border-t border-line pt-4">
          <Button variant="ghost" onClick={() => setStep((s) => s - 1)} disabled={step === 1} icon={<ArrowLeft className="h-4 w-4" aria-hidden />}>Back</Button>
          {step < 3 ? (
            <Button onClick={() => setStep((s) => s + 1)} disabled={step === 1 ? !step1Valid : !step2Valid}>
              Continue <ArrowRight className="h-4 w-4" aria-hidden />
            </Button>
          ) : (
            <Button onClick={finish} loading={update.isPending} icon={<CheckCircle2 className="h-4 w-4" aria-hidden />}>Finish setup</Button>
          )}
        </div>
      </Card>
    </div>
  );
};
