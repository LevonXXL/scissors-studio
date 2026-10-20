<template>
  <q-page class="site-page q-pa-md">
    <template v-if="page">
      <h1>{{ page.title }}</h1>
      <div class="page-content" v-html="page.content" />
      <div v-if="page.pictures.length" class="row q-gutter-md q-mt-md">
        <q-img
          v-for="pic in page.pictures"
          :key="pic.id"
          :src="pic.image"
          :alt="pic.alt"
          style="width: 240px; height: 180px"
        />
      </div>
    </template>
    <div v-else-if="loading" class="text-center q-pa-xl">
      <q-spinner color="primary" size="3em" />
    </div>
    <div v-else class="text-center q-pa-xl">
      <h1 class="text-h4">Страница недоступна</h1>
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router';
import { useMeta } from 'quasar';
import { computed, onServerPrefetch, ref, watch } from 'vue';
import { usePagesStore } from '@/stores/pages-store';

const route = useRoute();
const pagesStore = usePagesStore();

// Catch-all route supplies the page path as decoded URL segments.
const urlPath = computed(() => {
  const segments = route.params.pathMatch;
  const joined = Array.isArray(segments) ? segments.join('/') : String(segments ?? '');
  return joined.replace(/^\/+|\/+$/g, '');
});

const page = computed(() => pagesStore.byPath[urlPath.value] ?? null);
const loading = ref(false);

// Запускаем загрузку один раз сразу (работает и на сервере, и на клиенте).
// onServerPrefetch просто дожидается этого же промиса на сервере — без
// повторного запроса. Состояние Pinia-стора сериализуется Quasar SSR и
// переиспользуется на клиенте один в один, поэтому hydration mismatch нет.
const initialLoad = pagesStore.load(urlPath.value);
onServerPrefetch(() => initialLoad);

// Дозагрузка только при реальной смене urlPath — то есть при клиентской
// навигации между CMS-страницами (компонент переиспользуется для нового пути).
watch(urlPath, async (value, oldValue) => {
  if (value !== oldValue) {
    loading.value = true;
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
