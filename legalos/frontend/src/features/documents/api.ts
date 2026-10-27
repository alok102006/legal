import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import apiClient, { DEMO_FLAG_KEY, DEMO_ROLE_KEY, TOKEN_KEY } from '@/api/client';

export interface DocListItem {
  id: string;
  title: string;
  filename: string | null;
  category: string | null;
  doc_type: string | null;
  language: string | null;
  file_type: string | null;
  page_count: number | null;
  status: 'processing' | 'ready' | 'failed';
  stage: string | null;
  review_state: 'pending' | 'done' | 'failed';
  expiry_date: string | null;
  expiry_label: string | null;
  concern_count: number;
  error_kind: string | null;
  error_message: string | null;
  created_at: string;
}

export interface DocDetail extends DocListItem {
  summary_points: string[];
  key_facts: { label: string; value: string }[];
  concerns: { title: string; why_it_matters: string; quote: string; page: number | null; verified: boolean; exact: boolean }[];
  missing_items: string[];
  suggested_questions: string[];
  review_error: string | null;
  chunk_count: number;
  in_calendar: boolean;
  ocr_used: boolean;
  chunks: { chunk_index: number; page: number | null; section: string | null; text: string }[];
}

export interface Collection { name: string; count: number; ready: number }

export interface Citation {
  marker: string | null; quote: string; document_id: string | null; document_title: string | null;
  page: number | null; section: string | null; verified: boolean; exact: boolean;
}
export interface Source { marker: string; document_id: string; document_title: string; page: number | null; section: string | null; text: string; via: string[] }

export interface Turn {
  id: string; role: 'user' | 'assistant'; content: string; citations: Citation[]; sources: Source[];
  found_in_documents: boolean | null; confidence: number | null; created_at: string;
}
export interface Conversation { id: string; title: string; collection: string | null; created_at: string; updated_at: string }
export interface ConversationDetail extends Conversation { turns: Turn[] }

export interface SearchHit { document_id: string; document_title: string; page: number | null; section: string | null; snippet: string; via: string[] }

export const DOC_CATEGORIES = ['Policy', 'Contract', 'Licence or certificate', 'HR', 'Finance or tax', 'Board or company records', 'Other'];
export const ALL_DOCUMENTS = null;   // conversation scope meaning "every collection"

const KEY = ['documents'] as const;
const CONV = ['conversations'] as const;
const busy = (s?: string, r?: string) => s === 'processing' || (s === 'ready' && r === 'pending');

/* ------------------------------------------------------------------ documents and collections */

export const useDocuments = (collection?: string | null) =>
  useQuery({
    queryKey: [...KEY, collection ?? 'all'],
    queryFn: async () => (await apiClient.get<DocListItem[]>('/api/v1/knowledge/documents', { params: collection ? { collection } : undefined })).data,
    refetchInterval: (q) => (q.state.data?.some((d) => busy(d.status, d.review_state)) ? 2500 : false),
  });

export const useDocument = (id: string | undefined) =>
  useQuery({
    queryKey: [...KEY, 'detail', id], enabled: !!id,
    queryFn: async () => (await apiClient.get<DocDetail>(`/api/v1/knowledge/documents/${id}`)).data,
    refetchInterval: (q) => (busy(q.state.data?.status, q.state.data?.review_state) ? 1500 : false),
  });

export const useCollections = () =>
  useQuery({ queryKey: [...KEY, 'collections'], queryFn: async () => (await apiClient.get<Collection[]>('/api/v1/knowledge/collections')).data });

export const useSuggestions = (collection: string | null, enabled = true) =>
  useQuery({
    queryKey: [...KEY, 'suggestions', collection ?? 'all'], enabled,
    queryFn: async () => (await apiClient.get<{ questions: string[] }>('/api/v1/knowledge/suggestions', { params: collection ? { collection } : undefined })).data.questions,
  });

function useInvalidateDocs() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: KEY });
}

export function useUploadDocument() {
  const inv = useInvalidateDocs();
  return useMutation({
    mutationFn: async ({ file, category }: { file: File; category?: string }) => {
      const fd = new FormData();
      fd.append('file', file);
      if (category) fd.append('category', category);
      return (await apiClient.post<DocListItem>('/api/v1/knowledge/documents/upload', fd, { headers: { 'Content-Type': 'multipart/form-data' } })).data;
    },
    onSuccess: inv,
  });
}

export function useRetryDocument(id: string) {
  const inv = useInvalidateDocs();
  return useMutation({ mutationFn: async () => (await apiClient.post<DocListItem>(`/api/v1/knowledge/documents/${id}/retry`)).data, onSuccess: inv });
}

export function useUpdateDocument() {
  const inv = useInvalidateDocs();
  return useMutation({
    mutationFn: async ({ id, ...body }: { id: string; title?: string; category?: string }) => (await apiClient.patch<DocListItem>(`/api/v1/knowledge/documents/${id}`, body)).data,
    onSuccess: inv,
  });
}

export function useDeleteDocument() {
  const inv = useInvalidateDocs();
  return useMutation({ mutationFn: async (id: string) => (await apiClient.delete(`/api/v1/knowledge/documents/${id}`)).data, onSuccess: () => { inv(); } });
}

export function useSearchDocuments() {
  return useMutation({
    mutationFn: async (b: { q: string; collection?: string | null }) => (await apiClient.get<SearchHit[]>('/api/v1/knowledge/search', { params: { q: b.q, collection: b.collection ?? undefined } })).data,
  });
}

export async function downloadDocument(id: string, filename: string) {
  const r = await apiClient.get(`/api/v1/knowledge/documents/${id}/file`, { responseType: 'blob' });
  const url = URL.createObjectURL(r.data as Blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

/* ------------------------------------------------------------------ conversations */

export const useConversations = () =>
  useQuery({ queryKey: CONV, queryFn: async () => (await apiClient.get<Conversation[]>('/api/v1/knowledge/conversations')).data });

export const useConversation = (id: string | undefined) =>
  useQuery({ queryKey: [...CONV, id], enabled: !!id, queryFn: async () => (await apiClient.get<ConversationDetail>(`/api/v1/knowledge/conversations/${id}`)).data });

export function useCreateConversation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (b: { collection: string | null }) => (await apiClient.post<Conversation>('/api/v1/knowledge/conversations', b)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: CONV }),
  });
}

export function useUpdateConversation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...body }: { id: string; title?: string }) => (await apiClient.patch<Conversation>(`/api/v1/knowledge/conversations/${id}`, body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: CONV }),
  });
}

export function useDeleteConversation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => (await apiClient.delete(`/api/v1/knowledge/conversations/${id}`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: CONV }),
  });
}

/* ------------------------------------------------------------------ streaming answers (server-sent events) */

export type StreamEvent =
  | { kind: 'stage'; stage: 'searching' | 'writing' }
  | { kind: 'delta'; text: string }
  | { kind: 'done'; turn: Turn }
  | { kind: 'error'; errorKind: string; message: string };

function authHeaders(): Record<string, string> {
  try {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) return { Authorization: `Bearer ${token}` };
    if (localStorage.getItem(DEMO_FLAG_KEY) === '1') return { 'X-User-Role': localStorage.getItem(DEMO_ROLE_KEY) || 'owner' };
  } catch { /* storage blocked */ }
  return {};
}

/** Asks a question and reports progress as the server sends it. Resolves when the stream ends; rejects on transport failure. */
export async function streamAsk(conversationId: string, question: string, onEvent: (e: StreamEvent) => void, signal?: AbortSignal): Promise<void> {
  const base = (apiClient.defaults.baseURL ?? '').replace(/\/$/, '');
  const res = await fetch(`${base}/api/v1/knowledge/conversations/${conversationId}/ask/stream`, {
    method: 'POST', signal,
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream', ...authHeaders() },
    body: JSON.stringify({ question }),
  });
  if (res.status === 401) window.dispatchEvent(new CustomEvent('legalos:unauthorized'));
  if (!res.ok || !res.body) {
    let message = res.status >= 500 ? 'Something went wrong on our side. Please try again.' : 'Could not send your question.';
    try { const data = await res.json(); if (typeof data?.detail === 'string') message = data.detail; } catch { /* not json */ }
    throw new Error(message);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  const dispatch = (block: string) => {
    let event = 'message'; let data = '';
    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim();
      else if (line.startsWith('data:')) data += line.slice(5).trim();
    }
    if (!data) return;
    const payload = JSON.parse(data);
    if (event === 'stage') onEvent({ kind: 'stage', stage: payload.stage });
    else if (event === 'delta') onEvent({ kind: 'delta', text: payload.text });
    else if (event === 'done') onEvent({ kind: 'done', turn: payload as Turn });
    else if (event === 'error') onEvent({ kind: 'error', errorKind: payload.kind, message: payload.message });
  };
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buffer.indexOf('\n\n')) >= 0) {
      dispatch(buffer.slice(0, idx));
      buffer = buffer.slice(idx + 2);
    }
  }
  if (buffer.trim()) dispatch(buffer);
}
