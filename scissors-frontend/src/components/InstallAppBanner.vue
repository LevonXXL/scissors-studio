<template>
  <aside v-if="visible" class="install-banner site-page" aria-label="Установка приложения">
    <div class="install-banner__mark"><img :src="publicAssetUrl('/logo/scissors-512x512.png')" alt="" /></div>
    <div class="install-banner__copy">
      <div class="text-overline">SCISSORS STUDIO В ВАШЕМ ТЕЛЕФОНЕ</div>
      <div class="text-h6 text-weight-bold">Установите приложение</div>
      <p class="q-mb-sm">Быстрый доступ к услугам, салонам и онлайн-записи.</p>
      <div v-if="isIos" class="install-banner__steps">
        <span><q-icon name="ios_share" size="21px" /> Нажмите «Поделиться» в Safari</span>
        <q-icon name="arrow_forward" size="17px" />
        <span><q-icon name="add_box" size="21px" /> «На экран Домой»</span>
      </div>
      <div v-else-if="!installPrompt" class="install-banner__steps">
        <span><q-icon name="more_vert" size="21px" /> Откройте меню браузера</span>
        <q-icon name="arrow_forward" size="17px" />
        <span><q-icon name="install_mobile" size="21px" /> «Установить приложение»</span>
      </div>
    </div>
    <div class="install-banner__actions">
      <q-btn v-if="installPrompt" unelevated no-caps icon="install_mobile" label="Установить" color="white" text-color="dark" @click="install" />
      <q-btn flat round dense icon="close" color="white" aria-label="Скрыть предложение установки" @click="dismiss" />
    </div>
  </aside>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue';
import { publicAssetUrl } from '@/config/urls';

interface InstallPromptEvent extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

const visible = ref(false);
const isIos = ref(false);
const installPrompt = ref<InstallPromptEvent | null>(null);

function onBeforeInstall(event: Event) {
  event.preventDefault();
  installPrompt.value = event as InstallPromptEvent;
}
function onInstalled() { visible.value = false; }
function dismiss() {
  visible.value = false;
  window.sessionStorage.setItem('install-banner-dismissed', '1');
}
async function install() {
  if (!installPrompt.value) return;
  await installPrompt.value.prompt();
  const choice = await installPrompt.value.userChoice;
  installPrompt.value = null;
  if (choice.outcome === 'accepted') visible.value = false;
}

// onMounted(() => {
//   const standalone = window.matchMedia('(display-mode: standalone)').matches ||
//     ('standalone' in navigator && Boolean((navigator as Navigator & { standalone?: boolean }).standalone));
//   isIos.value = /iPad|iPhone|iPod/.test(navigator.userAgent);
//   visible.value = !standalone && window.sessionStorage.getItem('install-banner-dismissed') !== '1';
//   window.addEventListener('beforeinstallprompt', onBeforeInstall);
//   window.addEventListener('appinstalled', onInstalled);
// });
// onUnmounted(() => {
//   window.removeEventListener('beforeinstallprompt', onBeforeInstall);
//   window.removeEventListener('appinstalled', onInstalled);
// });


onMounted(() => {
  const standalone =
    window.matchMedia('(display-mode: standalone)').matches ||
    window.matchMedia('(display-mode: fullscreen)').matches ||
    ('standalone' in navigator &&
      Boolean((navigator as Navigator & { standalone?: boolean }).standalone));

  isIos.value = /iPad|iPhone|iPod/.test(navigator.userAgent);

  visible.value =
    !standalone &&
    window.sessionStorage.getItem('install-banner-dismissed') !== '1';

  window.addEventListener('beforeinstallprompt', onBeforeInstall);
  window.addEventListener('appinstalled', onInstalled);
});


</script>

<style scoped>
.install-banner {
  display: flex;
  align-items: center;
  gap: 20px;
  margin: 16px auto 0;
  padding: 18px 22px;
  border-radius: 20px;
  color: #fff;
  background: linear-gradient(120deg, #151515 0%, #2b2525 70%, #641d18 100%);
  box-shadow: 0 12px 30px rgba(25, 20, 20, .17);
}
.install-banner__mark { flex: 0 0 70px; }
.install-banner__mark img { display: block; width: 70px; height: 70px; border-radius: 16px; background: #fff; }
.install-banner__copy { flex: 1; min-width: 0; }
.install-banner__copy p { opacity: .9; }
.install-banner__steps { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; font-size: 13px; }
.install-banner__steps span { display: inline-flex; align-items: center; gap: 5px; }
.install-banner__actions { display: flex; align-items: center; gap: 6px; align-self: flex-start; }
@media (max-width: 600px) {
  .install-banner { width: calc(100% - 24px); margin: 12px auto 0; padding: 16px; gap: 12px; align-items: flex-start; flex-wrap: wrap; }
  .install-banner__mark { flex-basis: 46px; }
  .install-banner__mark img { width: 46px; height: 46px; border-radius: 12px; }
  .install-banner__copy { flex-basis: calc(100% - 58px); }
  .install-banner__actions { width: 100%; justify-content: flex-end; }
}

@media (display-mode: standalone),
(display-mode: fullscreen) {
  .install-banner {
    display: none !important;
  }
}
</style>
