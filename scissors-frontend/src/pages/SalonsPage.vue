<template>
  <q-page class="site-page q-px-md q-py-xl">
    <h1 class="text-h4 text-weight-bold q-mb-md">{{ page?.title || 'Салоны' }}</h1>
    <div v-if="page?.content" class="text-body1 q-mb-lg" v-html="page.content" />

    <div v-if="!salonsStore.listLoaded && !salonsStore.listFailed" class="text-center q-pa-xl">
      <q-spinner color="primary" size="3em" />
    </div>
    <p v-else-if="salonsStore.listFailed" class="text-grey-7">Не удалось загрузить салоны.</p>
    <p v-else-if="!salonsStore.list.length" class="text-grey-7">Сейчас нет доступных салонов.</p>
    <div v-else class="row q-col-gutter-md">
      <div v-for="salon in salonsStore.list" :key="salon.id" class="col-12 col-sm-6">
        <router-link :to="`/salons/${salon.slug}`" class="salon-card-link">
          <q-card flat bordered class="full-height overflow-hidden">
            <q-img
              v-if="coverImage(salon) && !failedImages.has(salon.id)"
              :src="coverSource(salon)"
              :alt="`Салон ${salon.name}`"
              style="height: 220px"
              @error="handleImageError(salon)"
            />
            <div v-else class="salon-image-placeholder flex flex-center bg-grey-2 text-grey-6">
              <q-icon name="storefront" size="48px" />
            </div>
            <q-card-section>
              <h2 class="text-h6 q-mt-none q-mb-sm">{{ salon.name }}</h2>
              <div class="text-body2">{{ salon.address }}</div>
              <div v-if="salon.working_hours" class="text-caption text-grey-7 q-mt-xs">{{ salon.working_hours }}</div>
            </q-card-section>
          </q-card>
        </router-link>
      </div>
    </div>
  </q-page>
</template>

<script lang="ts">
import { definePreFetch } from '#q-app';
import { usePagesStore } from '@/stores/pages-store';
import { useSalonsStore } from '@/stores/salons';

export default {
  preFetch: definePreFetch(async ({ store }) => {
    await Promise.all([usePagesStore(store).load('salons'), useSalonsStore(store).loadList()]);
  }),
};
</script>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useMeta } from 'quasar';
import type { Salon } from '@/api/types';
import { mediaImageUrl, mediaPreviewUrl } from '@/config/urls';

const pagesStore = usePagesStore();
const salonsStore = useSalonsStore();
const page = computed(() => pagesStore.byPath.salons ?? null);
const failedImages = ref(new Set<number>());
const failedPreviews = ref(new Set<number>());
void pagesStore.load('salons');
void salonsStore.loadList();

function coverImage(salon: Salon): string | undefined {
  return salon.photos.find((photo) => !!photo.image)?.image;
}

function coverSource(salon: Salon): string | undefined {
  const original = coverImage(salon);
  return original && !failedPreviews.value.has(salon.id)
    ? mediaPreviewUrl(original, 400)
    : original && mediaImageUrl(original);
}

function handleImageError(salon: Salon) {
  const original = coverImage(salon);
  if (!failedPreviews.value.has(salon.id) && original && coverSource(salon) !== mediaImageUrl(original)) {
    failedPreviews.value.add(salon.id);
  } else {
    failedImages.value.add(salon.id);
  }
}

useMeta(() => ({
  title: page.value?.title_tag || 'Салоны — Scissors Studio',
  meta: {
    description: { name: 'description', content: page.value?.meta_description || '' },
  },
}));
</script>

<style scoped>
.salon-card-link {
  display: block;
  height: 100%;
  color: inherit;
  text-decoration: none;
}
.salon-image-placeholder {
  height: 220px;
}
</style>
