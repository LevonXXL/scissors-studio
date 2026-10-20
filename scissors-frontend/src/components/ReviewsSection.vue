<template>
  <section class="q-px-md q-py-xl bg-grey-1 relative-position">
    <h2 class="text-h5 text-weight-bold q-mb-md text-center">{{ title }}</h2>

    <!-- Фильтры — ненавязчивые чипы, не полноразмерные кнопки -->
    <div class="site-page row justify-center q-gutter-xs q-mb-md">
      <template v-if="!lockedSalonId">
        <q-chip
          v-for="salon in salonOptions"
          :key="salon.value ?? 'all'"
          clickable dense
          :outline="selectedSalonId !== salon.value"
          :color="selectedSalonId === salon.value ? 'primary' : undefined"
          :text-color="selectedSalonId === salon.value ? 'white' : undefined"
          @click="selectedSalonId = salon.value"
        >
          {{ salon.label }}
        </q-chip>
        <q-separator vertical inset class="q-mx-xs" />
      </template>

      <q-chip
        v-for="source in sourceOptions"
        :key="source.value ?? 'all'"
        clickable dense
        :outline="selectedSource !== source.value"
        :color="selectedSource === source.value ? 'primary' : undefined"
        :text-color="selectedSource === source.value ? 'white' : undefined"
        @click="selectedSource = source.value"
      >
        {{ source.label }}
      </q-chip>
    </div>

    <div v-if="!loading && reviews.length === 0" class="text-center text-grey-7 q-pa-lg">
      Пока нет отзывов по выбранному фильтру.
    </div>

    <div v-else class="site-page reviews-wrapper relative-position">
      <q-btn
        round flat dense icon="chevron_left" color="primary"
        class="reviews-arrow reviews-arrow--left hide-on-sm-and-down"
        :disable="isAtStart"
        @click="scrollBy(-1)"
      />

      <div ref="scrollContainer" class="reviews-carousel" @scroll="checkScrollPosition">
        <div v-for="review in reviews" :key="review.id" class="review-slide">
          <q-card flat bordered square class="review-card full-height overflow-hidden column no-wrap">
            <q-img
              v-if="review.has_images && review.images[0]"
              :src="reviewImageSource(review.images[0])"
              class="review-image bg-grey-3 cursor-pointer"
              height="180px"
              fit="cover"
              role="button"
              tabindex="0"
              :aria-label="`Открыть фотографии отзыва ${review.author || 'гостя'}`"
              @click="openReviewImages(review)"
              @keydown.enter.prevent="openReviewImages(review)"
              @keydown.space.prevent="openReviewImages(review)"
              @error="failedPreviews.add(review.images[0].image || review.images[0].preview || '')"
            />
            <q-card-section class="review-content col column no-wrap q-pa-sm">
              <div class="row items-center justify-between q-mb-xs">
                <span class="text-subtitle2 text-weight-bold text-primary">{{ review.author || 'Гость' }}</span>
                <q-chip dense size="sm" outline>{{ review.source_display }}</q-chip>
              </div>
              <div class="review-text">
                <div class="text-body2 text-grey-8" style="font-style: italic; line-height: 1.4;">
                  "{{ review.text }}"
                </div>
                <div v-if="review.reply_text" class="text-caption text-grey-7 q-mt-sm q-pl-sm" style="border-left: 2px solid #ddd">
                  Ответ салона: {{ review.reply_text }}
                </div>
              </div>
              <div class="row items-center justify-between q-mt-sm">
                <div class="text-yellow-9">
                  <q-icon v-for="n in (review.rating || 0)" :key="n" name="star" size="16px" />
                </div>
                <a v-if="review.review_url" :href="review.review_url" target="_blank" class="text-caption text-grey-7">
                  Смотреть отзыв
                </a>
              </div>
            </q-card-section>
          </q-card>
        </div>
      </div>

      <q-btn
        round flat dense icon="chevron_right" color="primary"
        class="reviews-arrow reviews-arrow--right hide-on-sm-and-down"
        :disable="isAtEnd"
        @click="scrollBy(1)"
      />
    </div>
    <ImageLightbox v-model="lightboxOpen" :images="lightboxImages" />
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, onServerPrefetch, ref, watch } from 'vue';
import { fetchReviews, fetchSalons } from '@/api/endpoints';
import type { Review, ReviewSource, Salon } from '@/api/types';
import { REVIEW_SOURCE_LABELS } from '@/api/types';
import ImageLightbox from '@/components/ImageLightbox.vue';
import { getThumbnailUrl } from '@/utils/thumbnailUrl';
import { MEDIA_URL } from '@/config/urls';

const props = withDefaults(defineProps<{
  /** Если задан — компонент показывает отзывы только этого салона и прячет
   * фильтр по салону (для страницы конкретного салона). */
  salonId?: number | null;
  title?: string;
  withImagesOnly?: boolean;
}>(), {
  salonId: null,
  title: 'Отзывы и примеры работ',
  withImagesOnly: false,
});

const lockedSalonId = computed(() => props.salonId);

const reviews = ref<Review[]>([]);
const loading = ref(true);
const salons = ref<Salon[]>([]);
const failedPreviews = ref(new Set<string>());
const lightboxOpen = ref(false);
const lightboxImages = ref<{ src: string; alt: string }[]>([]);

function reviewImageSource(image: Review['images'][number]): string {
  const original = image.image || image.preview || '';
  return failedPreviews.value.has(original) ? original : getThumbnailUrl(original, 500, MEDIA_URL);
}

function openReviewImages(review: Review) {
  lightboxImages.value = review.images
    .map((image) => image.image || image.preview || '')
    .filter(Boolean)
    .map((src) => ({ src, alt: `Фото из отзыва ${review.author || 'гостя'}` }));
  lightboxOpen.value = lightboxImages.value.length > 0;
}

const selectedSalonId = ref<number | null>(props.salonId ?? null);
const selectedSource = ref<ReviewSource | null>(null);

const salonOptions = computed(() => [
  { value: null, label: 'Все салоны' },
  ...salons.value.map((s) => ({ value: s.id, label: s.name })),
]);

const sourceOptions = computed(() => [
  { value: null as ReviewSource | null, label: 'Все площадки' },
  ...(Object.entries(REVIEW_SOURCE_LABELS) as [string, string][])
    .filter(([value]) => value !== '4' && value !== '5')
    .map(([value, label]) => ({
      value: Number(value) as ReviewSource,
      label,
    })),
]);

async function load() {
  loading.value = true;
  try {
    const loaded = await fetchReviews({
      ...(selectedSalonId.value !== null ? { salon: selectedSalonId.value } : {}),
      ...(selectedSource.value !== null ? { source: selectedSource.value } : {}),
      ...(props.withImagesOnly ? { withImages: true } : {}),
    });
    reviews.value = props.withImagesOnly
      ? loaded.filter((review) => review.images.some((image) => !!(image.image || image.preview)))
      : loaded;
  } catch (err) {
    // Не даём сбою API (бэкенд недоступен и т.п.) уронить весь SSR-процесс —
    // см. аналогичный фикс в pages-store.ts. Просто остаёмся с пустым списком.
    console.error('Не удалось загрузить отзывы:', err);
    reviews.value = [];
  } finally {
    loading.value = false;
  }
}

// Список салонов для чипов-фильтров нужен, только если салон не зафиксирован
// пропсом — на странице салона фильтр по салону не показывается вовсе.
async function loadSalonsIfNeeded() {
  if (lockedSalonId.value) return;
  try {
    salons.value = await fetchSalons();
  } catch (err) {
    console.error('Не удалось загрузить список салонов для фильтра отзывов:', err);
    salons.value = [];
  }
}

const initialLoad = Promise.all([load(), loadSalonsIfNeeded()]);
onServerPrefetch(() => initialLoad);

watch([selectedSalonId, selectedSource], load);

// --- Карусель: горизонтальный скролл со стрелками (как было в HomePage) ---
const scrollContainer = ref<HTMLElement | null>(null);
const isAtStart = ref(true);
const isAtEnd = ref(false);

function scrollBy(direction: 1 | -1) {
  if (!scrollContainer.value) return;
  const firstSlide = scrollContainer.value.querySelector('.review-slide') as HTMLElement | null;
  if (!firstSlide) return;
  const slideWidth = firstSlide.offsetWidth + 16;
  scrollContainer.value.scrollBy({ left: slideWidth * direction, behavior: 'smooth' });
}

function checkScrollPosition() {
  if (!scrollContainer.value) return;
  const { scrollLeft, scrollWidth, clientWidth } = scrollContainer.value;
  isAtStart.value = scrollLeft <= 1;
  isAtEnd.value = scrollLeft + clientWidth >= scrollWidth - 1;
}

onMounted(() => {
  checkScrollPosition();
  window.addEventListener('resize', checkScrollPosition);
});
onBeforeUnmount(() => {
  window.removeEventListener('resize', checkScrollPosition);
});
</script>

<style scoped>
.reviews-carousel {
  display: flex;
  align-items: stretch;
  overflow-x: auto;
  scroll-behavior: smooth;
  scroll-snap-type: x mandatory;
  gap: 16px;
  padding: 8px 4px;
  scrollbar-width: none;
  -ms-overflow-style: none;
}
.reviews-carousel::-webkit-scrollbar {
  display: none;
}
.review-card {
  max-height: 400px;
}
.review-image {
  flex-shrink: 0;
}
.review-content {
  min-height: 0;
}
.review-text {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  scrollbar-width: thin;
}
.review-slide {
  flex: 0 0 100%;
  scroll-snap-align: start;
}
@media (min-width: 600px) {
  .review-slide { flex: 0 0 calc(50% - 8px); }
}
@media (min-width: 1024px) {
  .review-slide { flex: 0 0 calc(25% - 12px); }
}
.reviews-arrow {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  z-index: 10;
  background: white !important;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15) !important;
}
.reviews-arrow--left { left: -20px; }
.reviews-arrow--right { right: -20px; }
</style>
