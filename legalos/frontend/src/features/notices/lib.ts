import { formatDate, plural } from '@/lib/utils';
import type { NoticeListItem } from './api';

export type Tone = 'critical' | 'serious' | 'warn' | 'info' | 'good' | 'neutral';

export interface Countdown {
  /** short pill text, e.g. "6 days left", "Overdue 2 days", "Replied" */
  pill: string;
  /** big number for the deadline strip ("6") and its caption ("days left") */
  big: string | null;
  caption: string;
  tone: Tone;
  /** sort key: overdue first, then fewest days left; unknown after dated; replied last */
  rank: number;
}

type CountdownInput = Pick<NoticeListItem, 'status' | 'days_left' | 'response_deadline'>;

export function countdown(n: CountdownInput): Countdown {
  if (n.status === 'closed') return { pill: 'Replied', big: null, caption: 'Replied', tone: 'good', rank: 1e9 };
  if (n.status === 'processing') return { pill: 'Reading', big: null, caption: 'Reading the notice', tone: 'info', rank: -2e9 };
  if (n.status === 'failed') return { pill: 'Needs retry', big: null, caption: 'Needs retry', tone: 'critical', rank: -1e9 };
  if (!n.response_deadline || n.days_left === null) return { pill: 'No deadline found', big: null, caption: 'No deadline found', tone: 'warn', rank: 1e6 };
  const d = n.days_left;
  if (d < 0) return { pill: `Overdue ${plural(-d, 'day')}`, big: String(-d), caption: `${d === -1 ? 'day' : 'days'} overdue`, tone: 'critical', rank: d };
  if (d === 0) return { pill: 'Due today', big: '0', caption: 'due today', tone: 'critical', rank: 0 };
  const tone: Tone = d <= 3 ? 'critical' : d <= 7 ? 'serious' : d <= 14 ? 'warn' : 'info';
  return { pill: `${plural(d, 'day')} left`, big: String(d), caption: d === 1 ? 'day left' : 'days left', tone, rank: d };
}

export const sortNotices = (list: NoticeListItem[]): NoticeListItem[] =>
  [...list].sort((a, b) => countdown(a).rank - countdown(b).rank || b.created_at.localeCompare(a.created_at));

export const TONE_PILL: Record<Tone, string> = {
  critical: 'bg-critical-soft text-critical-ink',
  serious: 'bg-serious-soft text-serious-ink',
  warn: 'bg-warn-soft text-warn-ink',
  info: 'bg-primary-soft text-primary-ink',
  good: 'bg-good-soft text-good-ink',
  neutral: 'bg-surface-2 text-ink-2',
};

export const TONE_INK: Record<Tone, string> = {
  critical: 'text-critical-ink', serious: 'text-serious-ink', warn: 'text-warn-ink', info: 'text-primary-ink', good: 'text-good-ink', neutral: 'text-ink-2',
};

export const TONE_FILL: Record<Tone, string> = {
  critical: 'var(--critical)', serious: 'var(--serious)', warn: 'var(--warn)', info: 'var(--primary)', good: 'var(--good)', neutral: 'var(--border-strong)',
};

export const todayIso = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

/** Whole days between two ISO dates (b - a), ignoring time zones. */
export const dayDiff = (a: string, b: string) => Math.round((Date.parse(`${b}T00:00:00Z`) - Date.parse(`${a}T00:00:00Z`)) / 86_400_000);

export const longDate = (iso: string | null) => formatDate(iso);
