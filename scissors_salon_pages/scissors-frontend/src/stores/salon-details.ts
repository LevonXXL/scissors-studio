import { defineStore } from 'pinia';
import { fetchSalonBySlug } from '@/api/endpoints';
import type { Salon } from '@/api/types';

/**
 * Кэш салонов по slug. Через Pinia, а не локальный ref в компоненте — иначе
 * при SSR данные, загруженные на сервере, не доедут до клиента (Quasar
 * сериализует состояние Pinia в HTML автоматически) и случится hydration
 * mismatch. Тот же приём, что в pages-store.ts.
 */
export const useSalonDetailsStore = defineStore('salon-details', {
  state: () => ({
    bySlug: {} as Record<string, Salon>,
    notFound: {} as Record<string, true>,
  }),

  actions: {
    async load(slug: string) {
      if (this.bySlug[slug] || this.notFound[slug]) return;
      try {
        this.bySlug[slug] = await fetchSalonBySlug(slug);
      } catch (err) {
        if ((err as { response?: { status?: number } })?.response?.status === 404) {
          this.notFound[slug] = true;
        } else {
          // Сбой бэкенда не должен ронять SSR-процесс; страница покажет "временно недоступно".
          console.error(`Не удалось загрузить салон "${slug}":`, err);
        }
      }
    },
  },
});
