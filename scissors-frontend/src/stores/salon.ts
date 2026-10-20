// src/stores/salon.ts
import { defineStore } from 'pinia';
import { ref, watch, computed } from 'vue';
import { salons, type SalonInfo } from '@/data/salons';

export type SalonSlug = 'moscow' | 'zelenograd';

export const useSalonStore = defineStore('salon', () => {
  const selectedSalonSlug = ref<SalonSlug | null>(null);

  // Загрузка из localStorage при инициализации (только на клиенте)
  if (typeof window !== 'undefined') {
    const saved = localStorage.getItem('selectedSalonSlug') as SalonSlug;
    if (saved && salons.some(s => s.slug === saved)) {
      selectedSalonSlug.value = saved;
    } else {
      // Фоллбэк на первый салон (Москва), если ничего не сохранено
      selectedSalonSlug.value = 'moscow';
    }
  }

  // Сохранение в localStorage при изменении
  watch(selectedSalonSlug, (newVal) => {
    if (typeof window !== 'undefined' && newVal) {
      localStorage.setItem('selectedSalonSlug', newVal);
    }
  });

  const setSalon = (slug: SalonSlug) => {
    selectedSalonSlug.value = slug;
  };

  // Геттер для получения полного объекта текущего салона
  const currentSalon = computed<SalonInfo>(() =>
    salons.find(s => s.slug === selectedSalonSlug.value) || salons[0]
  );

  return {
    selectedSalonSlug,
    setSalon,
    currentSalon,
    allSalons: salons
  };
});
