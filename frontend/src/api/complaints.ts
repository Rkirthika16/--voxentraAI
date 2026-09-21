import { apiClient } from './client';
import { Complaint, ComplaintHistory, ComplaintStatus, ComplaintPriority } from '../types';

export interface CreateComplaintInput {
  title?: string;
  description: string;
  category?: string;
  location?: string;
  latitude?: string;
  longitude?: string;
  priority?: ComplaintPriority;
  language?: string;
  source?: string;
  ai_metadata?: Record<string, any>;
  citizen_confirmed?: boolean;
  audio_file_path?: string;
}

export interface ComplaintFilterQuery {
  status?: ComplaintStatus;
  category?: string;
  priority?: ComplaintPriority;
  department_id?: number;
  search?: string;
  page?: number;
  page_size?: number;
}

export const complaintsApi = {
  listComplaints: async (params?: ComplaintFilterQuery): Promise<Complaint[]> => {
    const res = await apiClient.get<Complaint[]>('/complaints', { params });
    return res.data;
  },

  getMyComplaints: async (): Promise<Complaint[]> => {
    const res = await apiClient.get<Complaint[]>('/complaints/my');
    return res.data;
  },

  createComplaint: async (data: CreateComplaintInput): Promise<Complaint> => {
    const res = await apiClient.post<Complaint>('/complaints', data);
    return res.data;
  },

  getComplaintDetails: async (identifier: string | number): Promise<Complaint> => {
    const res = await apiClient.get<Complaint>(`/complaints/${identifier}`);
    return res.data;
  },

  updateStatus: async (id: number, status: ComplaintStatus, note?: string): Promise<Complaint> => {
    const res = await apiClient.patch<Complaint>(`/complaints/${id}/status`, { status, note });
    return res.data;
  },

  getHistory: async (id: number): Promise<ComplaintHistory[]> => {
    const res = await apiClient.get<ComplaintHistory[]>(`/complaints/${id}/history`);
    return res.data;
  },

  getMapPins: async (params?: { category?: string; status?: string; priority?: string; limit?: number }): Promise<Complaint[]> => {
    const res = await apiClient.get<Complaint[]>('/complaints/map/pins', { params });
    return res.data;
  }
};

