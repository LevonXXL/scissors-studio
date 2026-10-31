import { defineStore } from 'pinia';
import { fetchReviews, type FetchReviewsParams } from '@/api/endpoints';
import type { Review } from '@/api/types';

export function reviewFilterKey(params: FetchReviewsParams): string {
  return `${params.salon ?? ''}|${params.source ?? ''}|${params.withImages ? 1 : 0}|${params.limit ?? ''}`;
}

export const useReviewsStore = defineStore('reviews', {
  state: () => ({
    byFilter: {} as Record<string, Review[]>,
    loaded: {} as Record<string, boolean>,
    loading: {} as Record<string, boolean>,
  }),

  actions: {
    async load(params: FetchReviewsParams): Promise<void> {
      const key = reviewFilterKey(params);
      if (this.loaded[key]) return;

      this.loading[key] = true;
      try {
        this.byFilter[key] = await fetchReviews(params);
      } catch (error) {
        console.error('Не удалось загрузить отзывы:', error);
        this.byFilter[key] = [];
      } finally {
        this.loaded[key] = true;
        this.loading[key] = false;
      }
    },
  },
});
