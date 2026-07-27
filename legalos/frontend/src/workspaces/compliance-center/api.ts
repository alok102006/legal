import apiClient from '@/api/client';
import { ComplianceTask, ComplianceDocumentAnalysis, ComplianceInitResponse } from '@/api/types';

export const listTasks = async (): Promise<ComplianceTask[]> => {
  const response = await apiClient.get<ComplianceTask[]>('/api/v1/compliance/tasks');
  return response.data;
};

export const createTask = async (data: {
  title: string;
  category: string;
  due_date: string | null;
  description: string | null;
  penalty_desc: string | null;
}): Promise<ComplianceTask> => {
  const response = await apiClient.post<ComplianceTask>('/api/v1/compliance/tasks', data);
  return response.data;
};

export const updateTask = async (
  taskId: string,
  data: {
    status?: 'pending' | 'completed' | 'overdue';
    title?: string;
    category?: string;
    due_date?: string | null;
    description?: string | null;
    penalty_desc?: string | null;
  }
): Promise<ComplianceTask> => {
  const response = await apiClient.put<ComplianceTask>(`/api/v1/compliance/tasks/${taskId}`, data);
  return response.data;
};

export const deleteTask = async (taskId: string): Promise<{ status: string; message: string }> => {
  const response = await apiClient.delete<{ status: string; message: string }>(`/api/v1/compliance/tasks/${taskId}`);
  return response.data;
};

export const initStatutoryTasks = async (businessType: string): Promise<ComplianceTask[]> => {
  const response = await apiClient.post<ComplianceTask[]>('/api/v1/compliance/init', {
    business_type: businessType,
  });
  return response.data;
};

export const uploadComplianceFile = async (file: File): Promise<ComplianceDocumentAnalysis> => {
  const formData = new FormData();
  formData.append('file', file);
  const response = await apiClient.post<ComplianceDocumentAnalysis>('/api/v1/compliance/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

export const listAnalyses = async (): Promise<ComplianceDocumentAnalysis[]> => {
  const response = await apiClient.get<ComplianceDocumentAnalysis[]>('/api/v1/compliance/analyses');
  return response.data;
};

export const getAnalysisDetails = async (id: string): Promise<ComplianceDocumentAnalysis> => {
  const response = await apiClient.get<ComplianceDocumentAnalysis>(`/api/v1/compliance/analyses/${id}`);
  return response.data;
};

export const initStatutoryTasksByGstin = async (gstin: string): Promise<ComplianceInitResponse> => {
  const response = await apiClient.post<ComplianceInitResponse>('/api/v1/compliance/init-by-gstin', { gstin });
  return response.data;
};
