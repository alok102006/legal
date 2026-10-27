import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/api/client';

export interface Org {
  id: string;
  legal_name: string;
  trade_name: string | null;
  entity_type: string | null;
  gstin: string | null;
  pan: string | null;
  cin_or_llpin: string | null;
  udyam_number: string | null;
  msme_category: string | null;
  industry: string | null;
  state_code: string | null;
  state_name: string | null;
  employee_band: string | null;
  turnover_band: string | null;
  gst_filing_frequency: string | null;
  registrations: Record<string, boolean>;
  onboarding_completed: boolean;
  missing_fields: string[];
}

export type OrgUpdate = Partial<Omit<Org, 'id' | 'state_name' | 'onboarding_completed' | 'missing_fields'>>;

export interface GstinCheck {
  valid: boolean;
  gstin: string;
  error: string | null;
  state_code: string | null;
  state_name: string | null;
  pan: string | null;
  holder_type: string | null;
  entity_hint: string | null;
  registry_checked: boolean;
  note: string;
}

export const ENTITY_TYPES: { value: string; label: string }[] = [
  { value: 'private_limited', label: 'Private Limited Company' },
  { value: 'public_limited', label: 'Public Limited Company' },
  { value: 'llp', label: 'Limited Liability Partnership (LLP)' },
  { value: 'partnership', label: 'Partnership firm' },
  { value: 'sole_proprietorship', label: 'Sole proprietorship' },
  { value: 'opc', label: 'One Person Company (OPC)' },
  { value: 'trust_society', label: 'Trust / Society' },
  { value: 'other', label: 'Other' },
];
export const EMPLOYEE_BANDS = ['1-9', '10-19', '20-49', '50-199', '200+'];
export const TURNOVER_BANDS: { value: string; label: string }[] = [
  { value: 'lt20l', label: 'Under ₹20 lakh' },
  { value: '20l-1.5cr', label: '₹20 lakh to ₹1.5 crore' },
  { value: '1.5-5cr', label: '₹1.5 crore to ₹5 crore' },
  { value: '5-20cr', label: '₹5 crore to ₹20 crore' },
  { value: '20-50cr', label: '₹20 crore to ₹50 crore' },
  { value: 'gt50cr', label: 'Over ₹50 crore' },
];
export const MSME_OPTIONS: { value: string; label: string }[] = [
  { value: 'micro', label: 'Micro enterprise' },
  { value: 'small', label: 'Small enterprise' },
  { value: 'medium', label: 'Medium enterprise' },
  { value: 'none', label: 'Not registered as MSME' },
  { value: 'unknown', label: "I'm not sure" },
];
export const REGISTRATIONS: { key: string; label: string; hint: string }[] = [
  { key: 'gst', label: 'GST', hint: 'Registered under GST' },
  { key: 'tds', label: 'TDS / TAN', hint: 'Deducts tax at source (salaries, contractors, rent)' },
  { key: 'pf', label: 'Provident Fund (EPF)', hint: 'Usually when you have 20+ employees' },
  { key: 'esi', label: 'ESI', hint: 'Usually when you have 10+ employees below the wage ceiling' },
  { key: 'pt', label: 'Professional Tax', hint: 'Applies in some states, e.g. Maharashtra, Karnataka' },
  { key: 'shops', label: 'Shops & Establishment', hint: 'State licence for shops and offices' },
];

export const entityLabel = (v: string | null | undefined) => ENTITY_TYPES.find((e) => e.value === v)?.label ?? '-';

export function useOrg() {
  return useQuery({
    queryKey: ['org'],
    queryFn: async () => (await apiClient.get<Org>('/api/v1/org')).data,
  });
}

export function useStates() {
  return useQuery({
    queryKey: ['org', 'states'],
    staleTime: Infinity,
    queryFn: async () => (await apiClient.get<{ code: string; name: string }[]>('/api/v1/org/states')).data,
  });
}

export function useUpdateOrg() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: OrgUpdate) => (await apiClient.patch<Org>('/api/v1/org', body)).data,
    onSuccess: (org) => qc.setQueryData(['org'], org),
  });
}

export function useGstinCheck() {
  return useMutation({
    mutationFn: async (gstin: string) => (await apiClient.post<GstinCheck>('/api/v1/org/gstin-check', { gstin })).data,
  });
}
