<template>
  <q-page class="site-page q-pa-md">
    <template v-if="page">
      <template v-if="page.master">
        <div class="master-profile">
          <div class="master-profile__copy">
            <h1>{{ page.master.name }}</h1>
            <div v-if="page.master.bio" class="page-content" v-html="page.master.bio" />
          </div>
          <img v-if="page.master.photo" class="master-profile__photo"
            :src="mediaImageUrl(page.master.photo)" :alt="page.master.name" />
        </div>
        <div v-if="page.content" class="page-content q-mt-lg" v-html="page.content" />
      </template>
      <template v-else>
        <h1 v-if="!isCategoryPage">{{ page.title }}</h1>
        <div v-if="!isCategoryPage" class="page-content" v-html="page.content" />
      </template>
      <ServiceCatalogue v-if="urlPath === 'uslugi' || urlPath.startsWith('uslugi/')"
        :path="urlPath" :page-title="page.title" :page-content="page.content" />
      <div v-if="page.yclients_booking_links?.length && !urlPath.startsWith('uslugi')" class="row q-gutter-sm q-mt-md">
        <q-btn v-for="link in page.yclients_booking_links" :key="link.salon_id"
          unelevated no-caps color="primary"
          :label="page.yclients_booking_links.length === 1 ? 'Записаться' : `Записаться — ${link.salon_name}`"
          :href="link.url" target="_blank" rel="noopener noreferrer" />
      </div>
      <template v-if="pictures.length && !isCategoryPage">
        <h2 v-if="page.master" class="text-h5 q-mt-xl q-mb-md">Примеры работ</h2>
        <ImageGallery :images="pictures" class="q-mt-md" :ratio="4 / 3" />
      </template>
    </template>
    <div v-else-if="loading" class="text-center q-pa-xl">
      <q-spinner color="primary" size="3em" />
    </div>
    <div v-else class="text-center q-pa-xl">
      <h1 class="text-h4">Страница недоступна</h1>
    </div>
  </q-page>
</template>

<script lang="ts">
import { definePreFetch } from '#q-app';
import { usePagesStore } from '@/stores/pages-store';
import { useServiceCatalogStore } from '@/stores/serviceCatalog';

function pagePath(pathMatch: unknown): string {
  const joined = Array.isArray(pathMatch) ? pathMatch.join('/') : String(pathMatch ?? '');
  return joined.replace(/^\/+|\/+$/g, '');
}

export default {
  preFetch: definePreFetch(async ({ store, currentRoute }) => {
    const path = pagePath(currentRoute.params.pathMatch);
    const pageLoad = usePagesStore(store).load(path);
    if (path === 'uslugi' || path.startsWith('uslugi/')) {
      await Promise.all([pageLoad, useServiceCatalogStore(store).loadForPath(path)]);
    } else {
      await pageLoad;
    }
  }),
};
</script>

<script setup lang="ts">
import { useRoute } from 'vue-router';
import { useMeta } from 'quasar';
import { computed, onMounted, ref, watch } from 'vue';
import ImageGallery from '@/components/ImageGallery.vue';
import ServiceCatalogue from '@/components/ServiceCatalogue.vue';
import { mediaImageUrl } from '@/config/urls';

const route = useRoute();
const pagesStore = usePagesStore();

// Catch-all route supplies the page path as decoded URL segments.
const urlPath = computed(() => pagePath(route.params.pathMatch));

const page = computed(() => pagesStore.byPath[urlPath.value] ?? null);
const isCategoryPage = computed(() => urlPath.value.startsWith('uslugi/') && urlPath.value.split('/').length === 2);
const pictures = computed(() => page.value?.pictures.filter((pic) => !!pic.image).map((pic) => ({
  id: pic.id,
  src: pic.image,
  alt: pic.alt || page.value?.title || '',
})) ?? []);
const loading = ref(false);

// A client-only offline shell has no SSR state. Valid SSR pages skip this.
onMounted(() => {
  if (page.value) return;
  loading.value = true;
  void pagesStore.load(urlPath.value).finally(() => { loading.value = false; });
});

// Дозагрузка только при реальной смене urlPath — то есть при клиентской
// навигации между CMS-страницами (компонент переиспользуется для нового пути).
watch(urlPath, async (value, oldValue) => {
  if (value !== oldValue) {
    loading.value = !pagesStore.byPath[value];
    await pagesStore.load(value);
    loading.value = false;
  }
});

useMeta(() => ({
  title: page.value?.title_tag || page.value?.title || 'Scissors Studio',
  meta: {
    description: {
      name: 'description',
      content: page.value?.meta_description || '',
    },
  },
}));
</script>

<style scoped>
.master-profile {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(260px, 38%);
  align-items: start;
  gap: 32px;
}

.master-profile__copy { min-width: 0; }
.master-profile__photo {
  display: block;
  width: 100%;
  height: auto;
  border-radius: 8px;
}

@media (max-width: 700px) {
  .master-profile { grid-template-columns: 1fr; }
}
</style>
