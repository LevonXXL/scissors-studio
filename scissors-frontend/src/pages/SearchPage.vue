<template>
  <q-page class="site-page q-px-md q-py-xl">
    <h1 class="text-h4 q-mt-none q-mb-lg">Поиск по сайту</h1>

    <form class="search-form row q-gutter-sm q-mb-xl" @submit.prevent="submitSearch">
      <q-input v-model="input" outlined dense class="search-form__input" label="Что найти?"
        type="search" :error="inputError" error-message="Введите не менее 3 символов" />
      <q-btn type="submit" unelevated color="primary" no-caps icon="search" label="Найти" />
    </form>

    <template v-if="query.length >= 3">
      <div v-if="error" role="alert">
        <p>{{ error }}</p>
        <q-btn flat no-caps color="primary" label="Повторить" :loading="retrying"
          @click="searchStore.retry(query, page)" />
      </div>
      <div v-else-if="!loaded" class="q-py-xl text-center"><q-spinner color="primary" size="3em" /></div>
      <template v-else>
        <p class="text-grey-7">Найдено: {{ result?.pagination.totalCount ?? 0 }}</p>
        <p v-if="!result?.data.length">По вашему запросу ничего не найдено.</p>
        <q-list v-else separator>
          <q-item v-for="hit in result.data" :key="hit.id" class="q-py-md">
            <q-item-section>
              <q-item-label caption>{{ typeLabels[hit.type] }}</q-item-label>
              <q-item-label class="text-h6"><router-link :to="hit.url">{{ hit.title }}</router-link></q-item-label>
              <q-item-label v-if="hit.content" class="search-result__description q-mt-sm">
                {{ hit.content }}
              </q-item-label>
            </q-item-section>
          </q-item>
        </q-list>
        <q-pagination v-if="pageCount > 1" :model-value="page" :max="pageCount"
          :max-pages="7" boundary-numbers class="q-mt-lg" color="primary"
          @update:model-value="goToPage" />
      </template>
    </template>
    <p v-else class="text-grey-7">Введите название услуги, специалиста, салона или раздела.</p>
  </q-page>
</template>

<script lang="ts">
import { definePreFetch } from '#q-app';
import { searchKey, useSearchStore } from '@/stores/search';

function routeQuery(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

function routePage(value: unknown): number {
  const page = Number(value);
  return Number.isSafeInteger(page) && page > 0 ? page : 1;
}

export default {
  preFetch: definePreFetch(async ({ store, currentRoute }) => {
    await useSearchStore(store).load(
      routeQuery(currentRoute.query.query), routePage(currentRoute.query.page),
    );
  }),
};
</script>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useMeta } from 'quasar';

const route = useRoute();
const router = useRouter();
const searchStore = useSearchStore();
const query = computed(() => routeQuery(route.query.query));
const page = computed(() => routePage(route.query.page));
const key = computed(() => searchKey(query.value, page.value));
const input = ref(query.value);
const inputError = ref(false);
const loaded = computed(() => !!searchStore.loaded[key.value]);
const retrying = computed(() => !!searchStore.loading[key.value]);
const result = computed(() => searchStore.byQuery[key.value]);
const error = computed(() => searchStore.errors[key.value]);
const pageCount = computed(() => Math.ceil((result.value?.pagination.totalCount ?? 0) / 30));

const typeLabels = {
  page: 'Страница', master: 'Специалист', salon: 'Салон',
  category: 'Категория услуг', service: 'Услуга',
};

watch(query, (value) => { input.value = value; inputError.value = false; });
watch([query, page], () => { void searchStore.load(query.value, page.value); });

function submitSearch() {
  const value = input.value.trim();
  inputError.value = value.length < 3;
  if (inputError.value) return;
  void router.push({ path: '/search', query: { query: value } });
}

function goToPage(value: number) {
  void router.push({ path: '/search', query: { query: query.value, page: String(value) } });
}

useMeta(() => ({
  title: query.value ? `Поиск: ${query.value} — Scissors Studio` : 'Поиск — Scissors Studio',
  meta: {
    description: { name: 'description', content: 'Поиск услуг, специалистов и салонов Scissors Studio.' },
  },
}));
</script>

<style scoped>
.search-form { align-items: flex-start; }
.search-form__input { min-width: min(100%, 420px); flex: 1; }
.search-result__description { display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.search-result__description, .search-result__description a { color: var(--sc-text-secondary); }
@media (max-width: 600px) { .search-form__input { flex-basis: 100%; } }
</style>
