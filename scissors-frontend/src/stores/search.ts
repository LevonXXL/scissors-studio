import { defineStore } from 'pinia';
import { fetchSearch, type SearchResponse } from '@/api/endpoints';

export function searchKey(query: string, page: number): string {
  return `${query.trim().toLocaleLowerCase('ru-RU')}|${page}`;
}

export const useSearchStore = defineStore('search', {
  state: () => ({
    byQuery: {} as Record<string, SearchResponse>,
    loaded: {} as Record<string, boolean>,
    loading: {} as Record<string, boolean>,
    errors: {} as Record<string, string>,
  }),

  actions: {
    async load(query: string, page = 1): Promise<void> {
      const cleanQuery = query.trim();
      if (cleanQuery.length < 3) return;
      const key = searchKey(cleanQuery, page);
      if (this.loaded[key] || this.loading[key]) return;
      this.loading[key] = true;
      try {
        this.byQuery[key] = await fetchSearch(cleanQuery, page);
        delete this.errors[key];
      } catch {
        this.errors[key] = 'Поиск временно недоступен. Попробуйте позже.';
      } finally {
        this.loaded[key] = true;
        this.loading[key] = false;
      }
    },

    async retry(query: string, page = 1): Promise<void> {
      delete this.loaded[searchKey(query, page)];
      await this.load(query, page);
    },
  },
});
