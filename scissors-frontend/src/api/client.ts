import axios from 'axios';
import { API_BASE_URL } from '@/config/urls';

const BASE_URL = API_BASE_URL;

if (!BASE_URL) {
  console.warn('[API] VITE_API_BASE_URL не задан');
}

const api = axios.create({
  baseURL: BASE_URL || '',
  headers: { 'Content-Type': 'application/json' },
});

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly retryAfter: number | null,
  ) {
    super(message);
  }
}

api.interceptors.request.use((config) => {
  // No browser token is read or serialized during SSR.
  if (typeof window !== 'undefined') {
    const token = window.localStorage.getItem('access_token');
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (axios.isAxiosError(error)) {
      const data = error.response?.data as { detail?: string; [key: string]: unknown } | undefined;
      const firstField = data && Object.values(data).find((value) => Array.isArray(value));
      const message = typeof data?.detail === 'string'
        ? data.detail
        : Array.isArray(firstField) && typeof firstField[0] === 'string'
          ? firstField[0]
          : 'Не удалось выполнить запрос.';
      const retryHeader = error.response?.headers['retry-after'];
      const retryAfter = retryHeader ? Number(retryHeader) : null;
      // Never reject the AxiosError itself: it contains request headers, including JWT.
      return Promise.reject(new ApiError(message, error.response?.status ?? 0, Number.isFinite(retryAfter) ? retryAfter : null));
    }
    return Promise.reject(new ApiError('Не удалось выполнить запрос.', 0, null));
  },
);

export default api;
