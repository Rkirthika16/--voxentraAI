import { apiClient } from './client';
import { NotificationItem } from '../types';

export const notificationsApi = {
  getNotifications: async (): Promise<NotificationItem[]> => {
    const res = await apiClient.get<NotificationItem[]>('/notifications');
    return res.data;
  },

  markAsRead: async (id: number): Promise<NotificationItem> => {
    const res = await apiClient.patch<NotificationItem>(`/notifications/${id}/read`);
    return res.data;
  },

  markAllAsRead: async (): Promise<{ message: string }> => {
    const res = await apiClient.post<{ message: string }>('/notifications/read-all');
    return res.data;
  }
};
