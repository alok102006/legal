import { useQuery } from '@tanstack/react-query';
import apiClient from '@/api/client';

export interface DepCheck { ok: boolean; latency_ms?: number; message?: string }

export interface LlmCacheStats {
  enabled: boolean; entries: number; size_mb: number; max_entries: number; max_mb: number;
  hits: number; misses: number; hit_rate: number | null; puts: number; evictions: number;
}

export interface Health {
  status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp?: number;
  demo_mode: boolean;
  checks: {
    database: DepCheck;
    vector_store: DepCheck;
    llm: {
      ok: boolean; provider: string; model?: string; kind?: string; message?: string;
      usage?: { calls: number; errors: number; prompt_tokens: number; output_tokens: number };
      quota?: { keys: number; models: string[]; exhausted: { key: number; model: string; resets_in_minutes: number }[] };
    };
    queue?: {
      jobs: { queued: number; running: number; retrying: number; depth: number; workers: number; failed_recent: number; succeeded_recent: number };
      llm: { waiting: number; in_flight: number; keys: Record<string, unknown> } | null;
    };
    cache?: {
      llm: LlmCacheStats | null;
      registry: { hits: number; misses: number; writes: number };
    };
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
