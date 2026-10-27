import { useMemo } from 'react';
import { useContracts } from '@/features/contracts/api';
import { useComplianceSummary } from '@/features/compliance/api';
import { useNotices } from '@/features/notices/api';
import { useDocuments } from '@/features/documents/api';
import { formatDate, plural } from '@/lib/utils';

export interface AttentionItem {
  id: string;
  kind: 'notice' | 'contract' | 'compliance' | 'document';
  level: 'critical' | 'high' | 'medium';
  title: string;
  detail: string;
  link: string;
}

const LEVEL_RANK = { critical: 0, high: 1, medium: 2 } as const;

/** One cross-workspace list of what needs the owner's attention, computed from real data only. */
export function useAttention() {
  const contracts = useContracts();
  const notices = useNotices();
  const compliance = useComplianceSummary();
  const documents = useDocuments();

  const items = useMemo<AttentionItem[]>(() => {
    const out: AttentionItem[] = [];
    for (const n of notices.data ?? []) {
      if (n.status !== 'analyzed') { if (n.status === 'failed') out.push({ id: n.id, kind: 'notice', level: 'medium', title: n.title ?? 'Notice', detail: 'Analysis did not finish. Retry it.', link: `/notices/${n.id}` }); continue; }
      if (n.urgency === 'critical' || n.urgency === 'high') {
        const d = n.days_left;
        const detail = n.response_deadline ? (d !== null && d < 0 ? `Reply was due ${formatDate(n.response_deadline)}` : d === 0 ? 'Reply today' : `Reply by ${formatDate(n.response_deadline)} (${plural(d ?? 0, 'day')} left)`) : 'No deadline found, check the notice';
        out.push({ id: n.id, kind: 'notice', level: n.urgency, title: n.title ?? 'Notice', detail, link: `/notices/${n.id}` });
      }
    }
    const c = compliance.data;
    if (c && !c.needs_profile) {
      if (c.overdue > 0) out.push({ id: 'overdue', kind: 'compliance', level: 'critical', title: `${plural(c.overdue, 'overdue filing')}`, detail: 'Past the due date. File or mark as already filed.', link: '/compliance' });
      for (const d of c.next_deadlines.filter((x) => x.days_left <= 7).slice(0, 3)) {
        out.push({ id: d.id, kind: 'compliance', level: 'high', title: d.title, detail: `${d.period_label ? d.period_label + ' · ' : ''}due ${formatDate(d.due_date)}${d.days_left === 0 ? ' (today)' : ` (${plural(d.days_left, 'day')})`}`, link: '/compliance' });
      }
    }
    for (const ct of contracts.data ?? []) {
      if (ct.status === 'failed') out.push({ id: ct.id, kind: 'contract', level: 'medium', title: ct.title || ct.filename || 'Contract', detail: 'Review did not finish. Retry it.', link: `/contracts/${ct.id}` });
      else if (ct.status === 'analyzed' && ct.risk_level === 'high') out.push({ id: ct.id, kind: 'contract', level: 'high', title: ct.title || 'Contract', detail: `High risk (${ct.overall_score}). ${ct.finding_counts.critical ? plural(ct.finding_counts.critical, 'critical finding') : plural(ct.finding_counts.high, 'high finding')}.`, link: `/contracts/${ct.id}` });
    }
    for (const d of documents.data ?? []) {
      if (d.status === 'failed') out.push({ id: d.id, kind: 'document', level: 'medium', title: d.title, detail: 'Processing did not finish. Retry it.', link: `/documents/${d.id}` });
    }
    return out.sort((a, b) => LEVEL_RANK[a.level] - LEVEL_RANK[b.level]);
  }, [contracts.data, notices.data, compliance.data, documents.data]);

  return { items, isLoading: contracts.isLoading || notices.isLoading || compliance.isLoading || documents.isLoading };
}
