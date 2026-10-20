import type { AxiosInstance } from 'axios';
import { defineBoot } from '#q-app';
import api from '@/api/client';

declare module 'vue' {
  interface ComponentCustomProperties {
    $api: AxiosInstance;
  }
}

export default defineBoot(({ app }) => {
  app.config.globalProperties.$api = api;
});

export { api };
