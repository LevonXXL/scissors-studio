<template>
  <q-dialog v-model="cookieStore.showModal" aria-labelledby="cookie-settings-title">
    <q-card class="cookie-settings-card">
      <q-card-section class="row items-center justify-between">
        <h2 id="cookie-settings-title" class="text-h6 q-ma-none">Настройки cookies</h2>
        <q-btn flat round dense icon="close" aria-label="Закрыть настройки" v-close-popup />
      </q-card-section>

      <q-card-section class="q-pt-none">
        <p>Выберите, какие данные разрешено сохранять для работы сайта.</p>

        <div class="cookie-option row items-center justify-between q-mb-md">
          <div class="col q-pr-md">
            <div class="text-weight-medium">Необходимые</div>
            <div class="text-body2 text-grey-7">
              Данные для авторизации и сохранения вашего выбора cookies. Без них вход в профиль не работает.
            </div>
          </div>
          <q-toggle :model-value="true" disable aria-label="Необходимые cookies всегда включены" />
        </div>

        <div class="cookie-option row items-center justify-between">
          <div class="col q-pr-md">
            <div class="text-weight-medium">Аналитика</div>
            <div class="text-body2 text-grey-7">
              Яндекс Метрика помогает узнать, какие страницы посещают. Включается только с вашего согласия.
            </div>
          </div>
          <q-toggle v-model="analyticsEnabled" aria-label="Разрешить Яндекс Метрику" />
        </div>

        <p class="text-caption text-grey-7 q-mt-md q-mb-none">
          Карта Яндекса загружается отдельно при открытии страницы салона и может использовать собственные cookies.
          Подробнее — в <router-link to="/privacy" @click="cookieStore.showModal = false">политике обработки персональных данных</router-link>.
        </p>
      </q-card-section>

      <q-card-actions align="right" class="q-px-md q-pb-md">
        <q-btn flat no-caps label="Только необходимые" @click="cookieStore.acceptNecessaryOnly()" />
        <q-btn unelevated no-caps color="primary" label="Сохранить" @click="cookieStore.saveCustomSettings(analyticsEnabled)" />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';
import { useCookieStore } from '@/stores/cookies';

const cookieStore = useCookieStore();
const analyticsEnabled = ref(false);

watch(() => cookieStore.showModal, (open) => {
  if (open) analyticsEnabled.value = cookieStore.consent?.analytics ?? false;
});
</script>

<style scoped>
.cookie-settings-card {
  width: min(520px, calc(100vw - 32px));
}

.cookie-option {
  padding: 12px;
  border: 1px solid var(--sc-border);
  border-radius: 8px;
  background: var(--sc-bg-muted);
}
</style>
