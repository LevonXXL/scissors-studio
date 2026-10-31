<template>
  <q-page class="site-page q-px-md q-py-xl">
    <template v-if="aboutPage">
      <h1 class="text-h4 text-weight-bold q-mb-md">{{ aboutPage.title }}</h1>
      <div class="about-intro">
        <div class="about-content text-body1" v-html="aboutPage.content" />
        <img
          class="about-portrait"
          :src="publicAssetUrl('/img/about/mikhail-stets.png')"
          alt="Михаил Стець, основатель Scissors Studio"
          width="1460"
          height="950"
        />
      </div>
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
import { publicAssetUrl } from '@/config/urls';

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
.about-intro {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 32px;
  align-items: start;
}

.about-portrait {
  display: block;
  width: 100%;
  height: auto;
}

.about-content :deep(p) {
  margin-bottom: 16px;
}

.about-content :deep(p:last-child) {
  font-size: 1.1rem;
  font-weight: 700;
  margin-top: 24px;
}

@media (max-width: 700px) {
  .about-intro {
    grid-template-columns: 1fr;
  }
}
</style>
