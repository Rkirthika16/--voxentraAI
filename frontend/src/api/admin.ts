import { apiClient } from './client';
import { AdminStats, Department, User } from '../types';

export const adminApi = {
  getStats: async (): Promise<AdminStats> => {
    const res = await apiClient.get<AdminStats>('/admin/stats');
    return res.data;
  },

  listUsers: async (role?: string): Promise<User[]> => {
    const res = await apiClient.get<User[]>('/users', { params: { role } });
    return res.data;
  },

  createOfficer: async (data: { full_name: string; email: string; password: string; phone?: string; department_id: number }): Promise<User> => {
    const res = await apiClient.post<User>('/users/officer', data);
    return res.data;
  },

  listDepartments: async (): Promise<Department[]> => {
    const res = await apiClient.get<Department[]>('/departments');
    return res.data;
  },

  createDepartment: async (data: { code: string; name: string; description?: string }): Promise<Department> => {
    const res = await apiClient.post<Department>('/departments', data);
    return res.data;
  },

  updateDepartment: async (id: number, data: { name?: string; description?: string; is_active?: boolean }): Promise<Department> => {
    const res = await apiClient.put<Department>(`/departments/${id}`, data);
    return res.data;
  },

  getEscalations: async () => {
    const res = await apiClient.get('/admin/escalations');
    return res.data;
  },

  resolveEscalation: async (id: number) => {
    const res = await apiClient.post(`/admin/escalations/${id}/resolve`);
    return res.data;
  }
};
