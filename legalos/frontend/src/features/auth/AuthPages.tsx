import React, { useState } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { CalendarCheck, Eye, EyeOff, FileSearch, ShieldCheck } from 'lucide-react';
import { Logo, LogoMark } from '@/ui/logo';
import { useSession } from '@/lib/auth/session';
import { toFriendlyError } from '@/api/client';
import { Button, Card, ErrorState, Field, Input } from '@/ui/primitives';

const AuthLayout: React.FC<{ title: string; subtitle: string; children: React.ReactNode }> = ({ title, subtitle, children }) => (
  <div className="grid min-h-screen bg-app lg:grid-cols-[1.05fr_1fr]">
    {/* Brand panel */}
    <div className="relative hidden overflow-hidden bg-ink text-app lg:flex lg:flex-col lg:justify-between lg:p-12 xl:p-16">
      <div className="bg-noise pointer-events-none absolute inset-0" aria-hidden />
      <div className="pointer-events-none absolute inset-0 opacity-[0.07] text-app" aria-hidden
        style={{ backgroundImage: 'linear-gradient(to right, currentColor 1px, transparent 1px), linear-gradient(to bottom, currentColor 1px, transparent 1px)', backgroundSize: '56px 56px', WebkitMaskImage: 'radial-gradient(ellipse at 30% 40%, #000 0%, transparent 75%)', maskImage: 'radial-gradient(ellipse at 30% 40%, #000 0%, transparent 75%)' }} />
      <div className="pointer-events-none absolute -left-40 top-1/3 h-[32rem] w-[32rem] rounded-full bg-primary/30 blur-3xl" aria-hidden />
      <div className="pointer-events-none absolute -bottom-32 right-0 h-80 w-80 rounded-full bg-primary/20 blur-3xl" aria-hidden />
      <div className="relative flex items-center gap-2">
        <LogoMark size={28} className="text-app" />
        <span className="text-[20px] font-semibold tracking-[-0.02em]">LegalOS</span>
      </div>
      <div className="relative">
        <p className="mb-4 text-xs font-medium uppercase tracking-[0.18em] text-app/60">Legal and compliance, run as a system</p>
        <h2 className="max-w-lg font-display text-[2.6rem] font-normal leading-[1.08] tracking-[-0.01em] xl:text-[3.2rem]">
          Every contract read. Every supplier checked. Every deadline on one calendar.
        </h2>
        <ul className="mt-12 grid max-w-xl gap-6">
          {[
            [FileSearch, 'Understand any contract', 'The clauses that could hurt you, quoted from your own document, with what to ask for instead.'],
            [ShieldCheck, 'Check a supplier before you pay', 'GSTIN verified against the live registry. Cancelled or fake registrations are caught in seconds.'],
            [CalendarCheck, 'Never miss a filing', 'GST, TDS, PF, ESI and ROC due dates built from your company profile, with the penalty for missing each one.'],
          ].map(([Icon, head, body]) => {
            const I = Icon as React.ElementType;
            return (
              <li key={head as string} className="flex gap-4">
                <span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-app/15 bg-app/5"><I className="h-4 w-4" aria-hidden /></span>
                <div>
                  <p className="font-medium">{head as string}</p>
                  <p className="mt-0.5 text-sm leading-relaxed text-app/65">{body as string}</p>
                </div>
              </li>
            );
          })}
        </ul>
      </div>
      <p className="relative text-xs text-app/50">Built for Indian small and medium businesses. AI-assisted guidance, not legal advice.</p>
    </div>

    {/* Form panel */}
    <main className="flex items-center justify-center px-4 py-10 sm:px-8" id="main">
      <div className="w-full max-w-[26rem]">
        <div className="mb-10 lg:hidden"><Logo /></div>
        <h1 className="text-[1.9rem] font-semibold leading-tight tracking-[-0.025em] text-ink">{title}</h1>
        <p className="mb-8 mt-2.5 text-[15px] leading-7 text-ink-2">{subtitle}</p>
        {children}
      </div>
    </main>
  </div>
);

const PasswordInput: React.FC<{ id: string; value: string; onChange: (v: string) => void; describedBy?: string; autoComplete: string; invalid?: boolean }> = ({
  id, value, onChange, describedBy, autoComplete, invalid,
}) => {
  const [show, setShow] = useState(false);
  return (
    <div className="relative">
      <Input id={id} type={show ? 'text' : 'password'} value={value} onChange={(e) => onChange(e.target.value)}
        autoComplete={autoComplete} aria-describedby={describedBy} invalid={invalid} className="pr-11" required />
      <button type="button" onClick={() => setShow((s) => !s)} aria-label={show ? 'Hide password' : 'Show password'}
        className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-ink-3 hover:text-ink">
        {show ? <EyeOff className="h-4 w-4" aria-hidden /> : <Eye className="h-4 w-4" aria-hidden />}
      </button>
    </div>
  );
};

const DEMO_LOGIN = { email: 'ramesh@kulkarnitextiles.in', password: 'Kulkarni@2026' };

const DemoButton: React.FC<{ onFill?: (email: string, password: string) => void }> = ({ onFill }) => {
  const { demoAvailable, startDemo } = useSession();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  if (!demoAvailable) return null;
  return (
    <div className="mt-6 rounded-2xl bg-surface-2 p-5">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-3">Demo company</p>
      <p className="mt-1.5 text-sm text-ink-2">Kulkarni Textiles, a 40-person textile business in Surat, with a contract, a legal notice, suppliers and documents already loaded.</p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {onFill && (
          <Button variant="secondary" size="sm" onClick={() => onFill(DEMO_LOGIN.email, DEMO_LOGIN.password)}>Fill demo login</Button>
        )}
        <button type="button" disabled={loading} className="text-sm font-medium text-primary-ink underline-offset-4 hover:underline disabled:opacity-60"
          onClick={async () => { setLoading(true); try { await startDemo('owner'); navigate('/'); } finally { setLoading(false); } }}>
          {loading ? 'Opening…' : 'or open it without signing in'}
        </button>
      </div>
    </div>
  );
};

export const LoginPage: React.FC = () => {
  const { status, login } = useSession();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from || '/';
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (status === 'authenticated') return <Navigate to={from} replace />;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(toFriendlyError(err).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout title="Sign in" subtitle="Welcome back. Pick up where your company left off.">
      <Card className="border border-line bg-surface p-6 shadow-raised sm:p-7">
        <form onSubmit={submit} className="space-y-5" noValidate>
          {error && <ErrorState title="Couldn't sign you in" message={error} />}
          <Field label="Email" required>
            {({ id }) => <Input id={id} type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required />}
          </Field>
          <Field label="Password" required>
            {({ id, describedBy }) => <PasswordInput id={id} value={password} onChange={setPassword} describedBy={describedBy} autoComplete="current-password" />}
          </Field>
          <Button type="submit" size="lg" className="w-full" loading={loading} disabled={!email || !password}>Sign in</Button>
        </form>
        <p className="mt-5 text-center text-sm text-ink-2">
          New to LegalOS? <Link to="/register" className="font-semibold text-primary-ink underline-offset-4 hover:underline">Create an account</Link>
        </p>
      </Card>
      <DemoButton onFill={(e, p) => { setEmail(e); setPassword(p); setError(null); }} />
    </AuthLayout>
  );
};

export const RegisterPage: React.FC = () => {
  const { status, register } = useSession();
  const navigate = useNavigate();
  const [form, setForm] = useState({ full_name: '', company_name: '', email: '', password: '' });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (status === 'authenticated') return <Navigate to="/" replace />;
  const set = (k: keyof typeof form) => (v: string) => setForm((f) => ({ ...f, [k]: v }));
  const passwordTooShort = form.password.length > 0 && form.password.length < 8;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await register(form);
      navigate('/onboarding', { replace: true });
    } catch (err) {
      setError(toFriendlyError(err).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout title="Create your account" subtitle="A clean workspace for your company. Setup takes about two minutes.">
      <Card className="border border-line bg-surface p-6 shadow-raised sm:p-7">
        <form onSubmit={submit} className="space-y-5" noValidate>
          {error && <ErrorState title="Couldn't create your account" message={error} />}
          <Field label="Your name" required>
            {({ id }) => <Input id={id} autoComplete="name" value={form.full_name} onChange={(e) => set('full_name')(e.target.value)} required />}
          </Field>
          <Field label="Company name" required hint="As registered, e.g. Kumar Auto Components Pvt Ltd">
            {({ id, describedBy }) => <Input id={id} autoComplete="organization" aria-describedby={describedBy} value={form.company_name} onChange={(e) => set('company_name')(e.target.value)} required />}
          </Field>
          <Field label="Work email" required>
            {({ id }) => <Input id={id} type="email" autoComplete="email" value={form.email} onChange={(e) => set('email')(e.target.value)} required />}
          </Field>
          <Field label="Password" required hint="At least 8 characters" error={passwordTooShort ? 'Use at least 8 characters.' : undefined}>
            {({ id, describedBy, invalid }) => <PasswordInput id={id} value={form.password} onChange={set('password')} describedBy={describedBy} autoComplete="new-password" invalid={invalid} />}
          </Field>
          <Button type="submit" size="lg" className="w-full" loading={loading}
            disabled={!form.full_name.trim() || !form.company_name.trim() || !form.email || form.password.length < 8}>
            Create account
          </Button>
        </form>
        <p className="mt-5 text-center text-sm text-ink-2">
          Already have an account? <Link to="/login" className="font-semibold text-primary-ink underline-offset-4 hover:underline">Sign in</Link>
        </p>
      </Card>
      <DemoButton />
    </AuthLayout>
  );
};
