import { useQuery } from '@tanstack/react-query';
import apiClient from '@/api/client';

export interface Health {
  status: 'healthy' | 'degraded' | 'unhealthy';
  demo_mode: boolean;
  checks: {
    database: { ok: boolean; message?: string };
    vector_store: { ok: boolean; message?: string };
    llm: { ok: boolean; provider: string; model?: string; kind?: string; message?: string };
    registry: { mode: string; live: boolean };
  };
}

/** Real status of the backend and its dependencies. The UI shows this instead of hard-coded badges. */
export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: async () => (await apiClient.get<Health>('/health')).data,
    refetchInterval: 60_000,
    retry: false,
    staleTime: 30_000,
  });
}
