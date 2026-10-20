<template>
  <q-page class="q-px-md q-py-xl" style="max-width: 900px; margin: 0 auto">
    <h1 class="text-h4 text-weight-bold">Стань частью дружной команды Scissors Studio</h1>
    <p class="text-body1" style="color: var(--sc-text-secondary)">
      Всегда в поиске талантливых ребят, которые горят своим делом
    </p>

    <p class="text-body1 q-mt-lg">
      Мы ценим вклад и труд наших сотрудников и стремимся создать условия для
      их профессионального роста и развития.
    </p>

    <div class="row q-col-gutter-md q-mt-md">
      <div v-for="block in benefits" :key="block.title" class="col-12 col-sm-6">
        <q-card flat bordered class="q-pa-md full-height">
          <div class="text-subtitle1 text-weight-bold">{{ block.title }}</div>
          <ul class="q-mt-xs q-pl-md">
            <li v-for="line in block.lines" :key="line">{{ line }}</li>
          </ul>
        </q-card>
      </div>
    </div>

    <h2 class="text-h5 text-weight-bold q-mt-xl">Карьера в Scissors</h2>
    <p class="text-body2">
      Для каждого члена команды разработана карта развития: от стажёра до
      топ-стилиста / мастера-модельера, от администратора до управляющего.
    </p>

    <q-btn
      unelevated no-caps label="Хочу в команду" class="q-mt-lg"
      :style="{ background: 'var(--q-primary)', color: '#fff' }"
    />
  </q-page>
</template>

<script setup lang="ts">
// ⚠️ КОНТЕНТ ЭТОЙ СТРАНИЦЫ СКОПИРОВАН С TILDA ДОСЛОВНО (этап 1 — визуальный
// паритет). В аудите контента ранее было отмечено: формулировки "оформление
// по ТК РФ", "выплата зп в срок", карьера "от администратора до управляющего"
// противоречат модели независимых мастеров-партнёров. НЕ редактируем текст
// в рамках верстки — это отдельная задача содержательного аудита, не рисковать
// тихо поменять смысл при переносе на новый стек.
import { useMeta } from 'quasar';

const benefits = [
  {
    title: 'Реализация',
    lines: ['возможность внедрять собственные идеи в салоне', 'возможность реализовать потенциал'],
  },
  {
    title: 'Регулярное обучение',
    lines: [
      'индивидуальная карта развития',
      'судьи и тренеры чемпионатов прокачивают мастеров',
      'топ тренеры России обучают администраторов',
    ],
  },
  {
    title: 'Комфортные условия',
    lines: ['современный интерьер в салонах', 'инструменты и материалы для работы', 'взаимное уважение друг к другу'],
  },
  {
    title: 'Уверенность в завтрашнем дне',
    lines: ['большая клиентская база', 'сотрудники всегда обеспечены работой'],
  },
  {
    title: 'Стабильность',
    lines: ['оформление по ТК РФ', 'выплата зп в срок', 'удобный график работы'],
  },
];

useMeta({
  title: 'Вакансии — Scissors Studio',
});
</script>
