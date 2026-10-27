import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/api/client';

export type Urgency = 'critical' | 'high' | 'medium' | 'low';

export interface NoticeListItem {
  id: string;
  title: string | null;
  notice_type: string | null;
  type_label: string | null;
  urgency: Urgency | null;
  status: 'processing' | 'analyzed' | 'failed' | 'closed';
  stage: string | null;
  issuer_name: string | null;
  amount_claimed: number | null;
  response_deadline: string | null;
  days_left: number | null;
  review_status: 'draft' | 'ready_for_lawyer' | 'lawyer_approved';
  error_kind: string | null;
  error_message: string | null;
  source_name: string | null;
  created_at: string;
}

export interface ReplyDraft {
  id: string;
  version: number;
  reply_text: string;
  placeholders: string[];
  points_to_confirm: string[];
  documents_to_gather: string[];
  author: 'ai' | 'user';
  instructions: string | null;
  created_at: string;
}

export interface KeyQuote { kind: 'deadline' | 'amount' | 'demand'; text: string; verified: boolean }

export interface NoticeDetail extends NoticeListItem {
  reference_number: string | null;
  notice_date: string | null;
  received_date: string | null;
  response_days: number | null;
  deadline_source: 'stated' | 'statutory_default' | 'unknown' | null;
  deadline_note: string | null;
  deadline_quote: string | null;
  deadline_verified: boolean;
  deadline_rule: string | null;
  received_confirmed: boolean;
  needs_received_date: boolean;
  issuer_role: string | null;
  addressed_to: string | null;
  summary_points: string[];
  demands: string[];
  statutes: string[];
  consequences: string | null;
  legal_note: string | null;
  legal_ref: string | null;
  legal_if_ignored: string | null;
  if_ignored: string | null;
  actions: string[];
  actions_done: number[];
  key_quotes: KeyQuote[];
  ocr_used: boolean;
  in_calendar: boolean;
  raw_text: string | null;
  drafts: ReplyDraft[];
}

const KEY = ['notices'] as const;
const running = (s?: string) => s === 'processing';

export const useNotices = () =>
  useQuery({
    queryKey: KEY,
    queryFn: async () => (await apiClient.get<NoticeListItem[]>('/api/v1/notices')).data,
    refetchInterval: (q) => (q.state.data?.some((n) => running(n.status)) ? 2500 : false),
  });

export const useNotice = (id: string | undefined) =>
  useQuery({
    queryKey: [...KEY, id], enabled: !!id,
    queryFn: async () => (await apiClient.get<NoticeDetail>(`/api/v1/notices/${id}`)).data,
    refetchInterval: (q) => (running(q.state.data?.status) ? 1500 : false),
  });

function useInvalidate() {
  const qc = useQueryClient();
  return (id?: string) => { qc.invalidateQueries({ queryKey: KEY }); if (id) qc.invalidateQueries({ queryKey: ['compliance'] }); };
}

export function useUploadNotice() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: async ({ file, receivedDate }: { file: File; receivedDate?: string }) => {
      const fd = new FormData();
      fd.append('file', file);
      if (receivedDate) fd.append('received_date', receivedDate);
      return (await apiClient.post<NoticeListItem>('/api/v1/notices/upload', fd, { headers: { 'Content-Type': 'multipart/form-data' } })).data;
    },
    onSuccess: () => inv(),
  });
}

export function usePasteNotice() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: async (b: { text: string; title?: string; received_date?: string }) => (await apiClient.post<NoticeListItem>('/api/v1/notices/text', b)).data,
    onSuccess: () => inv(),
  });
}

export function useRetryNotice(id: string) {
  const inv = useInvalidate();
  return useMutation({ mutationFn: async () => (await apiClient.post<NoticeListItem>(`/api/v1/notices/${id}/retry`)).data, onSuccess: () => inv(id) });
}

export function useUpdateNotice(id: string) {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: async (b: { received_date?: string; review_status?: string; status?: string; actions_done?: number[] }) => (await apiClient.patch<NoticeDetail>(`/api/v1/notices/${id}`, b)).data,
    onSuccess: () => inv(id),
  });
}

export function useRegenerateDraft(id: string) {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: async (instructions?: string) => (await apiClient.post<NoticeDetail>(`/api/v1/notices/${id}/draft`, { instructions })).data,
    onSuccess: () => inv(id),
  });
}

export function useSaveDraft(id: string) {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: async (reply_text: string) => (await apiClient.put<NoticeDetail>(`/api/v1/notices/${id}/draft`, { reply_text })).data,
    onSuccess: () => inv(id),
  });
}

export function useDeleteNotice() {
  const inv = useInvalidate();
  return useMutation({ mutationFn: async (id: string) => (await apiClient.delete(`/api/v1/notices/${id}`)).data, onSuccess: (_d, id) => inv(id) });
}

/** Ticking an action saves straight away; the checklist updates before the server answers. */
export function useSaveActions(id: string) {
  const qc = useQueryClient();
  const key = [...KEY, id];
  return useMutation({
    mutationFn: async (done: number[]) => (await apiClient.patch<NoticeDetail>(`/api/v1/notices/${id}`, { actions_done: done })).data,
    onMutate: async (done) => {
      await qc.cancelQueries({ queryKey: key });
      const prev = qc.getQueryData<NoticeDetail>(key);
      if (prev) qc.setQueryData<NoticeDetail>(key, { ...prev, actions_done: done });
      return { prev };
    },
    onError: (_e, _v, ctx) => { if (ctx?.prev) qc.setQueryData(key, ctx.prev); },
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  });
}
