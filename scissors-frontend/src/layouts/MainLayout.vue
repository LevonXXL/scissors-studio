<template>
  <q-layout view="lHh Lpr lFf">
    <q-header elevated class="bg-white text-dark">
      <q-toolbar class="q-py-sm">
        <q-btn
          flat dense round icon="menu" aria-label="Меню"
          @click="drawerOpen = !drawerOpen"
        />

        <router-link v-if="!drawerOpen" to="/" class="q-ml-sm" style="text-decoration: none; line-height: 1">
          <img
            src="/logo/scissors-160x47.png"
            alt="Scissors by Stets"
            style="display: block; width: 160px; height: auto; border-radius: 6px;"
          />
        </router-link>

        <q-space />

        <q-btn flat no-caps :label="auth.authenticated ? 'Мой вход' : 'Войти'" to="/login" class="q-mr-sm" />

        <!-- Иконки связи прямо в хедере (единым набором, не по салону —
             так на реальном сайте: Telegram/WhatsApp/MAX ссылаются на
             московский номер, отдельного плавающего виджета нет вообще) -->
        <div class="gt-sm row items-center q-gutter-xs q-mr-md">
          <q-btn v-for="link in messengerLinks" :key="link.label" flat dense round :icon="link.icon" :href="link.href" target="_blank" rel="noopener noreferrer" :aria-label="link.label" />
          <q-btn flat dense round icon="support_agent" aria-label="Обратная связь" @click="consultationOpen = true">
            <q-tooltip>Обратная связь</q-tooltip>
          </q-btn>
        </div>

        <div class="gt-sm text-caption text-right q-mr-md">
          <div v-for="salon in salons" :key="salon.city">
            <a :href="`tel:${salon.phoneRaw}`" style="color: inherit; text-decoration: none">{{ salon.phone }}</a>
            <span class="text-grey-7"> — {{ salon.shortName }}</span>
          </div>
        </div>

        <q-btn
          unelevated no-caps label="Онлайн-запись"
          href="https://n84109.yclients.com/select-city?o="
          target="_blank"
          :style="{ background: 'var(--sc-accent)', color: '#fff' }"
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
              src="/logo/scissors-512x512.png"
              alt="Scissors by Stets"
              style="display: block; width: 100%; max-width: 100%; height: auto; border-radius: 6px;"
            />
          </router-link>
        </q-item-label>

        <q-expansion-item label="Услуги и цены" icon="content_cut" default-opened>
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
          <q-item clickable to="/salons/moscow" v-close-popup><q-item-section>Москва</q-item-section></q-item>
          <q-item clickable to="/salons/zelenograd" v-close-popup><q-item-section>Зеленоград</q-item-section></q-item>
        </q-expansion-item>

        <q-item clickable to="/about" v-close-popup>
          <q-item-section avatar><q-icon name="info" /></q-item-section>
          <q-item-section>О нас</q-item-section>
        </q-item>

        <q-item clickable to="/login" v-close-popup>
          <q-item-section avatar><q-icon name="person" /></q-item-section>
          <q-item-section>{{ auth.authenticated ? 'Мой вход' : 'Войти' }}</q-item-section>
        </q-item>

        <q-separator class="q-my-sm" />
        <q-item-label header>Связаться</q-item-label>

        <q-item v-for="salon in salons" :key="salon.city" clickable :href="`tel:${salon.phoneRaw}`">
          <q-item-section avatar><q-icon name="phone" /></q-item-section>
          <q-item-section>
            <q-item-label>{{ salon.phone }}</q-item-label>
            <q-item-label caption>{{ salon.shortName }}</q-item-label>
          </q-item-section>
        </q-item>

        <q-item clickable @click="consultationOpen = true">
          <q-item-section avatar><q-icon name="support_agent" /></q-item-section>
          <q-item-section>Обратная связь</q-item-section>
        </q-item>

        <q-item class="lt-md">
          <q-item-section>
            <div class="row q-gutter-xs">
              <q-btn v-for="link in messengerLinks" :key="link.label" flat dense round :icon="link.icon" :href="link.href" target="_blank" rel="noopener noreferrer" :aria-label="link.label" />
            </div>
          </q-item-section>
        </q-item>
      </q-list>
    </q-drawer>

    <q-page-container>
      <InstallAppBanner />
      <router-view />
    </q-page-container>

    <q-footer class="bg-white text-dark q-pt-xl">
      <div class="site-page q-px-md q-pb-lg">
        <div class="row items-center q-col-gutter-md">
          <div class="col-auto">
            <q-btn outline no-caps label="Приобрести подарочную карту" :style="{ color: 'var(--sc-accent)', borderColor: 'var(--sc-accent)' }" @click="giftCardOpen = true" />
          </div>
          <div class="col-auto row items-center q-col-gutter-sm text-caption text-grey-8">
            <a v-for="link in reviewPlatforms" :key="link.href" :href="link.href" target="_blank" style="color: inherit">
              {{ link.label }}
            </a>
            <!-- В футере MAX-ссылка обёрнута в vk.com/away.php — так на реальном
                 сайте, отличается от прямой ссылки в хедере, сохраняю как есть -->
            <a :href="maxLinkFooter" target="_blank" style="color: inherit">MAX</a>
            <router-link to="/salons" style="color: inherit">Контакты</router-link>
            <router-link to="/privacy" style="color: inherit">Политика обработки персональных данных</router-link>
          </div>
        </div>

        <q-separator class="q-my-md" />

        <div class="text-caption text-grey-8">
          ⓒ SCISSORS, {{ currentYear }} / Все права защищены
        </div>
      </div>
    </q-footer>

    <!-- Попап "Приобрести подарочную карту" — на реальном сайте это #popup:gift -->
    <q-dialog v-model="giftCardOpen">
      <q-card style="min-width: 320px">
        <q-card-section>
          <div class="text-h6">Приобрести подарочную карту</div>
        </q-card-section>
        <q-card-section class="q-gutter-sm">
          <div class="text-caption">Сумма</div>
          <div class="row q-gutter-sm">
            <q-btn
              v-for="amount in giftCardAmounts" :key="amount"
              outline no-caps :label="`${amount.toLocaleString('ru-RU')} ₽`"
              :style="selectedAmount === amount
                ? { background: 'var(--sc-accent)', color: '#fff', borderColor: 'var(--sc-accent)' }
                : { color: 'var(--sc-accent)', borderColor: 'var(--sc-accent)' }"
              @click="selectedAmount = amount"
            />
          </div>
          <q-checkbox v-model="giftCardConsent">
            <span>
              Я соглашаюсь с
              <router-link to="/privacy" @click="giftCardOpen = false">политикой обработки персональных данных</router-link>
            </span>
          </q-checkbox>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Отмена" v-close-popup />
          <q-btn
            unelevated no-caps label="Отправить данные" :disable="!giftCardConsent || !selectedAmount"
            :style="{ background: 'var(--sc-accent)', color: '#fff' }"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <ConsultationDialog v-model="consultationOpen" />
  </q-layout>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { salons } from '@/data/salons';
import ConsultationDialog from '@/components/ConsultationDialog.vue';
import InstallAppBanner from '@/components/InstallAppBanner.vue';
import { messengerLinks } from '@/data/contacts';
import { useAuthStore } from '@/stores/auth';

const auth = useAuthStore();
onMounted(() => { void auth.restore(); });

const drawerOpen = ref(false);
const currentYear = new Date().getFullYear();
const giftCardOpen = ref(false);
const consultationOpen = ref(false);
const giftCardConsent = ref(false);
const selectedAmount = ref<number | null>(null);
const giftCardAmounts = [5000, 10000, 15000, 20000];

const servicesMenu = [
  { href: '/uslugi/hair', label: 'Для волос' },
  { href: '/uslugi/nails', label: 'Для ногтей' },
  { href: '/uslugi/cosmetology', label: 'Косметология' },
  { href: '/uslugi/browlashes', label: 'Брови и ресницы' },
  { href: '/uslugi/epilation', label: 'Эпиляция' },
  { href: '/uslugi/forman', label: 'Для мужчин' },
];

const reviewPlatforms = [
  { label: 'Zoon', href: 'https://zoon.ru/msk/beauty/network/scissors_studio_studii_krasoty/' },
  { label: 'Яндекс Карты', href: 'https://yandex.com.ge/maps/org/scissors_studio/93145938050/?ll=37.648052%2C55.766041&z=10' },
  { label: '2GIS', href: 'https://2gis.ru/moscow/branches/70000001018013076' },
];

const maxLinkFooter = `https://vk.com/away.php?to=${encodeURIComponent(messengerLinks.find((link) => link.label === 'MAX')?.href || '')}&utf=1`;
</script>
