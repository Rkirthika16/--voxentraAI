import { apiClient } from './client';
import { Complaint, User } from '../types';

export const officersApi = {
  getAssignedComplaints: async (assignedOnly = false): Promise<Complaint[]> => {
    const res = await apiClient.get<Complaint[]>('/officers/complaints', {
      params: { assigned_only: assignedOnly },
    });
    return res.data;
  },

  assignComplaint: async (complaintId: number, officerId: number, notes?: string): Promise<Complaint> => {
    const res = await apiClient.post<Complaint>(`/officers/assign?complaint_id=${complaintId}`, {
      officer_id: officerId,
      notes,
    });
    return res.data;
  },

  listOfficers: async (departmentId?: number): Promise<User[]> => {
    const res = await apiClient.get<User[]>('/officers/list', {
      params: { department_id: departmentId },
    });
    return res.data;
  }
};
