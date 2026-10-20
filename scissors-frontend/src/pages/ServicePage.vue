<template>
  <q-page v-if="category" class="site-page q-px-md q-py-xl">

    <!-- Хлебные крошки -->
    <div class="text-caption text-grey-7 q-mb-md">
      <router-link to="/" class="text-primary" style="text-decoration: none;">Главная</router-link>
      <span class="q-mx-xs">/</span>
      <router-link to="/price-list" class="text-primary" style="text-decoration: none;">Услуги и цены</router-link>
      <span class="q-mx-xs">/</span>
      <span class="text-grey-9">{{ category.title }}</span>
    </div>

    <h1 class="text-h4 text-weight-bold q-mb-sm">{{ category.title }}</h1>

    <!-- Важное уведомление (Стандарт аудита) -->
    <q-banner rounded class="bg-primary text-white q-mb-lg">
      <template v-slot:avatar>
        <q-icon name="info" color="white" />
      </template>
      {{ category.intro }}
    </q-banner>

    <!-- Предупреждение, если категория целиком недоступна в выбранном салоне -->
    <q-banner
      v-if="isCategoryUnavailable && fallbackCategorySalon"
      rounded
      class="bg-red-1 text-red-9 q-mb-lg"
    >
      <template v-slot:avatar>
        <q-icon name="warning" color="red-9" />
      </template>
      Эта категория услуг временно недоступна в салоне «{{ getSalonName(salonStore.selectedSalonSlug) }}».
      Ниже отображены актуальные цены салона «{{ getSalonName(fallbackCategorySalon) }}».
    </q-banner>

    <!-- Кнопки выбора салона -->
    <div class="row q-gutter-sm q-mb-lg">
      <q-btn
        v-for="salon in salonStore.allSalons"
        :key="salon.slug"
        :label="salon.shortName"
        :color="salonStore.selectedSalonSlug === salon.slug ? 'primary' : 'grey-3'"
        :text-color="salonStore.selectedSalonSlug === salon.slug ? 'white' : 'dark'"
        @click="salonStore.setSalon(salon.slug)"
        class="no-uppercase"
      />
    </div>

    <!-- Аккордеон с услугами -->
    <q-list bordered separator class="rounded-borders bg-white">
      <q-expansion-item
        v-for="item in category.items"
        :key="item.name"
        :label="item.name"
        header-class="text-subtitle1 text-weight-bold"
        expand-separator
      >
        <q-card>
          <q-card-section>
            <!-- Описание (рендерится всегда, отлично для SEO при SSR) -->
            <p class="text-body2 text-grey-8 q-mb-md">{{ item.description }}</p>

            <div v-if="item.duration" class="text-caption text-grey-7 q-mb-md">
              <q-icon name="schedule" size="16px" class="q-mr-xs" />
              {{ item.duration }}
            </div>

            <!-- Цены (рендерим только на клиенте, чтобы избежать гидратационных ошибок из-за localStorage) -->
            <div v-if="isClient" class="row q-col-gutter-md q-pt-sm" style="border-top: 1px solid #eee;">
              <template v-if="getItemPricing(item).prices">

                <!-- Бейдж-предупреждение, если для этой конкретной услуги сработал фолбэк -->
                <div v-if="getItemPricing(item).isFallback" class="col-12 q-mb-sm">
                  <q-badge color="orange" text-color="black" class="q-py-xs q-px-sm text-weight-medium">
                    <q-icon name="info" size="xs" class="q-mr-xs" />
                    В салоне «{{ getSalonName(salonStore.selectedSalonSlug) }}» не предоставляется. Показаны цены: {{ getSalonName(getItemPricing(item).fallbackSalon) }}
                  </q-badge>
                </div>

                <div class="col-12 col-sm-4 text-center q-pa-sm">
                  <div class="text-caption text-grey-7">Универсал / Модельер</div>
                  <div class="text-weight-bold text-primary" style="white-space: pre-line; font-size: 1.1em;">
                    {{ getItemPricing(item).prices.universal }} ₽
                  </div>
                </div>
                <div class="col-12 col-sm-4 text-center q-pa-sm">
                  <div class="text-caption text-grey-7">Топ-стилист</div>
                  <div class="text-weight-bold text-primary" style="white-space: pre-line; font-size: 1.1em;">
                    {{ getItemPricing(item).prices.topStylist }} ₽
                  </div>
                </div>
                <div class="col-12 col-sm-4 text-center q-pa-sm">
                  <div class="text-caption text-grey-7">Арт-директор</div>
                  <div class="text-weight-bold text-primary" style="white-space: pre-line; font-size: 1.1em;">
                    {{ getItemPricing(item).prices.artDirector }} ₽
                  </div>
                </div>
              </template>
              <div v-else class="col-12 text-center text-grey-6 q-pa-md">
                Стоимость уточняется у администратора
              </div>
            </div>
          </q-card-section>
        </q-card>
      </q-expansion-item>
    </q-list>
  </q-page>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import { useMeta } from 'quasar';
import { serviceCategories } from '@/data/services';
import { useSalonStore } from '@/stores/salon';
import type { SalonSlug } from '@/stores/salon';
import { SITE_URL } from '@/config/urls';

const route = useRoute();
const salonStore = useSalonStore();

// Флаг для предотвращения гидратационных ошибок (SSR vs Client localStorage)
const isClient = ref(false);

onMounted(() => {
  isClient.value = true;
});

const category = computed(() =>
  serviceCategories.find((c) => c.slug === route.params.slug)
);

// Хелпер для получения читаемого имени салона по slug
const getSalonName = (slug: string | null | undefined) => {
  if (!slug) return '';
  return salonStore.allSalons.find(s => s.slug === slug)?.shortName || slug;
};

// Проверка: доступна ли вся категория в выбранном салоне
const isCategoryUnavailable = computed(() => {
  if (!category.value || !salonStore.selectedSalonSlug) return false;
  return !category.value.availableIn.includes(salonStore.selectedSalonSlug);
});

// Поиск запасного салона для всей категории, если основная недоступна
const fallbackCategorySalon = computed(() => {
  if (!category.value || !salonStore.selectedSalonSlug) return null;
  return category.value.availableIn.find(s => s !== salonStore.selectedSalonSlug) || null;
});

// Главная логика: получение цен для КОНКРЕТНОЙ услуги с учетом фолбэка
const getItemPricing = (item: any) => {
  const selected = salonStore.selectedSalonSlug;
  if (!selected || !category.value) {
    return { prices: null, isFallback: false, fallbackSalon: null };
  }

  // 1. Если услуга есть в выбранном салоне — возвращаем её цены
  if (item.availableIn.includes(selected)) {
    return { prices: item.prices[selected], isFallback: false, fallbackSalon: null };
  }

  // 2. Если нет — ищем первый доступный салон для этой услуги (фолбэк)
  const fallbackSlug = item.availableIn.find(slug => slug !== selected) || null;
  if (fallbackSlug && item.prices[fallbackSlug]) {
    return { prices: item.prices[fallbackSlug], isFallback: true, fallbackSalon: fallbackSlug };
  }

  // 3. Если цен нет нигде
  return { prices: null, isFallback: false, fallbackSalon: null };
};

// SEO Meta
useMeta(() => ({
  title: category.value ? `${category.value.title} — Scissors Studio` : 'Scissors Studio',
  meta: {
    description: {
      name: 'description',
      content: category.value?.intro || 'Scissors Studio'
    }
  },
  link: category.value ? {
    canonical: { rel: 'canonical', href: `${SITE_URL}/services/${category.value.slug}` }
  } : undefined
}));
</script>

<style scoped>
.rounded-borders {
  border-radius: 12px;
  overflow: hidden;
}
</style>
