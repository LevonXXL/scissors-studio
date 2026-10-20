<template>
  <q-page class="q-px-md q-py-xl" style="max-width: 800px; margin: 0 auto">
    <h1 class="text-h4 text-weight-bold q-mb-md">О нас</h1>
    <p class="text-body1">
      Привет! Я Михаил Стець, владелец, идейный вдохновитель и арт-директор сети
      салонов красоты Scissors.
    </p>
    <p class="text-body1">
      Scissors — это пространство, где собрана команда партнёров-профессионалов.
      Наш общий подход строится на синергии высокого профессионализма и
      безупречного сервиса: здесь нет случайных людей, а есть общая цель дарить
      вам гармонию и мастерство высшего уровня.
    </p>
    <p class="text-body1">
      Наша задача — создать тот образ, который будет соответствовать вашему
      мироощущению и восприятию себя, вашему образу жизни и задачам.
    </p>
    <p class="text-body1">Приходите в Scissors. Позвольте себе себя.</p>
    <p class="text-subtitle1 text-weight-bold q-mt-lg">Михаил Стець</p>
  </q-page>
</template>

<script setup lang="ts">
import { useMeta } from 'quasar';

useMeta({
  title: 'О нас — Scissors Studio',
  meta: {
    description: {
      name: 'description',
      content: 'Scissors Studio — пространство, где собрана команда партнёров-профессионалов.',
    },
  },
});
</script>
