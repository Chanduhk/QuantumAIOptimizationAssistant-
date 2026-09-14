import axios, { AxiosError, InternalAxiosRequestConfig, AxiosResponse } from 'axios';
import { useToastStore } from '@/stores/toastStore';

// Determine base URL, assuming backend runs on port 8000 locally if not in prod
const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 seconds
});

// Request Interceptor
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // We can add auth tokens here in future phases
    // const token = localStorage.getItem('token');
    // if (token) {
    //   config.headers.Authorization = `Bearer ${token}`;
    // }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response Interceptor
apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    return response;
  },
  (error: AxiosError) => {
    // Add centralized error handling
    if (!error.response) {
      useToastStore.getState().addToast({
        type: 'error',
        title: 'Network Error',
        message: 'Could not connect to the server. Please check your connection.',
      });
    } else {
      const status = error.response.status;
      const data = error.response.data as any;
      
      // We don't want to show a toast for 404s on specific resources as they might be handled locally
      if (status >= 500) {
        useToastStore.getState().addToast({
          type: 'error',
          title: 'Server Error',
          message: data?.detail || 'An unexpected error occurred on the server.',
        });
      }
    }
    
    return Promise.reject(error);
  }
);
