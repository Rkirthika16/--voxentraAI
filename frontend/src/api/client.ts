import axios from 'axios';

const getApiBaseUrl = (): string => {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (envUrl && !envUrl.includes('localhost') && !envUrl.includes('127.0.0.1')) {
    return `${envUrl}/api/v1`;
  }
  if (typeof window !== 'undefined' && window.location.hostname) {
    if (window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
      return `http://${window.location.hostname}:8000/api/v1`;
    }
  }
  return 'http://127.0.0.1:8000/api/v1';
};

export const apiClient = axios.create({
  baseURL: getApiBaseUrl(),
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
