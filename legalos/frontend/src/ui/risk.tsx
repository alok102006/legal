import React from 'react';
import { AlertOctagon, AlertTriangle, CheckCircle2, Info, ShieldAlert } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Badge } from './primitives';

export type Severity = 'critical' | 'high' | 'medium' | 'low';
export type RiskLevel = 'low' | 'medium' | 'high';

/** Severity is never colour-only: every level has its own icon and label. */
const SEVERITY: Record<Severity, { label: string; tone: 'critical' | 'serious' | 'warn' | 'info'; Icon: React.ElementType }> = {
  critical: { label: 'Critical', tone: 'critical', Icon: AlertOctagon },
  high: { label: 'High', tone: 'serious', Icon: AlertTriangle },
  medium: { label: 'Medium', tone: 'warn', Icon: ShieldAlert },
  low: { label: 'Low', tone: 'info', Icon: Info },
};

export const SEVERITY_ORDER: Severity[] = ['critical', 'high', 'medium', 'low'];

export const SeverityBadge: React.FC<{ severity: Severity; className?: string }> = ({ severity, className }) => {
  const s = SEVERITY[severity];
  return (
    <Badge tone={s.tone} className={className} icon={<s.Icon className="h-3.5 w-3.5" aria-hidden />}>
      {s.label}
    </Badge>
  );
};

const LEVEL: Record<RiskLevel, { label: string; fill: string; track: string; ink: string; Icon: React.ElementType }> = {
  low: { label: 'Low risk', fill: 'var(--good)', track: 'var(--good-soft)', ink: 'text-good-ink', Icon: CheckCircle2 },
  medium: { label: 'Medium risk', fill: 'var(--warn)', track: 'var(--warn-soft)', ink: 'text-warn-ink', Icon: ShieldAlert },
  high: { label: 'High risk', fill: 'var(--critical)', track: 'var(--critical-soft)', ink: 'text-critical-ink', Icon: AlertOctagon },
};

/**
 * Meter: the fill carries the level, the track is the same hue's lighter step.
 * The number and the words (with an icon) carry the meaning, so colour is never the only cue.
 */
export const RiskMeter: React.FC<{ score: number; level: RiskLevel; className?: string }> = ({ score, level, className }) => {
  const l = LEVEL[level];
  const pct = Math.max(0, Math.min(100, score));
  return (
    <div className={className}>
      <div className="flex items-baseline gap-2">
        <span className="text-5xl font-bold leading-none text-ink">{score}</span>
        <span className="text-sm text-ink-3">out of 100</span>
      </div>
      <div
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        aria-label={`Risk score ${score} out of 100, ${l.label}`}
        className="mt-3 h-3 w-full overflow-hidden rounded-full"
        style={{ background: l.track }}
      >
        <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, background: l.fill }} />
      </div>
      <p className={cn('mt-2 flex items-center gap-1.5 text-sm font-semibold', l.ink)}>
        <l.Icon className="h-4 w-4" aria-hidden />
        {l.label}
      </p>
    </div>
  );
};

export const RiskLevelBadge: React.FC<{ level: RiskLevel | null | undefined; score?: number | null }> = ({ level, score }) => {
  if (!level) return <Badge tone="neutral">Not scored</Badge>;
  const l = LEVEL[level];
  const tone = level === 'high' ? 'critical' : level === 'medium' ? 'warn' : 'good';
  return (
    <Badge tone={tone} icon={<l.Icon className="h-3.5 w-3.5" aria-hidden />}>
      {l.label}{score !== null && score !== undefined ? ` · ${score}` : ''}
    </Badge>
  );
};
