<template>
  <div ref="mapEl" style="width: 100%; height: 400px" />
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import type { Salon } from '@/api/types';

const props = withDefaults(defineProps<{ salons: Salon[]; zoom?: number }>(), { zoom: 11 });
const emit = defineEmits<{ unavailable: [] }>();
const mapEl = ref<HTMLElement | null>(null);

// Ymaps API грузится динамически, только на клиенте — на сервере window нет,
// поэтому весь этот компонент должен рендериться внутри <q-no-ssr> (см. SalonPage.vue).
declare global {
  interface Window {
    ymaps?: {
      ready: () => PromiseLike<unknown>;
      Map: new (element: HTMLElement, opts: { center: number[]; zoom: number }) => {
        geoObjects: { add: (object: unknown) => void };
      };
      Placemark: new (coordinates: number[], properties: { hintContent: string }) => unknown;
    };
  }
}

let mapsReady: Promise<void> | null = null;

function loadYmapsScript(apiKey: string): Promise<void> {
  if (window.ymaps) return Promise.resolve(window.ymaps.ready()).then(() => undefined);
  if (mapsReady) return mapsReady;

  const promise = new Promise<void>((resolve, reject) => {
    const script = document.createElement('script');
    script.src = `https://api-maps.yandex.ru/2.1/?apikey=${encodeURIComponent(apiKey)}&lang=ru_RU&csp=true`;
    script.onload = () => {
      if (!window.ymaps) {
        reject(new Error('Yandex Maps API did not initialize'));
        return;
      }
      Promise.resolve(window.ymaps.ready()).then(() => resolve(), reject);
    };
    script.onerror = () => reject(new Error('Yandex Maps API script failed to load'));
    document.head.appendChild(script);
  });
  const ready = promise.catch((error: unknown) => {
    mapsReady = null;
    throw error;
  });
  mapsReady = ready;
  return ready;
}

onMounted(async () => {
  const apiKey = import.meta.env.VITE_YANDEX_MAPS_API_KEY as string;
  if (!apiKey) {
    console.warn('VITE_YANDEX_MAPS_API_KEY не задан — карта не будет показана.');
    emit('unavailable');
    return;
  }
  if (!mapEl.value || props.salons.length === 0) return;

  try {
    await loadYmapsScript(apiKey);
    const ymaps = window.ymaps!;
    const map = new ymaps.Map(mapEl.value, {
      center: props.salons[0]!.coordinates,
      zoom: props.zoom,
    });

    for (const salon of props.salons) {
      map.geoObjects.add(new ymaps.Placemark(salon.coordinates, { hintContent: salon.name }));
    }
  } catch {
    emit('unavailable');
  }
});
</script>
