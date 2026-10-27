import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/api/client';

export type TaskState = 'overdue' | 'due_soon' | 'upcoming' | 'done';

export interface PenaltyEstimate {
  amount: number;
  days_late: number;
  per_day: number | null;
  cap: number | null;
  capped: boolean;
  flat: boolean;
  note: string | null;
}

export interface TaskOrigin {
  kind: 'contract' | 'notice' | 'document';
  label: string;
  href: string;
}

export interface ComplianceTask {
  id: string;
  title: string;
  category: string;
  due_date: string | null;
  status: 'pending' | 'completed';
  state: TaskState;
  days_left: number | null;
  description: string | null;
  penalty_desc: string | null;
  rule_id: string | null;
  period_label: string | null;
  form_name: string | null;
  authority: string | null;
  source_ref: string | null;
  needs_confirmation: boolean;
  confirm_note: string | null;
  is_custom: boolean;
  completed_at: string | null;
  completion_note: string | null;
  verified: boolean;
  penalty_estimate: PenaltyEstimate | null;
  origin: TaskOrigin | null;
  file_where: string | null;
  file_url: string | null;
}

export interface ComplianceSummary {
  needs_profile: boolean;
  overdue: number;
  due_in_7_days: number;
  due_in_30_days: number;
  completed_last_30_days: number;
  needs_confirmation: number;
  next_deadlines: { id: string; title: string; period_label: string | null; due_date: string; days_left: number; needs_confirmation: boolean }[];
  rules_version: string;
  today: string;
  rules_total: number;
  rules_applicable: number;
  sources_total: number;
  last_synced: string | null;
}

export interface RulesOverview {
  rules_version: string;
  applicable: { id: string; title: string; category: string; authority: string; form: string; description: string; penalty: string; source: string; reason: string; needs_confirmation: boolean; confirm_note: string | null; verify: boolean; verified: boolean }[];
  not_applicable: { id: string; title: string; reason: string }[];
  not_covered: { title: string; reason: string }[];
}

export interface FactRule { id: string; title: string; form: string; applies: boolean; reason: string; verified: boolean }
export interface ProfileFact {
  key: string;
  label: string;
  kind: 'field' | 'registration' | 'always';
  value: string | null;
  hint: string | null;
  rules: FactRule[];
}
export interface ProfileFacts { facts: ProfileFact[]; rules_applicable: number; rules_total: number }

export const KEY = ['compliance'] as const;
const TASKS_KEY = [...KEY, 'tasks'] as const;

export const useComplianceTasks = () =>
  useQuery({ queryKey: TASKS_KEY, queryFn: async () => (await apiClient.get<ComplianceTask[]>('/api/v1/compliance/tasks')).data });

export const useComplianceSummary = () =>
  useQuery({ queryKey: [...KEY, 'summary'], queryFn: async () => (await apiClient.get<ComplianceSummary>('/api/v1/compliance/summary')).data });

export const useRulesOverview = (enabled: boolean) =>
  useQuery({ queryKey: [...KEY, 'rules'], enabled, queryFn: async () => (await apiClient.get<RulesOverview>('/api/v1/compliance/rules')).data });

export const useProfileFacts = (enabled = true) =>
  useQuery({ queryKey: [...KEY, 'facts'], enabled, queryFn: async () => (await apiClient.get<ProfileFacts>('/api/v1/compliance/profile-facts')).data });

export function useInvalidateCompliance() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: KEY });
}

/** Client-side mirror of the server's state rule, used only for the optimistic update. */
function stateFor(t: ComplianceTask, status: 'pending' | 'completed'): TaskState {
  if (status === 'completed') return 'done';
  if (t.days_left === null) return 'upcoming';
  if (t.days_left < 0) return 'overdue';
  return t.days_left <= 7 ? 'due_soon' : 'upcoming';
}

/** Done toggle: the row flips instantly, rolls back if the server says no. */
export function useToggleDone() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, status, note }: { id: string; status: 'pending' | 'completed'; note?: string }) =>
      (await apiClient.patch<ComplianceTask>(`/api/v1/compliance/tasks/${id}`, { status, note })).data,
    onMutate: async ({ id, status }) => {
      await qc.cancelQueries({ queryKey: TASKS_KEY });
      const prev = qc.getQueryData<ComplianceTask[]>(TASKS_KEY);
      qc.setQueryData<ComplianceTask[]>(TASKS_KEY, (old) =>
        (old ?? []).map((t) => (t.id === id ? { ...t, status, state: stateFor(t, status), penalty_estimate: status === 'completed' ? null : t.penalty_estimate } : t)));
      return { prev };
    },
    onError: (_e, _v, ctx) => { if (ctx?.prev) qc.setQueryData(TASKS_KEY, ctx.prev); },
    onSettled: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useCreateTask() {
  const invalidate = useInvalidateCompliance();
  return useMutation({
    mutationFn: async (body: { title: string; due_date: string; category: string; description?: string }) =>
      (await apiClient.post<ComplianceTask>('/api/v1/compliance/tasks', body)).data,
    onSuccess: invalidate,
  });
}

export function useBulkComplete() {
  const invalidate = useInvalidateCompliance();
  return useMutation({
    mutationFn: async (ids: string[]) =>
      (await apiClient.post<{ completed: number }>('/api/v1/compliance/tasks/bulk-complete', { ids, note: 'Marked as already filed' })).data,
    onSuccess: invalidate,
  });
}

export function useDeleteTask() {
  const invalidate = useInvalidateCompliance();
  return useMutation({
    mutationFn: async (id: string) => (await apiClient.delete(`/api/v1/compliance/tasks/${id}`)).data,
    onSuccess: invalidate,
  });
}

export function useSyncCalendar() {
  const invalidate = useInvalidateCompliance();
  return useMutation({
    mutationFn: async () => (await apiClient.post<{ created: number; updated: number; removed: number; kept: number }>('/api/v1/compliance/sync')).data,
    onSuccess: invalidate,
  });
}
