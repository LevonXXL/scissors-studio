<template>
  <router-view />
</template>

<script setup lang="ts">
import { useMeta } from 'quasar';

// Заголовок по умолчанию для страниц без своего useMeta. <title> убран из index.html:
// Quasar при SSR ДОПИСЫВАЕТ свои теги в <head>, а не заменяет шаблонные — с title в
// шаблоне на каждой странице получалось два <title>. Страничные useMeta переопределяют это значение.
useMeta({ title: 'Scissors by Stets — салоны красоты в Москве и Зеленограде' });
</script>
