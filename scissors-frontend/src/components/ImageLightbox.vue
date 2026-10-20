<template>
  <q-dialog :model-value="modelValue" maximized @update:model-value="emit('update:modelValue', $event)">
    <q-card class="lightbox bg-black text-white column no-wrap" @keydown.left.prevent="move(-1)" @keydown.right.prevent="move(1)">
      <div class="row items-center justify-between q-pa-sm">
        <span class="text-caption">{{ images.length ? `${currentIndex + 1} / ${images.length}` : '' }}</span>
        <q-btn flat round icon="close" aria-label="Закрыть фото" @click="emit('update:modelValue', false)" />
      </div>
      <div class="lightbox-stage col row items-center justify-center no-wrap">
        <q-btn v-if="images.length > 1" flat round icon="chevron_left" aria-label="Предыдущее фото" @click="move(-1)" />
        <img v-if="currentImage" :src="currentImage.src" :alt="currentImage.alt || ''" class="lightbox-image col" />
        <q-btn v-if="images.length > 1" flat round icon="chevron_right" aria-label="Следующее фото" @click="move(1)" />
      </div>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';

export interface LightboxImage { src: string; alt?: string }

const props = defineProps<{
  modelValue: boolean;
  images: LightboxImage[];
  initialIndex?: number;
}>();
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>();
const currentIndex = ref(0);
const currentImage = computed(() => props.images[currentIndex.value]);

watch(() => [props.modelValue, props.initialIndex, props.images.length] as const, () => {
  if (props.modelValue) currentIndex.value = Math.min(Math.max(props.initialIndex ?? 0, 0), props.images.length - 1);
});

function move(direction: number) {
  if (!props.images.length) return;
  currentIndex.value = (currentIndex.value + direction + props.images.length) % props.images.length;
}
</script>

<style scoped>
.lightbox { width: 100vw; height: 100dvh; }
.lightbox-stage { min-height: 0; }
.lightbox-image { min-width: 0; max-width: calc(100vw - 112px); max-height: calc(100dvh - 72px); object-fit: contain; }
</style>
