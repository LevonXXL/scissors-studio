<template>
  <q-page class="site-page q-px-md q-py-xl">
    <h1 class="text-h4 text-weight-bold q-mb-md">Онлайн-запись</h1>
    <p class="text-body1 q-mb-lg">Выберите город, салон и удобное время в YCLIENTS.</p>
    <q-btn unelevated no-caps color="primary" label="Перейти к записи"
      :href="YCLIENTS_NETWORK_BOOKING_URL" target="_blank" rel="noopener noreferrer" />
  </q-page>
</template>

<script setup lang="ts">
import { useMeta } from 'quasar';
import { YCLIENTS_NETWORK_BOOKING_URL } from '@/utils/yclientsBooking';

useMeta({ title: 'Запись — Scissors Studio' });
</script>
