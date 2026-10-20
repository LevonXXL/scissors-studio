import { defineStore } from 'pinia';
import { ApiError } from '@/api/client';
import { fetchSalonBySlug, fetchSalons } from '@/api/endpoints';
import type { Salon } from '@/api/types';

export const useSalonsStore = defineStore('salons', {
  state: () => ({
    list: [] as Salon[],
    listLoaded: false,
    listFailed: false,
    bySlug: {} as Record<string, Salon>,
    notFound: {} as Record<string, true>,
    failed: {} as Record<string, true>,
  }),

  actions: {
    async loadList() {
      if (this.listLoaded) return;
      try {
        this.list = await fetchSalons();
        this.listLoaded = true;
        this.listFailed = false;
        for (const salon of this.list) this.bySlug[salon.slug] = salon;
      } catch {
        this.listFailed = true;
      }
    },

    async loadDetail(slug: string) {
      if (this.bySlug[slug] || this.notFound[slug]) return;
      delete this.failed[slug];
      try {
        this.bySlug[slug] = await fetchSalonBySlug(slug);
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) this.notFound[slug] = true;
        else this.failed[slug] = true;
      }
    },
  },
});
