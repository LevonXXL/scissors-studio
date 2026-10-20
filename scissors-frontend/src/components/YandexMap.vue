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
// поэтому весь этот компонент должен рендериться внутри <q-no-ssr> (см. SalonsPage.vue).
interface YMapInstance {
  addChild: (child: unknown) => void;
}

declare global {
  interface Window {
    ymaps3?: {
      ready: Promise<void>;
      YMap: new (element: HTMLElement, opts: Record<string, unknown>) => YMapInstance;
      YMapDefaultSchemeLayer: new (opts?: Record<string, unknown>) => unknown;
      YMapDefaultFeaturesLayer: new (opts?: Record<string, unknown>) => unknown;
      YMapMarker: new (opts: Record<string, unknown>, element: HTMLElement) => unknown;
    };
  }
}

function loadYmapsScript(apiKey: string): Promise<void> {
  if (window.ymaps3) return window.ymaps3.ready;

  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = `https://api-maps.yandex.ru/v3/?apikey=${apiKey}&lang=ru_RU`;
    script.onload = () => {
      window.ymaps3!.ready.then(resolve).catch(reject);
    };
    script.onerror = reject;
    document.head.appendChild(script);
  });
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
  } catch {
    emit('unavailable');
    return;
  }
  const ymaps3 = window.ymaps3!;

  const [firstLat, firstLon] = props.salons[0]!.coordinates;

  const map = new ymaps3.YMap(mapEl.value, {
    location: { center: [firstLon, firstLat], zoom: props.zoom },
  });
  map.addChild(new ymaps3.YMapDefaultSchemeLayer());
  map.addChild(new ymaps3.YMapDefaultFeaturesLayer());

  for (const salon of props.salons) {
    const [lat, lon] = salon.coordinates;
    const markerEl = document.createElement('div');
    markerEl.title = salon.name;
    markerEl.style.cssText =
      'width:16px;height:16px;border-radius:50%;background:#8c2b12;border:2px solid #fff';
    map.addChild(new ymaps3.YMapMarker({ coordinates: [lon, lat] }, markerEl));
  }
});
</script>
