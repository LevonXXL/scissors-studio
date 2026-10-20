<template>
  <q-page v-if="salon" class="q-px-md q-py-xl" style="max-width: 1200px; margin: 0 auto">
    <nav aria-label="Хлебные крошки" class="text-caption text-grey-7 q-mb-md">
      <router-link to="/">Главная</router-link>
      <span class="q-mx-xs">/</span>
      <router-link to="/salons">Салоны</router-link>
      <span class="q-mx-xs">/</span>
      <span class="text-grey-9">{{ city }}</span>
    </nav>

    <h1 class="text-h4 text-weight-bold q-mb-lg">
      Салон красоты Scissors by Stets — {{ salon.name }}
    </h1>

    <div class="row q-col-gutter-lg q-mb-xl">
      <section class="col-12 col-md-7" aria-labelledby="about-heading">
        <h2 id="about-heading" class="text-h6 text-weight-bold q-mt-none">О салоне</h2>
        <template v-if="aboutParagraphs.length">
          <p v-for="(paragraph, i) in aboutParagraphs" :key="i" class="text-body1">{{ paragraph }}</p>
        </template>
        <p v-else class="text-body1">
          Scissors by Stets — пространство независимых мастеров-партнёров.
          Салон находится по адресу: {{ salon.address }}.
        </p>
      </section>

      <aside class="col-12 col-md-5" aria-label="Контакты и запись">
        <q-card flat bordered class="q-pa-md">
          <address style="font-style: normal">
            <div class="text-subtitle2 text-grey-7">Адрес</div>
            <div class="text-body1 q-mb-md">{{ salon.address }}</div>

            <template v-if="salon.working_hours">
              <div class="text-subtitle2 text-grey-7">Режим работы</div>
              <div class="text-body1 q-mb-md">{{ salon.working_hours }}</div>
            </template>

            <template v-if="phone">
              <div class="text-subtitle2 text-grey-7">Телефон</div>
              <div class="text-body1 q-mb-md">
                <a :href="`tel:${phoneDigits}`">{{ phone }}</a>
              </div>
            </template>
          </address>

          <div v-if="staticInfo" class="row q-gutter-sm q-mb-md">
            <q-btn outline no-caps dense icon="send" label="Telegram" :href="staticInfo.telegram" target="_blank" rel="noopener" />
            <q-btn outline no-caps dense icon="chat_bubble" label="WhatsApp" :href="staticInfo.whatsapp" target="_blank" rel="noopener" />
          </div>

          <q-btn
            unelevated no-caps size="lg" class="full-width"
            label="Записаться"
            :href="bookingUrl" target="_blank" rel="noopener"
            :style="{ background: 'var(--sc-accent)', color: '#fff' }"
          />
        </q-card>
      </aside>
    </div>

    <section v-if="salon.photos.length" class="q-mb-xl" aria-labelledby="photos-heading">
      <h2 id="photos-heading" class="text-h6 text-weight-bold">Фотографии салона</h2>
      <div class="row q-col-gutter-sm">
        <div v-for="(photo, i) in salon.photos" :key="photo.id" class="col-6 col-md-4">
          <a :href="photo.image" @click.prevent="photoIndex = i">
            <!-- Обычный <img>, а не q-img: атрибуты width/height/alt/loading и
                 порядок загрузки под полным контролем — это SEO и Core Web Vitals.
                 Первое фото грузим сразу (оно, как правило, LCP), остальные — лениво. -->
            <img
              :src="photo.thumbnail"
              :width="photo.thumbnail_width"
              :height="photo.thumbnail_height"
              :alt="`${salon.name} — фото салона ${i + 1}`"
              :loading="i === 0 ? 'eager' : 'lazy'"
              :fetchpriority="i === 0 ? 'high' : 'auto'"
              decoding="async"
              class="salon-photo"
            />
          </a>
        </div>
      </div>
    </section>

    <section class="q-mb-xl" aria-labelledby="map-heading">
      <h2 id="map-heading" class="text-h6 text-weight-bold">Как нас найти</h2>
      <p class="text-body2 text-grey-8">{{ salon.address }}</p>

      <q-no-ssr>
        <YandexMap v-if="!mapUnavailable" :salons="[salon]" :zoom="16" @unavailable="mapUnavailable = true" />
        <q-banner v-else rounded class="bg-grey-2 text-grey-9">
          Карта сейчас недоступна — адрес указан выше, маршрут можно построить по ссылке ниже.
        </q-banner>
        <template #placeholder>
          <q-skeleton height="400px" />
        </template>
      </q-no-ssr>

      <p class="q-mt-sm">
        <a :href="mapLink" target="_blank" rel="noopener">Открыть на Яндекс.Картах</a>
      </p>
    </section>

    <ReviewsSection :salon-id="salon.id" :title="`Отзывы о салоне: ${salon.name}`" />

    <div class="text-center q-mt-xl">
      <q-btn
        unelevated no-caps size="lg" label="Записаться в этот салон"
        :href="bookingUrl" target="_blank" rel="noopener"
        :style="{ background: 'var(--sc-accent)', color: '#fff' }"
      />
    </div>

    <q-dialog v-model="photoDialog">
      <q-card v-if="currentPhoto" style="max-width: 95vw">
        <img :src="currentPhoto.image" :alt="`${salon.name} — фото салона ${(photoIndex ?? 0) + 1}`" style="max-width: 100%; max-height: 80vh; display: block" />
        <q-card-actions align="between">
          <q-btn flat no-caps icon="chevron_left" label="Назад" :disable="(photoIndex ?? 0) === 0" @click="photoIndex = (photoIndex ?? 0) - 1" />
          <q-btn flat no-caps label="Закрыть" v-close-popup />
          <q-btn flat no-caps icon-right="chevron_right" label="Далее" :disable="(photoIndex ?? 0) >= salon.photos.length - 1" @click="photoIndex = (photoIndex ?? 0) + 1" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>

  <q-page v-else-if="notFound" class="q-pa-xl text-center">
    <h1 class="text-h5">Салон не найден</h1>
    <p>Возможно, адрес изменился. <router-link to="/salons">Все салоны Scissors by Stets</router-link></p>
  </q-page>

  <q-page v-else class="q-pa-xl text-center">
    <h1 class="text-h5">Информация о салоне временно недоступна</h1>
    <p>Попробуйте обновить страницу чуть позже.</p>
  </q-page>
</template>

<script lang="ts">
import { definePreFetch } from '#q-app';
import { useSalonDetailsStore } from '@/stores/salon-details';

/**
 * Данные салона загружаем в preFetch, а не в onServerPrefetch: Quasar при SSR
 * вычисляет useMeta() ОДИН раз прямо в setup() и не пересчитывает после
 * загрузки данных — с onServerPrefetch в <head> попадали бы заглушки
 * (проверено на реальном SSR-ответе). preFetch отрабатывает до создания
 * компонента, и setup() сразу видит готовый салон.
 *
 * slug берём из пути: маршруты статичны (/moscow, /zelenograd), params нет.
 */
export default {
  preFetch: definePreFetch(async ({ store, currentRoute, ssrContext }) => {
    const slug = currentRoute.path.replace(/^\/+|\/+$/g, '');
    const salonStore = useSalonDetailsStore(store);
    await salonStore.load(slug);

    // Настоящие HTTP-статусы вместо "200 с текстом об ошибке" (soft 404 вредит индексации):
    // нет салона — 404; сбой бэкенда — 503 (поисковик придёт позже, а не выкинет страницу).
    if (ssrContext) {
      if (salonStore.notFound[slug]) ssrContext.res.status(404);
      else if (!salonStore.bySlug[slug]) ssrContext.res.status(503);
    }
  }),
};
</script>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useMeta } from 'quasar';
import ReviewsSection from '@/components/ReviewsSection.vue';
import YandexMap from '@/components/YandexMap.vue';
import { salons as staticSalons } from '@/data/salons';
import { buildBookingUrl } from '@/utils/booking';
import {
  absoluteUrl, buildBreadcrumbJsonLd, buildSalonJsonLd, htmlToParagraphs, toJsonLd, truncate,
} from '@/utils/seo';

// Маршруты /moscow и /zelenograd статичны и передают slug пропсом (см. router/routes.ts) —
// адреса страниц не меняются, поэтому ничего не теряется в уже проиндексированном.
const props = defineProps<{ slug: string }>();

const store = useSalonDetailsStore();
const salon = computed(() => store.bySlug[props.slug] ?? null);
const notFound = computed(() => !!store.notFound[props.slug]);

// Статичные данные (Telegram/WhatsApp, город) — в API их пока нет.
const staticInfo = computed(() => staticSalons.find((s) => s.slug === props.slug) ?? null);
const city = computed(() => staticInfo.value?.city ?? salon.value?.name ?? '');

const path = computed(() => `/${props.slug}`);
const phone = computed(() => salon.value?.phone || staticInfo.value?.phone || '');
const phoneDigits = computed(() => phone.value.replace(/[^\d+]/g, ''));
const bookingUrl = computed(() => buildBookingUrl(salon.value?.yclients_company_id));
const aboutParagraphs = computed(() => htmlToParagraphs(salon.value?.description));

const mapLink = computed(() => {
  if (staticInfo.value?.mapLink) return staticInfo.value.mapLink;
  const s = salon.value;
  return s ? `https://yandex.ru/maps/?pt=${s.longitude},${s.latitude}&z=16&l=map` : '#';
});

const mapUnavailable = ref(false);

const photoIndex = ref<number | null>(null);
const photoDialog = computed({
  get: () => photoIndex.value !== null,
  set: (open: boolean) => { if (!open) photoIndex.value = null; },
});
const currentPhoto = computed(() =>
  photoIndex.value === null ? null : salon.value?.photos[photoIndex.value] ?? null,
);

// --- Загрузка данных ---
// Основная загрузка — в preFetch выше (идемпотентна: повторный load() берёт из кэша стора).
// Здесь — страховка на случай смены slug без перезахода через роутер.
store.load(props.slug);
watch(() => props.slug, (slug) => store.load(slug));

// --- SEO ---
useMeta(() => {
  if (notFound.value) {
    return { title: 'Салон не найден — Scissors by Stets', meta: { robots: { name: 'robots', content: 'noindex' } } };
  }
  const s = salon.value;
  if (!s) {
    return { title: 'Салон — Scissors by Stets', meta: { robots: { name: 'robots', content: 'noindex' } } };
  }

  const title = `${s.name} — салон красоты Scissors by Stets`;
  const description = truncate(
    aboutParagraphs.value[0]
      ?? `Салон красоты Scissors by Stets: ${s.address}.${s.working_hours ? ` ${s.working_hours}.` : ''} Запись онлайн.`,
  );
  const url = absoluteUrl(path.value);
  const image = s.photos[0]?.image ?? s.logo ?? undefined;

  return {
    title,
    meta: {
      description: { name: 'description', content: description },
      ogType: { property: 'og:type', content: 'website' },
      ogSiteName: { property: 'og:site_name', content: 'Scissors by Stets' },
      ogLocale: { property: 'og:locale', content: 'ru_RU' },
      ogTitle: { property: 'og:title', content: title },
      ogDescription: { property: 'og:description', content: description },
      ogUrl: { property: 'og:url', content: url },
      ...(image ? { ogImage: { property: 'og:image', content: image } } : {}),
    },
    link: {
      // canonical строго на наш домен — у прежнего сайта на Tilda этот тег указывал на служебный поддомен.
      canonical: { rel: 'canonical', href: url },
    },
    script: {
      salonLd: {
        type: 'application/ld+json',
        innerHTML: toJsonLd(buildSalonJsonLd({
          salon: s, path: path.value, city: staticInfo.value?.city, description,
        })),
      },
      breadcrumbLd: {
        type: 'application/ld+json',
        innerHTML: toJsonLd(buildBreadcrumbJsonLd([
          { name: 'Главная', path: '/' },
          { name: 'Салоны', path: '/salons' },
          { name: city.value, path: path.value },
        ])),
      },
    },
  };
});
</script>

<style scoped>
.salon-photo {
  display: block;
  width: 100%;
  height: auto;
  object-fit: cover;
  border-radius: 8px;
}
</style>
