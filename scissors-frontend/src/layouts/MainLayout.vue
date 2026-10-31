<template>
  <q-layout view="lHh Lpr lFf" class="site-layout">
    <q-header elevated class="site-header">
      <q-toolbar class="q-py-sm">
        <q-btn
          flat dense round icon="menu" aria-label="Меню"
          @click="drawerOpen = !drawerOpen"
        />

        <router-link v-if="!drawerOpen" to="/" class="q-ml-sm" style="text-decoration: none; line-height: 1">
          <picture>
            <source
              media="(max-width: 480px)"
              :srcset="publicAssetUrl('/logo/s-256x256.png')"
            />
            <img
              :src="publicAssetUrl('/logo/scissors-160x47.png')"
              alt="Scissors by Stets"
              class="header-logo"
            />
          </picture>
        </router-link>

        <q-space />

        <q-btn flat dense round icon="search" aria-label="Открыть поиск" class="q-mr-sm">
          <q-menu v-model="searchMenuOpen" anchor="bottom right" self="top right" :offset="[0, 8]"
            class="header-search-menu bg-white text-dark" @show="headerSearchError = false">
            <form class="header-search-form" role="search" @submit.prevent="submitHeaderSearch">
              <q-input v-model="headerSearchQuery" outlined dense autofocus type="search" maxlength="200"
                label="Поиск по сайту" class="header-search-form__input"
                :error="headerSearchError" error-message="Введите не менее 3 символов"
                @update:model-value="headerSearchError = false" />
              <q-btn type="submit" unelevated no-caps color="primary" icon="search" label="Искать" />
            </form>
          </q-menu>
        </q-btn>

<!--        <q-btn v-if="auth.authenticated" flat dense round icon="account_circle" aria-label="Профиль" to="/login" class="q-mr-sm">-->
<!--          <q-tooltip>Профиль</q-tooltip>-->
<!--        </q-btn>-->
<!--        <template v-else>-->
<!--          <q-btn flat no-caps icon="account_circle" label="Войти" to="/login" class="gt-xs q-mr-sm" />-->
<!--          <q-btn flat dense round icon="account_circle" aria-label="Войти" to="/login" class="lt-sm q-mr-sm" />-->
<!--        </template>-->

        <div class="gt-sm q-mr-md">
          <q-btn flat dense round icon="support_agent" aria-label="Обратная связь" @click="consultationOpen = true">
            <q-tooltip>Обратная связь</q-tooltip>
          </q-btn>
        </div>

        <div class="gt-sm text-caption text-right q-mr-md">
          <div v-for="salon in salons" :key="salon.city">
            <a :href="`tel:${salon.phoneRaw}`" style="color: inherit; text-decoration: none">{{ salon.phone }}</a>
            <span class="site-header__secondary"> — {{ salon.shortName }}</span>
          </div>
        </div>

        <q-btn
          unelevated no-caps label="Онлайн-запись"
          :href="YCLIENTS_NETWORK_BOOKING_URL" target="_blank" rel="noopener noreferrer"
          class="site-header__booking"
        />
      </q-toolbar>
    </q-header>

    <!-- Единое боковое меню — стандартный паттерн Quasar-шаблона:
         show-if-above делает его постоянной панелью на широких экранах
         и оверлеем по клику на гамбургер на узких. Раньше здесь были
         раздельные q-tabs (десктоп) + отдельный список в q-drawer
         (мобильный) с дублированием пунктов — теперь один список. -->
    <q-drawer v-model="drawerOpen" show-if-above bordered side="left">

      <q-list>
        <q-item-label header>
          <router-link
            to="/"
            class="q-ml-sm"
            style="display: block; text-decoration: none; line-height: 1"
          >
            <img
              :src="publicAssetUrl('/logo/512-rounded.png')"
              alt="Scissors by Stets"
              style="display: block; width: 100%; max-width: 100%; height: auto; border-radius: 6px;"
            />
          </router-link>
        </q-item-label>

        <q-item clickable @click="consultationOpen = true">
          <q-item-section avatar><q-icon name="support_agent" /></q-item-section>
          <q-item-section>Обратная связь</q-item-section>
        </q-item>

        <q-item v-for="salon in salons" :key="salon.city" clickable :href="`tel:${salon.phoneRaw}`">
          <q-item-section avatar><q-icon name="phone" /></q-item-section>
          <q-item-section>
            <q-item-label>{{ salon.phone }}</q-item-label>
            <q-item-label caption>{{ salon.shortName }}</q-item-label>
          </q-item-section>
        </q-item>

        <q-separator class="q-my-sm" />

        <q-item clickable to="/search" v-close-popup>
          <q-item-section avatar><q-icon name="search" /></q-item-section>
          <q-item-section>Поиск</q-item-section>
        </q-item>

        <q-expansion-item label="Услуги и цены" icon="content_cut" default-opened>
          <q-item clickable to="/uslugi" v-close-popup>
            <q-item-section>Все услуги и цены</q-item-section>
          </q-item>
          <q-item
            v-for="item in servicesMenu" :key="item.href"
            clickable :to="item.href" v-close-popup
          >
            <q-item-section>{{ item.label }}</q-item-section>
          </q-item>
        </q-expansion-item>

        <q-item clickable to="/team" v-close-popup>
          <q-item-section avatar><q-icon name="groups" /></q-item-section>
          <q-item-section>Команда и портфолио</q-item-section>
        </q-item>

        <q-expansion-item label="Салоны" icon="place">
          <q-item clickable to="/salons" v-close-popup><q-item-section>Все салоны</q-item-section></q-item>
          <q-item clickable to="/salons/scissors-krasnye-vorota" v-close-popup><q-item-section>Москва</q-item-section></q-item>
          <q-item clickable to="/salons/scissors-zelenograd-17mkr" v-close-popup><q-item-section>Зеленоград</q-item-section></q-item>
        </q-expansion-item>

        <q-item clickable to="/about" v-close-popup>
          <q-item-section avatar><q-icon name="info" /></q-item-section>
          <q-item-section>О нас</q-item-section>
        </q-item>

        <q-item clickable to="/login" v-close-popup>
          <q-item-section avatar><q-icon name="person" /></q-item-section>
          <q-item-section>{{ auth.authenticated ? 'Профиль' : 'Войти' }}</q-item-section>
        </q-item>
      </q-list>
    </q-drawer>

    <q-page-container class="site-content">
      <InstallAppBanner />
      <router-view />
      <footer class="site-footer q-pt-md">
        <div class="site-page q-px-md q-pb-lg">
          <q-separator class="q-mb-md" />

          <div class="row items-center q-col-gutter-md text-caption site-footer__content">
            <div class="col-auto">ⓒ SCISSORS, {{ currentYear }} / Все права защищены</div>
            <div class="col-auto row items-center q-gutter-sm">
              <a
                v-for="link in messengerLinks"
                :key="link.label"
                :href="link.href"
                :aria-label="link.label"
                :title="link.label"
                target="_blank"
                rel="noopener noreferrer"
                class="site-footer__messenger"
              >
                <img
                  :src="publicAssetUrl(link.icon)"
                  :alt="link.label"
                  width="24"
                  height="24"
                  loading="lazy"
                />
              </a>
              <a v-for="link in reviewPlatforms" :key="link.href" :href="link.href" target="_blank" rel="noopener noreferrer" style="color: inherit">
                {{ link.label }}
              </a>
              <router-link to="/privacy" style="color: inherit">Политика обработки персональных данных</router-link>
              <q-btn flat dense no-caps label="Настройки cookies" @click="cookieStore.openSettings()" />
            </div>
          </div>
        </div>
      </footer>
    </q-page-container>

    <ConsultationDialog v-model="consultationOpen" />
    <CookieSettingsDialog />

    <section v-if="cookieStore.showBanner" class="cookie-banner shadow-4" role="region" aria-label="Настройки cookies">
      <div class="cookie-banner__inner">
        <div class="cookie-banner__text">
          <strong>Мы используем cookies</strong>
          <p class="q-mb-none">
            Необходимые данные нужны для входа в профиль. Яндекс Метрика включится только с вашего согласия.
            <router-link to="/privacy">Политика обработки персональных данных</router-link>
          </p>
        </div>
        <div class="cookie-banner__actions">
          <q-btn flat no-caps label="Только необходимые" @click="cookieStore.acceptNecessaryOnly()" />
          <q-btn outline no-caps label="Настроить" @click="cookieStore.openSettings()" />
          <q-btn unelevated no-caps color="primary" label="Все" @click="cookieStore.acceptAll()" />
        </div>
      </div>
    </section>
  </q-layout>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, onServerPrefetch, ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { salons } from '@/data/salons';
import ConsultationDialog from '@/components/ConsultationDialog.vue';
import CookieSettingsDialog from '@/components/CookieSettingsDialog.vue';
import InstallAppBanner from '@/components/InstallAppBanner.vue';
import { messengerLinks } from '@/data/contacts';
import { useAuthStore } from '@/stores/auth';
import { useCookieStore } from '@/stores/cookies';
import { useServiceCatalogStore } from '@/stores/serviceCatalog';
import { useSalonStore } from '@/stores/salon';
import { publicAssetUrl } from '@/config/urls';
import { YCLIENTS_NETWORK_BOOKING_URL } from '@/utils/yclientsBooking';

const auth = useAuthStore();
const cookieStore = useCookieStore();
const salonStore = useSalonStore();
const router = useRouter();
let removeRouteHook: (() => void) | undefined;

onMounted(() => {
  salonStore.restoreSelection();
  void auth.restore();
  cookieStore.hit(router.currentRoute.value.path);
  cookieStore.loadFromStorage();
  removeRouteHook = router.afterEach((to) => cookieStore.hit(to.path));
});
onUnmounted(() => removeRouteHook?.());

const drawerOpen = ref(false);
const currentYear = new Date().getFullYear();
const consultationOpen = ref(false);
const searchMenuOpen = ref(false);
const headerSearchQuery = ref('');
const headerSearchError = ref(false);

function submitHeaderSearch() {
  const query = headerSearchQuery.value.trim();
  headerSearchError.value = query.length < 3;
  if (headerSearchError.value) return;

  searchMenuOpen.value = false;
  void router.push({ path: '/search', query: { query } });
}

const serviceCatalog = useServiceCatalogStore();

const servicesMenu = computed(() =>
  serviceCatalog.rootCategories.map((item) => ({
    href: `/${item.url_path}`,
    label: item.title,
  })),
);

async function ensureServicesMenu() {
  if (!serviceCatalog.rootLoaded) {
    await serviceCatalog.loadRootCategories();
  }
}

onServerPrefetch(ensureServicesMenu);

// const servicesMenu = ref<{ href: string; label: string }[]>([]);
// const catalogueLoad = fetchCatalogueCategories().then((items) => {
//   servicesMenu.value = items.map((item) => ({ href: `/${item.url_path}`, label: item.title }));
// });
// onServerPrefetch(() => catalogueLoad);

const reviewPlatforms = [
  { label: 'Zoon', href: 'https://zoon.ru/msk/beauty/network/scissors_studio_studii_krasoty/' },
  { label: 'Яндекс Карты', href: 'https://yandex.ru/maps/org/scissors_studio/93145938050/?ll=37.648052%2C55.766041&z=10' },
  { label: '2GIS', href: 'https://2gis.ru/moscow/branches/70000001018013076' },
];
</script>

<style scoped>
.site-layout {
  display: flex;
  flex-direction: column;
}

.site-content {
  flex: 1 0 auto;
}

.site-header,
.site-footer {
  background: #8c2b12;
  color: #ffffff;
}

.site-header__secondary {
  color: rgba(255, 255, 255, 0.72);
}

.site-header__booking {
  background: transparent !important;
  color: #ffffff !important;
  box-shadow: inset 0 0 0 1px #ffffff;
}

.site-header__booking:hover {
  background: #a54127 !important;
}

:global(.header-search-menu) {
  width: 380px;
  max-width: calc(100vw - 24px);
  border-radius: 8px;
}

.header-search-form {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 16px;
}

.header-search-form__input {
  flex: 1;
  min-width: 0;
}

.site-footer {
  flex: 0 0 auto;
}

.site-footer .q-separator {
  background: rgba(255, 255, 255, 0.4);
}

.site-footer__content {
  color: rgba(255, 255, 255, 0.72);
}

.site-footer__content a,
.site-footer__content .q-btn {
  color: #ffffff !important;
}

.cookie-banner {
  position: fixed;
  z-index: 5000;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 16px;
  background: var(--sc-bg);
  border-top: 2px solid var(--sc-accent);
}

.cookie-banner__inner {
  display: flex;
  align-items: center;
  gap: 24px;
  max-width: 1200px;
  margin: 0 auto;
}

.cookie-banner__text {
  flex: 1;
  min-width: 0;
  line-height: 1.5;
}

.cookie-banner__text p {
  font-size: 13px;
}

.cookie-banner__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

@media (max-width: 700px) {
  .cookie-banner__inner {
    display: block;
  }

  .cookie-banner__actions {
    margin-top: 12px;
  }
}

.header-logo {
  display: block;
  width: 160px;
  height: auto;
  border-radius: 6px;
}

@media (max-width: 480px) {
  .header-logo {
    width: 48px;
    height: 48px;
    object-fit: contain;
  }
}
</style>
