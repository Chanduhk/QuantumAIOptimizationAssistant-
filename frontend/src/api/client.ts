import axios, { AxiosError, InternalAxiosRequestConfig, AxiosResponse } from 'axios';
import { useToastStore } from '@/stores/toastStore';

export type ApiErrorKind = 'authentication' | 'validation' | 'server' | 'network' | 'http';

export class ApiRequestError extends Error {
  constructor(
    message: string,
    readonly kind: ApiErrorKind,
    readonly status?: number,
  ) {
    super(message);
    this.name = 'ApiRequestError';
  }
}

function detailMessage(detail: unknown): string | undefined {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    const messages = detail.flatMap((entry: unknown) => {
      if (typeof entry !== 'object' || entry === null || !('msg' in entry)) return [];
      const message = (entry as { msg?: unknown }).msg;
      return typeof message === 'string' ? [message] : [];
    });
    return messages.length ? messages.join('; ') : undefined;
  }
  return undefined;
}

export function getApiErrorMessage(error: unknown, fallback = 'The request could not be completed.'): string {
  return error instanceof Error ? error.message : fallback;
}

// Set VITE_API_URL when the frontend and API are hosted separately.
// In browser development, default to '' to use the Vite server proxy and avoid IPv6 resolution latency.
const baseURL = import.meta.env.VITE_API_URL !== undefined 
  ? import.meta.env.VITE_API_URL 
  : (typeof window !== 'undefined' ? '' : 'http://127.0.0.1:8000');

export const apiClient = axios.create({
  baseURL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 seconds
});

// Request Interceptor
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    if (!['get', 'head', 'options'].includes((config.method || 'get').toLowerCase())) {
      const csrf = document.cookie
        .split('; ')
        .find((entry) => entry.startsWith('heliox_csrf='))
        ?.slice('heliox_csrf='.length);
      if (csrf) config.headers.set('X-CSRF-Token', decodeURIComponent(csrf));
    }
    try {
      const userTz = Intl.DateTimeFormat().resolvedOptions().timeZone;
      if (userTz) config.headers.set('X-User-Timezone', userTz);
    } catch {
      // Intl fallback
    }
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
  (error: AxiosError<unknown>) => {
    if (!error.response) {
      const normalized = new ApiRequestError('Could not connect to the server. Check the API URL and your connection.', 'network');
      useToastStore.getState().addToast({
        type: 'error',
        title: 'Network Error',
        message: normalized.message,
      });
      return Promise.reject(normalized);
    } else {
      const status = error.response.status;
      const body = error.response.data;
      const detail = typeof body === 'object' && body !== null && 'detail' in body
        ? detailMessage((body as { detail?: unknown }).detail)
        : undefined;
      const kind: ApiErrorKind = status === 401 || status === 403
        ? 'authentication'
        : status === 422 || status === 400
          ? 'validation'
          : status >= 500
            ? 'server'
            : 'http';
      const normalized = new ApiRequestError(
        detail ?? (status === 401
          ? 'Your session is no longer valid. Sign in again.'
          : status === 403
            ? 'You are not authorized to perform this action.'
            : `Request failed (${status}).`),
        kind,
        status,
      );
      if (status === 401 && !error.config?.url?.endsWith('/auth/me') && !error.config?.url?.endsWith('/auth/login') && !error.config?.url?.endsWith('/auth/register')) {
        window.dispatchEvent(new Event('heliox:unauthorized'));
      }
      if (status >= 500) {
        useToastStore.getState().addToast({
          type: 'error',
          title: 'Server Error',
          message: normalized.message,
        });
      }
      return Promise.reject(normalized);
    }
  }
);
