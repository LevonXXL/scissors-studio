<template>
  <q-page>
    <!-- Hero -->
    <section class="q-px-md q-py-xl text-center" style="max-width: 1200px; margin: 0 auto">
      <div class="text-overline text-primary text-weight-bold">
        ПРОСТРАНСТВО НЕЗАВИСИМЫХ МАСТЕРОВ SCISSORS STUDIO
      </div>
      <h1 class="text-h3 text-weight-bold q-mt-sm">Стратегический подход к вашему образу</h1>
      <p class="text-body1 q-mt-md text-grey-8">
        У нас можно полностью довериться профессионалам: персональная бьюти-стратегия,
        современный подход и точность исполнения гарантируют естественный, уверенный
        и безупречный результат.
      </p>
      <q-btn
        unelevated no-caps size="lg" label="Онлайн-запись" class="q-mt-md"
        color="primary"
        @click="openBooking"
      />
    </section>

    <!-- Преимущества -->
    <section class="q-px-md q-py-xl" style="max-width: 1200px; margin: 0 auto">
      <h2 class="text-h5 text-weight-bold q-mb-md text-center">Наши преимущества</h2>
      <div class="row q-col-gutter-md">
        <div v-for="(item, index) in advantages" :key="item.title" class="col-12 col-sm-6 col-md-4">
          <q-card flat bordered class="q-pa-md full-height hover-lift">
            <div class="text-subtitle1 text-weight-bold">{{ item.title }}</div>
            <img
              :src="item.icon"
              alt="icon"
              class="q-mb-md"
              style="width: 40px; height: 40px; object-fit: contain; filter: brightness(0);"
            />
            <div class="text-body2 q-mt-xs text-grey-8">
              {{ item.description }}
            </div>
          </q-card>
        </div>
      </div>
    </section>

    <!-- Отзывы -->
    <ReviewsSection has-images />

  </q-page>
</template>

<script setup lang="ts">
import { useMeta } from 'quasar';
import { advantages } from '@/data/home';
import ReviewsSection from '@/components/ReviewsSection.vue';

const openBooking = () => {
  console.log('Открыть запись');
};

useMeta({
  title: 'Scissors Studio — пространство независимых мастеров',
  meta: {
    description: {
      name: 'description',
      content: 'Scissors Studio — пространство независимых мастеров-партнёров. Стратегический подход к вашему образу в Москве и Зеленограде.',
    },
  },
});
</script>

<style scoped>
.hover-lift {
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.hover-lift:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.08) !important;
}
</style>
