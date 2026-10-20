<template>
  <q-page class="q-px-md q-py-xl" style="max-width: 900px; margin: 0 auto">
    <h1 class="text-h4 text-weight-bold q-mb-md">Прайс</h1>
    <p class="text-body2" style="color: var(--sc-text-secondary)">
      Стоимость услуг состоит из сервисного обслуживания и услуги мастера.
      Категорию мастера смотрите в его карточке — цена зависит от уровня
      выбранного специалиста (Универсал/Модельер, Топ-стилист, Арт-директор).
    </p>

    <div class="row q-col-gutter-md q-mt-md">
      <div v-for="cat in serviceCategories" :key="cat.slug" class="col-12 col-sm-6">
        <q-card flat bordered class="q-pa-md">
          <router-link :to="`/uslugi/${cat.slug}`" class="text-h6" style="text-decoration: none; color: inherit">
            {{ cat.title }}
          </router-link>
        </q-card>
      </div>
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { useMeta } from 'quasar';
import { serviceCategories } from '@/data/services';

useMeta({ title: 'Прайс — Scissors Studio' });
</script>
