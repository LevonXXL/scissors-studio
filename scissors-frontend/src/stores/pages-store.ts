import { defineStore } from 'pinia';
import { fetchPageByPath } from '@/api/endpoints';
import type { PageDetail } from '@/api/types';
import { dedupeInFlight } from '@/utils/inFlight';

export const usePagesStore = defineStore('pages', {
  state: () => ({
    byPath: {} as Record<string, PageDetail>,
  }),

  actions: {
    async load(urlPath: string) {
      if (this.byPath[urlPath]) return this.byPath[urlPath];
      return dedupeInFlight(this, `page:${urlPath}`, async () => {
        if (this.byPath[urlPath]) return this.byPath[urlPath];
        try {
          const page = await fetchPageByPath(urlPath);
          this.byPath[urlPath] = page;
          return page;
        } catch (err) {
          console.error(`Не удалось загрузить страницу "${urlPath}":`, err);
          return null;
        }
      });
    },
  },
});
