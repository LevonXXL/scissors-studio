import axios, { type AxiosInstance } from 'axios';
import { defineBoot } from '#q-app';

declare module 'vue' {
  interface ComponentCustomProperties {
    $api: AxiosInstance;
  }
}

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL as string,
});

export default defineBoot(({ app }) => {
  app.config.globalProperties.$api = api;
});

export { api };
