<template>
  <nav aria-label="Хлебные крошки" class="breadcrumbs text-caption text-grey-7">
    <router-link to="/">Главная</router-link>
    <template v-for="(item, index) in items" :key="item.url_path">
      <span aria-hidden="true" class="q-mx-sm">/</span>
      <span v-if="index === items.length - 1" aria-current="page">{{ item.link_title }}</span>
      <router-link v-else :to="`/${item.url_path}`">{{ item.link_title }}</router-link>
    </template>
  </nav>
</template>

<script setup lang="ts">
import type { PageBreadcrumb } from '@/api/types';

defineProps<{ items: PageBreadcrumb[] }>();
</script>

<style scoped>
.breadcrumbs {
  line-height: 1.5;
}
</style>
