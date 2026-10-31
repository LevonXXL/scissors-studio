// src/stores/salon.ts
import { defineStore } from 'pinia';
import { ref, watch, computed } from 'vue';
import { salons, type SalonInfo } from '@/data/salons';

export type SalonSlug = 'moscow' | 'zelenograd';

export const useSalonStore = defineStore('salon', () => {
  const selectedSalonSlug = ref<SalonSlug | null>(null);

  // Read browser preferences only after the server markup is hydrated.
  const restoreSelection = () => {
    if (typeof window === 'undefined') return;
    try {
      const saved = window.localStorage.getItem('selectedSalonSlug') as SalonSlug;
      selectedSalonSlug.value = saved && salons.some(s => s.slug === saved)
        ? saved
        : 'moscow';
    } catch {
      selectedSalonSlug.value = 'moscow';
    }
  };

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
    salons.find(s => s.slug === selectedSalonSlug.value) || salons[0]!
  );

  return {
    selectedSalonSlug,
    setSalon,
    restoreSelection,
    currentSalon,
    allSalons: salons
  };
});
