import React, { useId, useRef, useState } from 'react';
import { AlertCircle, CheckCircle2, FileUp, Info, Loader2, RefreshCw } from 'lucide-react';
import { cn, fileSize } from '@/lib/utils';

/* ------------------------------------------------------------------ Button */

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  icon?: React.ReactNode;
}

const buttonVariants: Record<ButtonVariant, string> = {
  primary: 'btn-raised bg-primary text-primary-on hover:bg-primary-hover',
  secondary: 'btn-quiet bg-surface text-ink border border-line-strong hover:bg-surface-2',
  ghost: 'text-ink-2 hover:bg-surface-2 hover:text-ink',
  danger: 'btn-raised bg-critical text-white hover:opacity-90',
};
const buttonSizes: Record<ButtonSize, string> = {
  sm: 'h-9 px-3.5 text-[13px] gap-1.5',
  md: 'h-10 px-4 text-sm gap-2',
  lg: 'h-12 px-6 text-[15px] gap-2',
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'primary', size = 'md', loading, icon, className, children, disabled, type = 'button', ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        'inline-flex items-center justify-center rounded-xl font-medium tracking-[-0.005em] transition-[background-color,box-shadow,transform,filter] duration-150 select-none',
        'disabled:cursor-not-allowed disabled:opacity-55 max-sm:min-h-[44px]',
        buttonVariants[variant],
        buttonSizes[size],
        className,
      )}
      {...rest}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : icon}
      {children}
    </button>
  );
});

/* ------------------------------------------------------------------ Card */

export const Card: React.FC<React.HTMLAttributes<HTMLDivElement> & { padded?: boolean }> = ({
  className, padded = true, ...rest
}) => (
  <div className={cn('rounded-2xl bg-surface-2', padded && 'p-5', className)} {...rest} />
);

export const SectionTitle: React.FC<{ children: React.ReactNode; action?: React.ReactNode; id?: string }> = ({
  children, action, id,
}) => (
  <div className="mb-3 flex items-center justify-between gap-3">
    <h2 id={id} className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-2">{children}</h2>
    {action}
  </div>
);

/* ------------------------------------------------------------------ Badge */

type Tone = 'neutral' | 'info' | 'good' | 'warn' | 'serious' | 'critical';
const toneClasses: Record<Tone, string> = {
  neutral: 'bg-surface-2 text-ink-2 border-line',
  info: 'bg-primary-soft text-primary-ink border-transparent',
  good: 'bg-good-soft text-good-ink border-transparent',
  warn: 'bg-warn-soft text-warn-ink border-transparent',
  serious: 'bg-serious-soft text-serious-ink border-transparent',
  critical: 'bg-critical-soft text-critical-ink border-transparent',
};

export const Badge: React.FC<{ tone?: Tone; icon?: React.ReactNode; children: React.ReactNode; className?: string }> = ({
  tone = 'neutral', icon, children, className,
}) => (
  <span className={cn('inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium', toneClasses[tone], className)}>
    {icon}
    {children}
  </span>
);

/* ------------------------------------------------------------------ Form fields */

interface FieldProps {
  label: string;
  hint?: string;
  error?: string;
  required?: boolean;
  children: (p: { id: string; describedBy?: string; invalid: boolean }) => React.ReactNode;
}

export const Field: React.FC<FieldProps> = ({ label, hint, error, required, children }) => {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  const errId = error ? `${id}-err` : undefined;
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-medium text-ink">
        {label}
        {required && <span className="text-critical-ink" aria-hidden> *</span>}
      </label>
      {children({ id, describedBy: [hintId, errId].filter(Boolean).join(' ') || undefined, invalid: !!error })}
      {hint && !error && <p id={hintId} className="text-xs text-ink-3">{hint}</p>}
      {error && <p id={errId} role="alert" className="flex items-center gap-1 text-xs font-medium text-critical-ink"><AlertCircle className="h-3.5 w-3.5" aria-hidden />{error}</p>}
    </div>
  );
};

const inputBase =
  'field-inset w-full rounded-lg border bg-surface px-3 text-sm text-ink placeholder:text-ink-3 transition-[border-color,box-shadow] ' +
  'focus:border-primary focus:outline-none disabled:cursor-not-allowed disabled:opacity-60 max-sm:min-h-[44px]';

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }>(
  function Input({ className, invalid, ...rest }, ref) {
    return <input ref={ref} aria-invalid={invalid || undefined} className={cn(inputBase, 'h-10', invalid ? 'border-critical' : 'border-line-strong', className)} {...rest} />;
  },
);

export const Select = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement> & { invalid?: boolean }>(
  function Select({ className, invalid, children, ...rest }, ref) {
    return (
      <select ref={ref} aria-invalid={invalid || undefined} className={cn(inputBase, 'h-10 pr-8', invalid ? 'border-critical' : 'border-line-strong', className)} {...rest}>
        {children}
      </select>
    );
  },
);

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ className, ...rest }, ref) {
    return <textarea ref={ref} className={cn(inputBase, 'min-h-[88px] border-line-strong py-2', className)} {...rest} />;
  },
);

/* ------------------------------------------------------------------ States */

export const Spinner: React.FC<{ label?: string; className?: string }> = ({ label = 'Loading', className }) => (
  <span role="status" className={cn('inline-flex items-center gap-2 text-sm text-ink-2', className)}>
    <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
    {label}
  </span>
);

export const Skeleton: React.FC<{ className?: string }> = ({ className }) => (
  <div aria-hidden className={cn('skeleton rounded-md bg-surface-2', className)} />
);

/** Reference-style loading rows: a circle and two lines, used while a list or tab loads. */
export const SkeletonRows: React.FC<{ rows?: number; className?: string }> = ({ rows = 3, className }) => (
  <div aria-hidden className={cn('space-y-5 py-2', className)}>
    {Array.from({ length: rows }).map((_, i) => (
      <div key={i} className="flex items-center gap-4">
        <div className="skeleton h-7 w-7 shrink-0 rounded-full bg-surface-2" />
        <div className="flex-1 space-y-2"><div className="skeleton h-2.5 w-2/5 rounded-full bg-surface-2" /><div className="skeleton h-2.5 w-3/5 rounded-full bg-surface-2" /></div>
      </div>
    ))}
  </div>
);

export const EmptyState: React.FC<{
  icon?: React.ReactNode; title: string; description?: string; action?: React.ReactNode; className?: string;
}> = ({ icon, title, description, action, className }) => (
  <div className={cn('flex flex-col items-center rounded-2xl bg-surface-2 px-6 py-12 text-center', className)}>
    {icon && <div className="mb-3 flex h-10 w-10 items-center justify-center text-ink-2" aria-hidden>{icon}</div>}
    <h3 className="text-base font-medium text-ink">{title}</h3>
    {description && <p className="mt-1 max-w-md text-sm text-ink-2">{description}</p>}
    {action && <div className="mt-4">{action}</div>}
  </div>
);

export const ErrorState: React.FC<{
  title?: string; message: string; onRetry?: () => void; retrying?: boolean; className?: string;
}> = ({ title = 'Something went wrong', message, onRetry, retrying, className }) => (
  <div role="alert" className={cn('flex items-start gap-3 rounded-xl border border-critical/40 bg-critical-soft p-4', className)}>
    <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-critical-ink" aria-hidden />
    <div className="min-w-0 flex-1">
      <p className="font-semibold text-critical-ink">{title}</p>
      <p className="mt-0.5 text-sm text-ink-2">{message}</p>
      {onRetry && (
        <Button className="mt-3" size="sm" variant="secondary" loading={retrying} icon={<RefreshCw className="h-4 w-4" aria-hidden />} onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  </div>
);

export const Notice: React.FC<{ tone?: 'info' | 'warn' | 'good'; title?: string; children: React.ReactNode; className?: string }> = ({
  tone = 'info', title, children, className,
}) => {
  const styles = { info: 'bg-primary-soft text-primary-ink', warn: 'bg-warn-soft text-warn-ink', good: 'bg-good-soft text-good-ink' }[tone];
  const Icon = tone === 'good' ? CheckCircle2 : tone === 'warn' ? AlertCircle : Info;
  return (
    <div className={cn('flex gap-3 rounded-xl p-3.5 text-sm', styles, className)} role={tone === 'warn' ? 'alert' : 'note'}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <div className="min-w-0">
        {title && <p className="font-semibold">{title}</p>}
        <div className={cn(title && 'mt-0.5')}>{children}</div>
      </div>
    </div>
  );
};

export const AiDisclaimer: React.FC<{ className?: string }> = ({ className }) => (
  <p className={cn('flex items-start gap-2 text-xs text-ink-3', className)}>
    <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
    AI-assisted review to help you decide what to ask about. It is not legal advice; have a lawyer or CA check anything important before you sign or reply.
  </p>
);

/* ------------------------------------------------------------------ Page header / stat tile */

export const PageHeader: React.FC<{
  title: string; subtitle?: string; actions?: React.ReactNode; back?: React.ReactNode; badges?: React.ReactNode;
}> = ({ title, subtitle, actions, back, badges }) => (
  <header className="mb-6">
    {back && <div className="mb-2">{back}</div>}
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <h1 className="text-[1.65rem] font-semibold tracking-[-0.02em] text-ink">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-ink-2">{subtitle}</p>}
        {badges && <div className="mt-2 flex flex-wrap gap-2">{badges}</div>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  </header>
);

export const StatTile: React.FC<{ label: string; value: React.ReactNode; hint?: string; tone?: Tone }> = ({
  label, value, hint, tone = 'neutral',
}) => (
  <div className="rounded-2xl border border-line bg-surface p-5">
    <p className={cn('text-[2rem] font-medium leading-none tracking-[-0.02em]', tone === 'critical' ? 'text-critical-ink' : tone === 'good' ? 'text-good-ink' : 'text-ink')}>{value}</p>
    <p className="mt-2.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-2">{label}</p>
    {hint && <p className="mt-1 text-xs text-ink-3">{hint}</p>}
  </div>
);

/* ------------------------------------------------------------------ Progress steps */

export const ProgressSteps: React.FC<{
  steps: { key: string; label: string }[]; current: string | null | undefined; className?: string;
}> = ({ steps, current, className }) => {
  const idx = Math.max(0, steps.findIndex((s) => s.key === current));
  return (
    <ol className={cn('space-y-3', className)} aria-label="Progress">
      {steps.map((s, i) => {
        const done = i < idx;
        const active = i === idx;
        return (
          <li key={s.key} className="flex items-center gap-3" aria-current={active ? 'step' : undefined}>
            <span className={cn(
              'flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-xs font-semibold',
              done && 'border-good bg-good-soft text-good-ink',
              active && 'border-primary bg-primary-soft text-primary-ink',
              !done && !active && 'border-line text-ink-3',
            )}>
              {done ? <CheckCircle2 className="h-4 w-4" aria-hidden /> : active ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : i + 1}
            </span>
            <span className={cn('text-sm', active ? 'font-semibold text-ink' : done ? 'text-ink-2' : 'text-ink-3')}>
              {s.label}
              <span className="sr-only">{done ? ' (done)' : active ? ' (in progress)' : ' (waiting)'}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
};

/* ------------------------------------------------------------------ Dropzone */

export const Dropzone: React.FC<{
  accept: string;
  file: File | null;
  onFile: (f: File | null) => void;
  disabled?: boolean;
  hint?: string;
}> = ({ accept, file, onFile, disabled, hint }) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const id = useId();

  const pick = (f: File | undefined | null) => {
    if (f) onFile(f);
  };

  return (
    <div>
      <label
        htmlFor={id}
        onDragOver={(e) => { e.preventDefault(); if (!disabled) setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); if (!disabled) pick(e.dataTransfer.files?.[0]); }}
        className={cn(
          'flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-4 py-10 text-center transition-colors',
          'focus-within:outline focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-[var(--ring)]',
          over ? 'border-primary bg-primary-soft' : 'border-line-strong bg-surface hover:bg-surface-2',
          disabled && 'cursor-not-allowed opacity-60',
        )}
      >
        <FileUp className="mb-2 h-8 w-8 text-primary-ink" aria-hidden />
        {file ? (
          <>
            <span className="font-semibold text-ink">{file.name}</span>
            <span className="text-sm text-ink-2">{fileSize(file.size)} · click to choose a different file</span>
          </>
        ) : (
          <>
            <span className="font-semibold text-ink">Drop a file here, or click to choose</span>
            <span className="text-sm text-ink-2">{hint}</span>
          </>
        )}
        <input
          id={id}
          ref={inputRef}
          type="file"
          accept={accept}
          disabled={disabled}
          className="sr-only"
          onChange={(e) => { pick(e.target.files?.[0]); e.target.value = ''; }}
        />
      </label>
    </div>
  );
};
