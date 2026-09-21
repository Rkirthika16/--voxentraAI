import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export const apiClient = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Automatic Bearer token interceptor
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('voxentra_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor for clear error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      // Don't auto-redirect if checking auth or on login page
      const isAuthCheck = error.config?.url?.includes('/auth/me');
      if (!isAuthCheck && !window.location.pathname.includes('/login')) {
        localStorage.removeItem('voxentra_token');
        localStorage.removeItem('voxentra_user');
      }
    }
    return Promise.reject(error);
  }
);
