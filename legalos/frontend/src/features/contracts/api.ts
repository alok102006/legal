import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/api/client';
import type { RiskLevel, Severity } from '@/ui/risk';

export type ContractStatus = 'queued' | 'processing' | 'analyzed' | 'failed';

export interface FindingCounts { critical: number; high: number; medium: number; low: number }

export interface ContractListItem {
  id: string;
  title: string | null;
  counterparty_name: string | null;
  contract_type: string | null;
  status: ContractStatus;
  stage: string | null;
  risk_level: RiskLevel | null;
  overall_score: number | null;
  finding_counts: FindingCounts;
  error_kind: string | null;
  error_message: string | null;
  filename: string | null;
  created_at: string;
  analyzed_at: string | null;
}

export interface Finding {
  id: string;
  source: 'ai' | 'rule' | 'missing';
  category: string;
  severity: Severity;
  title: string;
  why_it_matters: string;
  recommendation: string | null;
  suggested_wording: string | null;
  quote: string | null;
  segment_id: string | null;
  page: number | null;
  verified: boolean;
  counts_toward_score: boolean;
  rule_id: string | null;
  legal_note: string | null;
  legal_ref: string | null;
  condition_note: string | null;
  status: 'open' | 'resolved' | 'dismissed';
}

export interface Segment {
  seg_id: string;
  number: string | null;
  heading: string;
  text: string;
  page_start: number | null;
  page_end: number | null;
}

export interface ContractFacts {
  title?: string;
  contract_type_detail?: string | null;
  termination_terms?: string | null;
  termination_notice_days_client?: number | null;
  termination_notice_days_other?: number | null;
  liability_cap_text?: string | null;
  parties?: { name: string; role: string; is_our_client: boolean }[];
  effective_date?: string | null;
  end_date?: string | null;
  term_description?: string | null;
  auto_renewal?: boolean | null;
  renewal_notice_days?: number | null;
  contract_value_amount?: number | null;
  contract_value_currency?: string | null;
  contract_value_basis?: string | null;
  payment_days?: number | null;
  payment_terms_text?: string | null;
  late_payment_interest?: string | null;
  governing_law?: string | null;
  jurisdiction?: string | null;
  dispute_mechanism?: string | null;
  arbitration_seat?: string | null;
  liability_cap_present?: boolean | null;
  key_dates?: string[];
}

export interface ScoreContribution { title: string; category: string; severity: Severity; points: number; source: string; rule_id: string | null }

export interface ReviewInfo { ai_calls?: number; parts?: number; sweep_run?: boolean; sweep_added?: number; client?: string | null; ocr_calls?: number }

export interface ContractDetail extends ContractListItem {
  /** e.g. "Dealership agreement": covers types the UI has no label for */
  contract_type_label?: string | null;
  summary_points: string[];
  facts: ContractFacts | null;
  score_breakdown: {
    by_category: Record<string, number>;
    top_drivers: string[];
    /** every counted finding with its points (absent on contracts read before this was recorded) */
    contributions?: ScoreContribution[];
    /** findings shown but not counted in the score (unverified or missing clauses) */
    excluded_findings?: number;
    review?: ReviewInfo;
    /** how much of a long contract was read by the AI */
    coverage?: { truncated: boolean; reviewed_segments: number | null; total_segments: number | null; reviewed_pages: number | null; total_pages: number | null };
  } | null;
  warnings: string[];
  page_count: number | null;
  has_pages: boolean;
  ocr_used: boolean;
  findings: Finding[];
  segments: Segment[];
}

export interface ChatCitation { quote: string; segment_id: string | null; page: number | null; verified: boolean; finding?: string | null; legal_ref?: string | null }
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations: ChatCitation[];
  found_in_contract: boolean | null;
  created_at: string;
}

export const CONTRACT_TYPE_LABEL: Record<string, string> = {
  supply: 'Supply agreement',
  service: 'Service agreement',
  distribution: 'Distribution agreement',
  franchise: 'Franchise agreement',
  lease: 'Lease agreement',
  employment: 'Employment agreement',
  nda: 'NDA',
  loan_guarantee: 'Loan or guarantee',
  partnership: 'Partnership agreement',
  software_license: 'Software or SaaS agreement',
  other: 'Contract',
};

/** The server's own label when it sent one, else the local map, else the raw type made readable. */
export const contractTypeLabel = (t: string | null | undefined, serverLabel?: string | null) => {
  if (serverLabel) return serverLabel;
  if (!t) return null;
  return CONTRACT_TYPE_LABEL[t] ?? (t === 'other' ? 'Contract' : t.replace(/_/g, ' ').replace(/^./, (m) => m.toUpperCase()));
};

/** "Landlord: Mehta Estates" - the other side of the deal, with their role. */
export function counterpartyLine(facts: ContractFacts | null, fallbackName: string | null): string | null {
  const other = facts?.parties?.find((p) => !p.is_our_client);
  if (other) return `${other.role}: ${other.name}`;
  return fallbackName ? `With ${fallbackName}` : null;
}

const KEY = ['contracts'] as const;
const isRunning = (s?: string) => s === 'processing' || s === 'queued';

export function useContracts() {
  return useQuery({
    queryKey: KEY,
    queryFn: async () => (await apiClient.get<ContractListItem[]>('/api/v1/contracts')).data,
    // keep refreshing the list while anything is still being analysed
    refetchInterval: (q) => (q.state.data?.some((c) => isRunning(c.status)) ? 2500 : false),
  });
}

export function useContract(id: string | undefined) {
  return useQuery({
    queryKey: [...KEY, id],
    enabled: !!id,
    queryFn: async () => (await apiClient.get<ContractDetail>(`/api/v1/contracts/${id}`)).data,
    refetchInterval: (q) => (isRunning(q.state.data?.status) ? 1500 : false),
  });
}

export function useUploadContract() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ files, clientParty }: { files: File[]; clientParty?: string }) => {
      const fd = new FormData();
      // one document goes as `file`; several page photos go as `files`, in page order
      if (files.length === 1) fd.append('file', files[0]);
      else files.forEach((f) => fd.append('files', f));
      if (clientParty?.trim()) fd.append('client_party', clientParty.trim());
      const r = await apiClient.post<ContractListItem>('/api/v1/contracts/upload', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return r.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useRetryContract() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => (await apiClient.post<ContractListItem>(`/api/v1/contracts/${id}/retry`)).data,
    onSuccess: (_d, id) => {
      qc.invalidateQueries({ queryKey: [...KEY, id] });
      qc.invalidateQueries({ queryKey: KEY });
    },
  });
}

export function useDeleteContract() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => (await apiClient.delete(`/api/v1/contracts/${id}`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useSetFindingStatus(contractId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ findingId, status }: { findingId: string; status: Finding['status'] }) =>
      (await apiClient.patch<Finding>(`/api/v1/contracts/${contractId}/findings/${findingId}`, { status })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...KEY, contractId] });
      qc.invalidateQueries({ queryKey: KEY });
    },
  });
}

export function useChat(contractId: string) {
  const qc = useQueryClient();
  const messages = useQuery({
    queryKey: [...KEY, contractId, 'messages'],
    queryFn: async () => (await apiClient.get<ChatMessage[]>(`/api/v1/contracts/${contractId}/messages`)).data,
  });
  const ask = useMutation({
    mutationFn: async (question: string) =>
      (await apiClient.post<ChatMessage>(`/api/v1/contracts/${contractId}/chat`, { question })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: [...KEY, contractId, 'messages'] }),
  });
  return { messages, ask };
}

export async function downloadContractFile(id: string, filename: string) {
  const r = await apiClient.get(`/api/v1/contracts/${id}/file`, { responseType: 'blob' });
  const url = URL.createObjectURL(r.data as Blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
