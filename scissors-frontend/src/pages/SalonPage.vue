<template>
  <q-page class="site-page q-px-md q-py-xl">
    <template v-if="salon">
      <nav class="text-caption text-grey-7 q-mb-md" aria-label="Хлебные крошки">
        <router-link to="/">Главная</router-link> / <router-link to="/salons">Салоны</router-link> / {{ salon.name }}
      </nav>

      <h1 class="text-h4 text-weight-bold q-mb-md">{{ salon.page?.title || salon.name }}</h1>
      <div v-if="salon.page?.content" class="text-body1 q-mb-xl" v-html="salon.page.content" />
      <p v-else-if="descriptionText" class="text-body1 q-mb-xl description-fallback">{{ descriptionText }}</p>

      <q-card flat bordered class="q-pa-md q-mb-xl">
        <div class="text-subtitle1 text-weight-bold">Адрес</div>
        <div>{{ salon.address }}</div>
        <template v-if="salon.working_hours">
          <div class="text-subtitle1 text-weight-bold q-mt-md">Режим работы</div>
          <div>{{ salon.working_hours }}</div>
        </template>
        <q-btn v-if="salon.phone" flat no-caps icon="phone" :label="salon.phone" :href="`tel:${salon.phone}`" class="q-mt-sm" />
        <div class="q-mt-md">
          <q-btn
            unelevated no-caps label="Онлайн-запись"
            :href="salonBookingUrl(salon)" target="_blank" rel="noopener noreferrer"
            :style="{ background: 'var(--sc-accent)', color: '#fff' }"
          />
        </div>
      </q-card>

      <section v-if="photos.length" class="q-mb-xl">
        <ImageGallery :images="photos" />
      </section>

      <section v-if="hasCoordinates" class="q-mb-xl">
        <h2 class="text-h5 text-weight-bold q-mb-md">Как нас найти</h2>
        <q-no-ssr>
          <YandexMap v-if="!mapUnavailable" :key="salon.id" :salons="[salon]" :zoom="16" @unavailable="mapUnavailable = true" />
          <q-banner v-else class="bg-grey-2">Карта временно недоступна. Адрес салона указан выше.</q-banner>
          <template #placeholder><q-skeleton height="400px" /></template>
        </q-no-ssr>
      </section>

      <ReviewsSection :key="salon.id" :salon-id="salon.id" :title="`Отзывы о салоне ${salon.name}`" />
    </template>

    <div v-else-if="salonsStore.notFound[slug]" class="text-center q-pa-xl">
      <h1 class="text-h5">Салон не найден</h1>
      <router-link to="/salons">Все салоны</router-link>
    </div>
    <div v-else-if="salonsStore.failed[slug]" class="text-center q-pa-xl">
      <h1 class="text-h5">Информация о салоне временно недоступна</h1>
    </div>
    <div v-else class="text-center q-pa-xl"><q-spinner color="primary" size="3em" /></div>
  </q-page>
</template>

<script lang="ts">
import { definePreFetch } from '#q-app';
import { useSalonsStore } from '@/stores/salons';

export default {
  preFetch: definePreFetch(async ({ store, currentRoute, ssrContext }) => {
    const slug = String(currentRoute.params.slug || currentRoute.path.replace(/^\/+|\/+$/g, ''));
    const salonsStore = useSalonsStore(store);
    await salonsStore.loadDetail(slug);
    if (ssrContext) {
      if (salonsStore.notFound[slug]) ssrContext.res.status(404);
      else if (!salonsStore.bySlug[slug]) ssrContext.res.status(503);
    }
  }),
};
</script>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useMeta } from 'quasar';
import YandexMap from '@/components/YandexMap.vue';
import ReviewsSection from '@/components/ReviewsSection.vue';
import ImageGallery from '@/components/ImageGallery.vue';
import { salonBookingUrl } from '@/utils/yclientsBooking';

const props = defineProps<{ slug: string }>();
const salonsStore = useSalonsStore();
const slug = computed(() => props.slug);
const salon = computed(() => salonsStore.bySlug[slug.value] ?? null);
const photos = computed(() => salon.value?.photos.filter((photo) => !!photo.image).map((photo) => ({
  id: photo.id,
  src: photo.image,
  alt: `Салон ${salon.value?.name || ''}`,
})) ?? []);
const mapUnavailable = ref(false);
const hasCoordinates = computed(() => {
  const coordinates = salon.value?.coordinates;
  return Array.isArray(coordinates) && coordinates.length === 2
    && coordinates.every((value) => Number.isFinite(value))
    && !(coordinates[0] === 0 && coordinates[1] === 0);
});
const descriptionText = computed(() => (salon.value?.description || '')
  .replace(/<\s*br\s*\/?>/gi, '\n')
  .replace(/<\s*\/\s*(p|div)>/gi, '\n')
  .replace(/<[^>]*>/g, ' ')
  .replace(/&nbsp;/g, ' ')
  .replace(/&amp;/g, '&')
  .replace(/\n[ \t]+/g, '\n')
  .trim());

void salonsStore.loadDetail(slug.value);
watch(slug, (value) => {
  mapUnavailable.value = false;
  void salonsStore.loadDetail(value);
});

useMeta(() => ({
  title: salon.value?.page?.title_tag || salon.value?.name || 'Салон — Scissors Studio',
  meta: {
    description: {
      name: 'description',
      content: salon.value?.page?.meta_description || '',
    },
  },
}));
</script>

<style scoped>
.description-fallback {
  white-space: pre-line;
}
</style>
