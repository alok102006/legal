import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/api/client';

export type SampleKind = 'contract' | 'notice' | 'document';

/** Loads a realistic sample into the user's own account and runs the real pipeline. */
export function useLoadSample() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (kind: SampleKind) => (await apiClient.post<{ kind: SampleKind; id: string; path: string }>(`/api/v1/samples/${kind}`)).data,
    onSuccess: () => qc.invalidateQueries(),
  });
}

export interface ActivityItem { id: string; action: string; text: string; link: string | null; created_at: string }

export const useActivity = () =>
  useQuery({ queryKey: ['activity'], queryFn: async () => (await apiClient.get<ActivityItem[]>('/api/v1/org/activity', { params: { limit: 12 } })).data, refetchInterval: 30_000 });
