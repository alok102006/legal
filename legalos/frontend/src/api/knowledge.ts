import apiClient from './client';

export interface AddressInfo {
  building_no?: string;
  floor_no?: string;
  building_name?: string;
  street?: string;
  location?: string;
  district?: string;
  pincode?: string;
  state?: string;
  formatted?: string;
}

export interface CompanyDocument {
  id: string;
  company_id: string;
  document_id?: string;
  title: string;
  document_category: string;
  summary?: string;
  file_name?: string;
  file_type?: string;
  file_path?: string;
  extracted_text?: string;
  created_at: string;
}

export interface RegisteredCompany {
  id: string;
  gstin: string;
  legal_name: string;
  trade_name?: string;
  entity_type?: string;
  registration_date?: string;
  taxpayer_type?: string;
  status: string;
  state_jurisdiction?: string;
  center_jurisdiction?: string;
  principal_address?: AddressInfo;
  nature_of_business?: string[];
  registered_by?: string;
  created_at: string;
  updated_at: string;
  documents: CompanyDocument[];
}

export interface CompanyProfilePreview {
  gstin: string;
  legal_name: string;
  trade_name?: string;
  entity_type?: string;
  registration_date?: string;
  taxpayer_type?: string;
  status: string;
  state_jurisdiction?: string;
  center_jurisdiction?: string;
  principal_address?: AddressInfo;
  nature_of_business?: string[];
  raw_response?: Record<string, any>;
}

export interface GroundTruthExcerpt {
  document_title: string;
  file_name?: string;
  excerpt: string;
}

export interface AskKnowledgeResponse {
  answer: string;
  company_context?: string;
  sources: string[];
  ground_truth_excerpts?: GroundTruthExcerpt[];
}

export const previewCompanyGstin = async (gstin: string): Promise<CompanyProfilePreview> => {
  const response = await apiClient.post<CompanyProfilePreview>('/api/v1/knowledge/companies/preview', { gstin });
  return response.data;
};

export const registerCompany = async (gstin: string): Promise<RegisteredCompany> => {
  const response = await apiClient.post<RegisteredCompany>('/api/v1/knowledge/companies', { gstin });
  return response.data;
};

export const getRegisteredCompanies = async (): Promise<RegisteredCompany[]> => {
  const response = await apiClient.get<RegisteredCompany[]>('/api/v1/knowledge/companies');
  return response.data;
};

export const getCompanyDetails = async (companyId: string): Promise<RegisteredCompany> => {
  const response = await apiClient.get<RegisteredCompany>(`/api/v1/knowledge/companies/${companyId}`);
  return response.data;
};

export const deleteRegisteredCompany = async (companyId: string): Promise<void> => {
  await apiClient.delete(`/api/v1/knowledge/companies/${companyId}`);
};

export const uploadCompanyDocumentFile = async (
  companyId: string,
  file: File,
  title?: string,
  category: string = 'Policy'
): Promise<CompanyDocument> => {
  const formData = new FormData();
  formData.append('company_id', companyId);
  formData.append('file', file);
  if (title) formData.append('title', title);
  formData.append('document_category', category);

  const response = await apiClient.post<CompanyDocument>('/api/v1/knowledge/documents/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

export const deleteCompanyDocument = async (documentId: string): Promise<void> => {
  await apiClient.delete(`/api/v1/knowledge/documents/${documentId}`);
};


export const askKnowledgeAI = async (
  question: string,
  companyId?: string
): Promise<AskKnowledgeResponse> => {
  const response = await apiClient.post<AskKnowledgeResponse>('/api/v1/knowledge/ask', {
    question,
    company_id: companyId
  });
  return response.data;
};
