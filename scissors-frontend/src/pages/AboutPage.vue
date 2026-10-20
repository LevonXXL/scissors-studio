<template>
  <q-page class="site-page q-px-md q-py-xl">
    <template v-if="aboutPage">
      <h1 class="text-h4 text-weight-bold q-mb-md">{{ aboutPage.title }}</h1>
      <div class="about-content text-body1" v-html="aboutPage.content" />
    </template>
    <div v-else-if="!loadFailed" class="text-center q-pa-xl">
      <q-spinner color="primary" size="3em" />
    </div>
    <div v-else class="text-center q-pa-xl">
      <h1 class="text-h4">Страница недоступна</h1>
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, onServerPrefetch, ref } from 'vue';
import { useMeta } from 'quasar';
import { usePagesStore } from '@/stores/pages-store';

const pagesStore = usePagesStore();
const aboutPage = computed(() => pagesStore.byPath.about ?? null);
const loadFailed = ref(false);
const pageLoad = pagesStore.load('about');

onServerPrefetch(() => pageLoad);
onMounted(() => {
  void pageLoad.then((page) => {
    loadFailed.value = !page;
  });
});

useMeta(() => ({
  title: aboutPage.value?.title_tag || 'О нас — Scissors Studio',
  meta: {
    description: {
      name: 'description',
      content: aboutPage.value?.meta_description || '',
    },
  },
}));
</script>

<style scoped>
.about-content :deep(p) {
  margin-bottom: 16px;
}

.about-content :deep(p:last-child) {
  font-size: 1.1rem;
  font-weight: 700;
  margin-top: 24px;
}
</style>
