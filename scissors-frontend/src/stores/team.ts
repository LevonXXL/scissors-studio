import { defineStore } from 'pinia';
import { fetchMasters, fetchSalons } from '@/api/endpoints';
import type { Master, Salon } from '@/api/types';
import { dedupeInFlight } from '@/utils/inFlight';

export const useTeamStore = defineStore('team', {
  state: () => ({
    masters: [] as Master[],
    salons: [] as Salon[],
    loaded: false,
  }),

  actions: {
    async load() {
      if (this.loaded) return;
      return dedupeInFlight(this, 'team-data', async () => {
        if (this.loaded) return;
        try {
          const [mastersData, salonsData] = await Promise.all([
            fetchMasters(),
            fetchSalons(),
          ]);
          this.masters = mastersData;
          this.salons = salonsData;
        } catch (err) {
          console.error('Failed to load team data:', err);
        } finally {
          this.loaded = true;
        }
      });
    },
  },
});
