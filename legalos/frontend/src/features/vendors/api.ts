import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/api/client';

export type VendorRisk = 'high' | 'medium' | 'low' | 'unverified';
export type CheckStatus = 'pass' | 'warn' | 'fail' | 'unknown';
export type RegistrySource = 'live' | 'sample' | 'unavailable';
export type RegistryMode = 'live' | 'sample' | 'offline';
export type IdKind = 'gstin' | 'pan' | 'udyam' | 'cin' | 'llpin' | 'tan' | 'ifsc' | 'iec' | 'fssai' | 'esic' | 'pf';

export interface VendorCheckItem { key: string; label: string; status: CheckStatus; detail: string }

/** What the registry told us (or why it did not). Every field is optional: we only show what exists. */
export interface RegistryInfo {
  source?: RegistrySource;
  provider?: string;
  message?: string;
  error_kind?: 'not_connected' | 'no_gstin' | 'invalid_gstin' | 'auth' | 'quota' | 'unavailable' | 'not_found';
  legal_name?: string;
  trade_name?: string;
  status?: string;
  registration_date?: string;
  cancellation_date?: string;
  constitution?: string;
  taxpayer_type?: string;
  state?: string;
  filing_status?: string;
  note?: string;
  msme_category?: string;
  /** true when this answer came from the 24 h lookup cache (no new registry call was made) */
  cached?: boolean;
  /** when the registry was actually asked (ISO) */
  fetched_at?: string;
}

export interface LinkedContract { id: string; title: string | null; status: string; risk_level: string | null; overall_score: number | null }
export interface LinkedNotice { id: string; title: string | null; status: string; urgency: string | null; response_deadline: string | null }
export interface HistoryEntry { at: string; risk_level: VendorRisk; registry_source: RegistrySource | null; registry_status: string | null; summary: string | null }

export interface VendorBrief {
  id: string;
  name: string;
  gstin: string | null;
  pan: string | null;
  udyam_number: string | null;
  state_name: string | null;
  msme_category: string | null;
  risk_level: VendorRisk;
  summary: string | null;
  registry_source: RegistrySource | null;
  last_checked_at: string | null;
  created_at: string;
}

export interface VendorDetail extends VendorBrief {
  kind: IdKind;
  state_code: string | null;
  notes: string | null;
  reasons: string[];
  checks: VendorCheckItem[];
  registry: RegistryInfo | null;
  registry_mode: RegistryMode;
  registry_provider: string | null;
  history: HistoryEntry[];
  contracts: LinkedContract[];
  notices: LinkedNotice[];
}

/** Result of the check desk (not saved). */
export interface CheckResult {
  kind: IdKind;
  identifier: string;
  suggested_name: string | null;
  risk_level: VendorRisk;
  summary: string;
  reasons: string[];
  checks: VendorCheckItem[];
  registry: RegistryInfo | null;
  registry_source: RegistrySource | null;
  registry_mode: RegistryMode;
  registry_provider: string | null;
  state_name: string | null;
  pan: string | null;
  holder_type: string | null;
  /** decoded parts of a CIN / IFSC / PF ... number */
  details?: Record<string, unknown>;
  saved_vendor: VendorBrief | null;
  contracts: LinkedContract[];
  notices: LinkedNotice[];
  checked_at: string;
}

export interface VendorInput {
  name: string;
  gstin?: string;
  pan?: string;
  state_code?: string;
  udyam_number?: string;
  msme_category?: string;
  notes?: string;
}

const KEY = ['vendors'] as const;

export const useVendors = () =>
  useQuery({ queryKey: KEY, queryFn: async () => (await apiClient.get<VendorBrief[]>('/api/v1/vendors')).data });

export const useVendor = (id: string | undefined) =>
  useQuery({ queryKey: [...KEY, id], enabled: !!id, queryFn: async () => (await apiClient.get<VendorDetail>(`/api/v1/vendors/${id}`)).data });

export const useVendorSamples = () =>
  useQuery({
    queryKey: [...KEY, 'samples'], staleTime: Infinity,
    queryFn: async () => (await apiClient.get<{ gstin: string; name: string; label: string }[]>('/api/v1/vendors/samples')).data,
  });

export const useVendorMatch = (name: string | null | undefined) =>
  useQuery({
    queryKey: [...KEY, 'match', name], enabled: !!name && name.length >= 2,
    queryFn: async () => (await apiClient.get<VendorBrief | null>('/api/v1/vendors/match', { params: { name } })).data,
  });

/** The check desk: GSTIN, PAN or Udyam number. Runs offline checks + the live registry when connected. Does not save. */
export const useCheckIdentifier = () =>
  useMutation({
    mutationFn: async (b: { identifier: string; name?: string; kind?: IdKind }) => (await apiClient.post<CheckResult>('/api/v1/vendors/check', b)).data,
  });

export interface RiskRules {
  levels: { level: string; label: string; when: string[] }[];
  checks: { key: string; label: string; fails_when: string; warns_when: string }[];
  notes: string[];
}

/** The plain-English rules behind every verdict. Fetched only when `enabled` (when the disclosure is opened). */
export const useRiskRules = (enabled: boolean) =>
  useQuery({
    queryKey: [...KEY, 'risk-rules'], enabled, staleTime: Infinity,
    queryFn: async () => (await apiClient.get<RiskRules>('/api/v1/vendors/risk-rules')).data,
  });

export interface RecheckAll {
  total: number;
  rechecked: number;
  live_lookups: number;
  from_cache: number;
  failed: number;
  deferred: number;
  deferred_names: string[];
  changed: { id: string; name: string; previous: string; current: string }[];
  registry_mode: string;
  max_live_per_run: number;
}

function useInvalidate() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: KEY });
}

export function useCreateVendor() {
  const inv = useInvalidate();
  return useMutation({ mutationFn: async (b: VendorInput) => (await apiClient.post<VendorDetail>('/api/v1/vendors', b)).data, onSuccess: inv });
}
export function useUpdateVendor(id: string) {
  const inv = useInvalidate();
  return useMutation({ mutationFn: async (b: Partial<VendorInput>) => (await apiClient.patch<VendorDetail>(`/api/v1/vendors/${id}`, b)).data, onSuccess: inv });
}
export function useRecheckVendor(id: string) {
  const inv = useInvalidate();
  return useMutation({ mutationFn: async () => (await apiClient.post<VendorDetail>(`/api/v1/vendors/${id}/recheck`)).data, onSuccess: inv });
}
export function useRecheckAll() {
  const inv = useInvalidate();
  return useMutation({ mutationFn: async () => (await apiClient.post<RecheckAll>('/api/v1/vendors/recheck-all')).data, onSuccess: inv });
}
export function useDeleteVendor() {
  const inv = useInvalidate();
  return useMutation({ mutationFn: async (id: string) => (await apiClient.delete(`/api/v1/vendors/${id}`)).data, onSuccess: inv });
}
