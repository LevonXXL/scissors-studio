import { defineStore } from 'pinia';
import { fetchPageByPath } from '@/api/endpoints';
import type { PageDetail } from '@/api/types';

export const usePagesStore = defineStore('pages', {
  state: () => ({
    byPath: {} as Record<string, PageDetail>,
  }),

  actions: {
    async load(urlPath: string) {
      if (this.byPath[urlPath]) return this.byPath[urlPath];
      try {
        const page = await fetchPageByPath(urlPath);
        this.byPath[urlPath] = page;
        return page;
      } catch (err) {
        // Ошибка API (бэкенд недоступен, страницы нет и т.п.) не должна
        // ронять весь SSR-процесс — просто отдаём null, компонент покажет
        // соответствующее состояние (пока — пустую страницу, страница 404
        // подключается отдельно).
        console.error(`Не удалось загрузить страницу "${urlPath}":`, err);
        return null;
      }
    },
  },
});
