import { defineStore } from 'pinia';
import api from '@/api/client';
import { fetchSalons } from '@/api/endpoints';

export interface Price {
  level: string;
  amount: string;
}

export interface MasterPrice {
  id: number;
  name: string;
  level: string;
  amount: string | null;
}

export interface Service {
  id: number;
  title: string;
  description: string;
  group_title: string;
  subgroup_title: string;
  conditions: string;
  duration_display: string;
  url_path: string;
  image: string;
  prices: Price[];
  masters: MasterPrice[];
}

export interface Category {
  id: number;
  title: string;
  code: string;
  image_url: string;
  image_path: string;
  meta_description?: string;
  group_images: {
    name: string;
    url: string;
  }[];
  url_path: string;
  services: Service[];
}

export interface Salon {
  id: number;
  name: string;
  slug: string;
  yclients_booking_url: string;
}

export interface SalonCatalogue {
  salon: Salon;
  categories: Category[];
}

type ApiList<T> = T[] | { results?: T[] };

function toArray<T>(data: ApiList<T>): T[] {
  return Array.isArray(data) ? data : data.results ?? [];
}

function isSelectableSalon(salon: Salon): boolean {
  return (
    salon.slug.includes('zelenograd') ||
    salon.slug.includes('krasnye-vorota')
  );
}

export const useServiceCatalogStore = defineStore('serviceCatalog', {
  state: () => ({
    rootCategories: [] as Category[],
    salons: [] as Salon[],
    salonCatalogues: [] as SalonCatalogue[],
    openGroupsByPage: {} as Record<string, Record<string, boolean>>,

    rootLoaded: false,
    salonsLoaded: false,
    cataloguesLoaded: false,

    loading: false,
  }),

  actions: {
    isGroupOpen(path: string, group: string, defaultOpen = false): boolean {
      return this.openGroupsByPage[path]?.[group] ?? defaultOpen;
    },

    setGroupOpen(path: string, group: string, open: boolean): void {
      this.openGroupsByPage[path] ??= {};
      this.openGroupsByPage[path][group] = open;
    },

    /**
     * Загружает данные, необходимые для страницы каталога.
     * Вызывается до SSR-рендеринга и при клиентской навигации.
     */
    async loadForPath(path: string): Promise<void> {
      const segments = path.split('/').filter(Boolean);

      // Корневые категории нужны и каталогу, и боковому меню.
      // Загружаем их до сохранения состояния для SSR.
      await this.loadRootCategories();

      // Для категорий и отдельных услуг дополнительно нужны
      // каталоги салонов с ценами и специалистами.
      if (segments.length >= 2) {
        await this.loadSalonCatalogues();
      }
    },

    /**
     * Корневой список категорий услуг.
     */
    async loadRootCategories(): Promise<void> {
      if (this.rootLoaded) return;

      this.loading = true;

      try {
        const { data } = await api.get<ApiList<Category>>(
          '/service-categories/',
        );

        this.rootCategories = toArray(data);
        this.rootLoaded = true;
      } finally {
        this.loading = false;
      }
    },

    /**
     * Салоны и каталоги услуг каждого салона.
     */
    async loadSalonCatalogues(): Promise<void> {
      if (this.cataloguesLoaded) return;

      this.loading = true;

      try {
        if (!this.salonsLoaded) {
          this.salons = (await fetchSalons()) as Salon[];
          this.salonsLoaded = true;
        }

        const selectableSalons = this.salons.filter(isSelectableSalon);

        this.salonCatalogues = await Promise.all(
          selectableSalons.map(async (salon) => {
            const { data } = await api.get<ApiList<Category>>(
              '/service-categories/',
              {
                params: {
                  salon: salon.id,
                },
              },
            );

            return {
              salon,
              categories: toArray(data),
            };
          }),
        );

        this.cataloguesLoaded = true;
      } finally {
        this.loading = false;
      }
    },
  },
});
