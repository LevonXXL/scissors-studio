<template>
  <div class="gallery relative-position">
    <q-btn v-if="images.length > 1" round flat dense icon="chevron_left" color="primary"
      class="gallery-arrow gallery-arrow--left" :disable="isAtStart" aria-label="Предыдущее фото"
      @click="scrollBy(-1)" />
    <div ref="scrollContainer" class="gallery-track" @scroll="checkScrollPosition">
      <button v-for="(image, index) in images" :key="image.id" type="button" class="gallery-slide"
        :aria-label="`Открыть фото ${index + 1}`" @click="open(index)">
        <q-img :src="previewSource(image)" :alt="image.alt" :ratio="ratio" fit="cover"
          class="rounded-borders" @error="failedPreviews.add(image.src)" />
      </button>
    </div>
    <q-btn v-if="images.length > 1" round flat dense icon="chevron_right" color="primary"
      class="gallery-arrow gallery-arrow--right" :disable="isAtEnd" aria-label="Следующее фото"
      @click="scrollBy(1)" />
    <ImageLightbox v-model="lightboxOpen" :images="originals" :initial-index="selectedIndex" />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import ImageLightbox from '@/components/ImageLightbox.vue';
import { getThumbnailUrl } from '@/utils/thumbnailUrl';
import { MEDIA_URL } from '@/config/urls';

export interface GalleryImage { id: number | string; src: string; alt: string }

const props = withDefaults(defineProps<{
  images: GalleryImage[];
  previewWidth?: number;
  ratio?: number;
}>(), { previewWidth: 800, ratio: 1.5 });

const failedPreviews = ref(new Set<string>());
const scrollContainer = ref<HTMLElement | null>(null);
const isAtStart = ref(true);
const isAtEnd = ref(false);
const lightboxOpen = ref(false);
const selectedIndex = ref(0);
const originals = computed(() => props.images.map((image) => ({ src: image.src, alt: image.alt })));

function previewSource(image: GalleryImage) {
  return failedPreviews.value.has(image.src)
    ? image.src
    : getThumbnailUrl(image.src, props.previewWidth, MEDIA_URL);
}

function open(index: number) {
  selectedIndex.value = index;
  lightboxOpen.value = true;
}

function scrollBy(direction: 1 | -1) {
  const container = scrollContainer.value;
  const slide = container?.querySelector('.gallery-slide') as HTMLElement | null;
  if (!container || !slide) return;
  const gap = parseFloat(getComputedStyle(container).columnGap) || 0;
  container.scrollBy({ left: direction * (slide.offsetWidth + gap), behavior: 'smooth' });
}

function checkScrollPosition() {
  const container = scrollContainer.value;
  if (!container) return;
  isAtStart.value = container.scrollLeft <= 1;
  isAtEnd.value = container.scrollLeft + container.clientWidth >= container.scrollWidth - 1;
}

watch(() => props.images, async () => {
  failedPreviews.value.clear();
  await nextTick();
  scrollContainer.value?.scrollTo({ left: 0 });
  checkScrollPosition();
});
onMounted(() => {
  checkScrollPosition();
  window.addEventListener('resize', checkScrollPosition);
});
onBeforeUnmount(() => window.removeEventListener('resize', checkScrollPosition));
</script>

<style scoped>
.gallery-track { display: flex; gap: 16px; overflow-x: auto; scroll-snap-type: x mandatory; scrollbar-width: none; padding: 4px; }
.gallery-track::-webkit-scrollbar { display: none; }
.gallery-slide { flex: 0 0 calc(100% - 8px); padding: 0; border: 0; background: transparent; cursor: pointer; scroll-snap-align: start; }
.gallery-slide:focus-visible { outline: 3px solid var(--q-primary); outline-offset: 2px; }
@media (min-width: 600px) { .gallery-slide { flex-basis: calc(50% - 8px); } }
@media (min-width: 1024px) { .gallery-slide { flex-basis: calc(33.333% - 11px); } }
.gallery-arrow { position: absolute; top: 50%; transform: translateY(-50%); z-index: 2; background: white !important; box-shadow: 0 2px 8px rgba(0,0,0,.15) !important; }
.gallery-arrow--left { left: -16px; }
.gallery-arrow--right { right: -16px; }
</style>
