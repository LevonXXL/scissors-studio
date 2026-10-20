<template>
  <q-page class="q-pa-md">
    <h1>Салоны</h1>

    <!-- q-no-ssr: карта требует window/DOM, на сервере не рендерится вообще,
         на клиенте после гидратации показывается вместо плейсхолдера -->
    <q-no-ssr>
      <YandexMap :salons="salons" />
      <template #placeholder>
        <q-skeleton height="400px" />
      </template>
    </q-no-ssr>

    <div class="row q-col-gutter-md q-mt-md">
      <div v-for="salon in salons" :key="salon.id" class="col-12 col-sm-6">
        <q-card>
          <q-card-section>
            <div class="text-h6">{{ salon.name }}</div>
            <div>{{ salon.address }}</div>
            <div class="text-caption">{{ salon.working_hours }}</div>
            <div class="text-caption">{{ salon.phone }}</div>
          </q-card-section>
        </q-card>
      </div>
    </div>
  </q-page>
</template>

<script setup lang="ts">
// Этап 1 (статика по образу и подобию Tilda) — реальные данные о салонах
// захардкожены, как и остальные страницы. Этап 2 переведёт это на
// GET /api/v1/salons/ (см. api/endpoints.ts — функция уже готова).
import { useMeta } from 'quasar';
import type { Salon } from '@/api/types';
import YandexMap from '@/components/YandexMap.vue';

const salons: Salon[] = [
  {
    id: 1,
    name: 'Москва, Красные ворота',
    address: 'Большой Козловский переулок, 11/4',
    latitude: '55.769600',
    longitude: '37.652200',
    coordinates: [55.7696, 37.6522],
    phone: '+7 (926) 071-71-63',
    working_hours: 'Ежедневно 10:00 — 22:00',
    position: 0,
  },
  {
    id: 2,
    name: 'Зеленоград, 17 район',
    address: 'Георгиевский проспект, 33А, к.2',
    latitude: '55.987200',
    longitude: '37.181300',
    coordinates: [55.9872, 37.1813],
    phone: '+7 (926) 729-79-89',
    working_hours: 'Ежедневно 10:00 — 21:00',
    position: 1,
  },
];

useMeta({ title: 'Салоны — Scissors Studio' });
</script>
