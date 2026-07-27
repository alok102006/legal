export interface ContractSummary {
  id: string;
  document_id: string;
  title: string | null;
  counterparty_name: string | null;
  status: 'processing' | 'analyzed' | 'failed';
  created_at: string;
  risk_clause_count: number;
  high_risk_count: number;
}

export interface NegotiationSuggestion {
  id: string;
  clause_id: string;
  suggestion_text: string;
  created_at: string;
}

export interface Clause {
  id: string;
  contract_id: string;
  clause_index: number;
  raw_text: string;
  summary: string | null;
  risk_type: 'penalty' | 'lock_in' | 'indemnity' | 'termination' | 'none';
  risk_score: number;
  qdrant_point_id: string | null;
  created_at: string;
  suggestions: NegotiationSuggestion[];
}

export interface ContractDetail {
  id: string;
  document_id: string;
  title: string | null;
  counterparty_name: string | null;
  status: 'processing' | 'analyzed' | 'failed';
  created_at: string;
  clauses: Clause[];
}

export interface VendorCheck {
  id: string;
  gstin: string;
  company_name: string | null;
  is_valid: boolean | null;
  registration_date: string | null;
  trust_score: number | null;
  fraud_flagged: boolean;
  raw_mock_response: any;
  checked_by: string | null;
  checked_at: string;
}

export interface DraftReply {
  id: string;
  notice_id: string;
  reply_text: string;
  created_at: string;
}

export interface NoticeSummary {
  id: string;
  document_id: string | null;
  notice_type: 'demand' | 'show_cause' | 'summons' | 'other' | null;
  urgency: 'low' | 'medium' | 'high' | 'critical' | null;
  created_at: string;
  original_filename: string;
}

export interface NoticeDetail {
  id: string;
  document_id: string | null;
  raw_text: string;
  notice_type: 'demand' | 'show_cause' | 'summons' | 'other' | null;
  urgency: 'low' | 'medium' | 'high' | 'critical' | null;
  created_at: string;
  replies: DraftReply[];
}

export interface ComplianceTask {
  id: string;
  title: string;
  category: 'tax' | 'corporate' | 'labor' | 'license' | 'other';
  due_date: string | null;
  status: 'pending' | 'completed' | 'overdue';
  description: string | null;
  penalty_desc: string | null;
  document_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ComplianceDocumentAnalysis {
  id: string;
  document_id: string;
  authority: string;
  document_type: string;
  identifier_number: string | null;
  issue_date: string | null;
  expiry_date: string | null;
  status: 'active' | 'expired' | 'needs_action' | 'warning';
  risk_assessment: string | null;
  extracted_actions: any[] | null;
  created_at: string;
}

export interface ComplianceInitResponse {
  company_name: string;
  business_type: string;
  gstin: string;
  constitution: string;
  tasks: ComplianceTask[];
}
