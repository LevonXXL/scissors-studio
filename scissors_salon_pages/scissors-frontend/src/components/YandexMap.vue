<template>
  <div ref="mapEl" style="width: 100%; height: 400px" />
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import type { Salon } from '@/api/types';

const props = withDefaults(defineProps<{
  salons: Salon[];
  /** 11 — обзор города (несколько салонов), 16 — конкретное здание. */
  zoom?: number;
}>(), { zoom: 11 });

// Карта — улучшение поверх текста: адрес, ссылки и JSON-LD на странице уже
// есть без неё. Если ключа нет или скрипт Яндекса не загрузился (блокировка,
// сеть) — сообщаем родителю, он покажет запасной вариант.
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
  } catch (err) {
    console.warn('Не удалось загрузить Яндекс.Карты:', err);
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
      'width:16px;height:16px;border-radius:50%;background:#C5291C;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.4)';
    map.addChild(new ymaps3.YMapMarker({ coordinates: [lon, lat] }, markerEl));
  }
});
</script>
