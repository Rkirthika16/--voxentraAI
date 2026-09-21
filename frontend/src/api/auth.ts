import { apiClient } from './client';
import { AuthResponse, User } from '../types';

export const authApi = {
  login: async (email: string, password: string): Promise<AuthResponse> => {
    const res = await apiClient.post<AuthResponse>('/auth/login', { email, password });
    return res.data;
  },

  register: async (data: { full_name: string; email: string; password: string; phone?: string }): Promise<AuthResponse> => {
    const res = await apiClient.post<AuthResponse>('/auth/register', data);
    return res.data;
  },

  getMe: async (): Promise<User> => {
    const res = await apiClient.get<User>('/auth/me');
    return res.data;
  },

  updateProfile: async (data: { full_name?: string; phone?: string }): Promise<User> => {
    const res = await apiClient.put<User>('/users/profile', data);
    return res.data;
  },

  logout: async (): Promise<void> => {
    try {
      await apiClient.post('/auth/logout');
    } finally {
      localStorage.removeItem('voxentra_token');
      localStorage.removeItem('voxentra_user');
    }
  }
};
