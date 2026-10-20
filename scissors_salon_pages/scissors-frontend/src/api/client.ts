import axios from 'axios';

const BASE_URL = import.meta.env.VITE_API_BASE_URL;

if (!BASE_URL) {
  console.warn('[API] VITE_API_BASE_URL не задан');
}

const api = axios.create({
  baseURL: BASE_URL || '',
  headers: { 'Content-Type': 'application/json' },
});

// ─── Request: подставляем access-токен (для будущего auth) ───────────────────
// api.interceptors.request.use((config) => {
//   const token = localStorage.getItem('access_token');
//   if (token) config.headers.Authorization = `Bearer ${token}`;
//   return config;
// });

// ─── Response: автообновление токена по 401 (для будущего auth) ─────────────
// api.interceptors.response.use(
//   (response) => response,
//   async (error) => { ... },
// );

export default api;
