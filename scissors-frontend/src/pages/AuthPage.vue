<template>
  <q-page class="site-page q-px-md q-py-xl">
    <q-card class="q-mx-auto" style="max-width: 520px">
      <q-card-section v-if="!auth.authenticated">
        <h1 class="text-h5 q-my-sm">Вход и профиль</h1>
        <p class="text-grey-7 q-mb-none">Войдите по телефону или подтверждённому email.</p>
      </q-card-section>

      <q-tabs v-if="auth.authenticated && !verificationToken" v-model="activeSection" align="left" active-color="primary" indicator-color="primary">
        <q-tab name="bookings" label="Записи" no-caps />
        <q-tab name="profile" label="Профиль" no-caps />
      </q-tabs>

      <q-card-section v-if="verificationToken" class="q-gutter-md">
        <p class="q-my-none">Подтвердите адрес электронной почты для входа по email и паролю.</p>
        <q-btn unelevated color="primary" no-caps label="Подтвердить email" :loading="busy" @click="submitEmailVerification" />
      </q-card-section>

      <q-card-section v-else-if="!auth.authenticated" class="q-gutter-md">
        <div class="row q-gutter-sm">
          <q-btn no-caps :outline="loginMode !== 'phone'" :unelevated="loginMode === 'phone'" color="primary" label="По телефону" @click="loginMode = 'phone'; clearMessage()" />
          <q-btn no-caps :outline="loginMode !== 'email'" :unelevated="loginMode === 'email'" color="primary" label="По email" @click="loginMode = 'email'; clearMessage()" />
        </div>

        <template v-if="loginMode === 'email'">
          <q-input v-model.trim="email" outlined label="Email" type="email" autocomplete="email" />
          <q-input v-model="password" outlined label="Пароль" type="password" autocomplete="current-password" @keyup.enter="submitEmailLogin" />
          <q-btn unelevated color="primary" no-caps label="Войти" :loading="busy" :disable="!email || !password" @click="submitEmailLogin" />
          <p class="text-caption text-grey-7 q-mb-none">Вход по email доступен после подтверждения адреса.</p>
        </template>

        <template v-else>
          <q-input v-model="phone" outlined label="Номер телефона" type="tel" autocomplete="tel" placeholder="+7 999 123-45-67" />
          <template v-if="step === 'choose'">
            <div class="row q-gutter-sm">
              <q-btn unelevated color="primary" no-caps label="Войти по паролю" @click="step = 'password'" />
              <q-btn outline color="primary" no-caps label="Получить код по SMS" @click="step = 'sms'" />
            </div>
          </template>
          <template v-else-if="step === 'password'">
            <q-input v-model="password" outlined label="Пароль" type="password" autocomplete="current-password" @keyup.enter="submitPhonePassword" />
            <q-btn unelevated color="primary" no-caps label="Войти" :loading="busy" @click="submitPhonePassword" />
            <q-btn flat no-caps label="Получить код по SMS" @click="step = 'sms'; clearMessage()" />
          </template>
          <template v-else>
            <q-btn outline color="primary" no-caps :label="cooldown ? `Повторить через ${cooldown} с` : 'Запросить код'" :loading="busy" :disable="cooldown > 0" @click="requestCode" />
            <q-input v-if="codeRequested" v-model="code" outlined label="Код подтверждения" inputmode="numeric" maxlength="6" autocomplete="one-time-code" @keyup.enter="submitCode" />
            <q-btn v-if="codeRequested" unelevated color="primary" no-caps label="Подтвердить" :loading="busy" @click="submitCode" />
            <q-btn flat no-caps label="Войти по паролю" @click="step = 'password'; clearMessage()" />
          </template>
        </template>
      </q-card-section>

      <q-card-section v-else-if="activeSection === 'profile'" class="q-gutter-md">
        <div class="text-subtitle1 text-weight-medium">Телефоны для входа и ваших записей</div>
        <q-list v-if="auth.phones.length" bordered separator>
          <q-item v-for="verifiedPhone in auth.phones" :key="verifiedPhone">
            <q-item-section avatar><q-icon name="verified" color="positive" /></q-item-section>
            <q-item-section>{{ verifiedPhone }}</q-item-section>
          </q-item>
        </q-list>
        <p v-else class="text-body2 q-my-none">Подтверждённых номеров пока нет.</p>
        <div class="text-subtitle2 text-weight-medium">Добавить номер</div>
        <p class="text-body2 q-my-none">После подтверждения по SMS по этому номеру можно будет входить и находить записи.</p>
        <q-input v-model="profilePhone" outlined type="tel" autocomplete="tel" label="Новый номер телефона" placeholder="+7 999 123-45-67" />
        <q-btn outline color="primary" no-caps :label="profileCooldown ? `Повторить через ${profileCooldown} с` : 'Запросить код'" :loading="busy" :disable="profileCooldown > 0 || !profilePhone" @click="requestProfileCode" />
        <template v-if="profileCodeRequested">
          <q-input v-model="profileCode" outlined inputmode="numeric" maxlength="6" autocomplete="one-time-code" label="Код подтверждения" />
          <q-btn unelevated color="primary" no-caps label="Подтвердить телефон" :loading="busy" :disable="!profileCode" @click="submitProfileCode" />
        </template>
        <p v-if="auth.isStaff" class="q-my-none text-weight-medium">Профиль сотрудника</p>

        <q-separator />
        <div class="text-subtitle1 text-weight-medium">Email для входа</div>
        <p class="text-body2 q-my-none">{{ auth.email ? `Подтверждён: ${auth.email}` : 'Адрес пока не подтверждён.' }}</p>
        <p v-if="auth.pendingEmail" class="text-caption text-grey-7 q-my-none">Ожидает подтверждения: {{ auth.pendingEmail }}</p>
        <q-input v-model.trim="profileEmail" outlined type="email" autocomplete="email" label="Email" />
        <q-input v-if="auth.email && profileEmail.toLowerCase() !== auth.email" v-model="emailChangePassword" outlined type="password" autocomplete="current-password" label="Текущий пароль для смены email" />
        <q-btn outline color="primary" no-caps label="Отправить ссылку подтверждения" :loading="busy" :disable="!profileEmail" @click="requestVerification" />

        <q-separator />
        <div class="text-subtitle1 text-weight-medium">Пароль</div>
        <template v-if="!auth.hasPassword">
          <p class="text-grey-7 q-my-none">Установите пароль для последующих входов.</p>
          <q-input v-model="newPassword" outlined type="password" autocomplete="new-password" label="Новый пароль" />
          <q-btn unelevated color="primary" no-caps label="Установить пароль" :loading="busy" @click="submitSetPassword" />
        </template>
        <template v-else>
          <q-btn flat no-caps :label="showChange ? 'Скрыть смену пароля' : 'Сменить пароль'" @click="showChange = !showChange" />
          <template v-if="showChange">
            <q-input v-model="password" outlined type="password" autocomplete="current-password" label="Текущий пароль" />
            <q-input v-model="newPassword" outlined type="password" autocomplete="new-password" label="Новый пароль" />
            <q-btn unelevated color="primary" no-caps label="Изменить пароль" :loading="busy" @click="submitChangePassword" />
          </template>
        </template>

        <q-separator />
        <div class="q-pa-sm rounded-borders bg-grey-1">
          <q-toggle :model-value="auth.pushEnabled" :disable="pushBusy" label="Получать push-сообщения" @update:model-value="updatePush" />
          <p class="text-caption text-grey-7 q-ml-md q-mb-none">Разрешение браузера: {{ permissionLabel }}</p>
          <q-btn
            v-if="auth.pushEnabled"
            flat no-caps color="primary" label="Подключить push на этом устройстве"
            :loading="pushBusy" :disable="pushPermission === 'unsupported'"
            @click="connectDevicePush"
          />
        </div>
        <q-btn flat no-caps label="Выйти" @click="logout" />
      </q-card-section>

      <q-card-section v-if="(error || notice) && (!auth.authenticated || activeSection === 'profile' || verificationToken)">
        <q-banner :class="error ? 'bg-red-1 text-negative' : 'bg-blue-1'">{{ error || notice }}</q-banner>
      </q-card-section>
    </q-card>
    <q-card v-if="auth.authenticated && activeSection === 'bookings' && !verificationToken" class="q-mx-auto q-mt-lg" :style="{ maxWidth: '520px' }">
      <q-card-section>
        <div class="text-h6">Мои записи</div>
        <p v-if="auth.phones.length" class="text-caption text-grey-7 q-mb-none">Показаны записи по подтверждённым номерам: {{ auth.phones.join(', ') }}</p>
        <p v-else class="text-caption text-grey-7 q-mb-none">Подтвердите телефон в профиле, чтобы увидеть записи, оформленные на него.</p>
        <q-btn
          unelevated no-caps color="primary" class="q-mt-md"
          label="Записаться в YCLIENTS"
          :href="YCLIENTS_NETWORK_BOOKING_URL" target="_blank" rel="noopener noreferrer"
        />
      </q-card-section>
      <q-card-section v-if="historyError" class="text-negative">{{ historyError }}</q-card-section>
      <q-card-section v-for="period in periods" :key="period">
        <div class="text-subtitle1 text-weight-medium q-mb-sm">{{ period === 'future' ? 'Будущие записи и заявки' : 'Прошлые записи и заявки' }}</div>
        <q-linear-progress v-if="historyBusy && history[period].length === 0" indeterminate color="primary" />
        <p v-else-if="history[period].length === 0" class="text-grey-7 q-my-none">Записей нет.</p>
        <q-list v-else separator>
          <q-item v-for="booking in history[period]" :key="booking.id" class="q-px-none">
            <q-item-section>
              <q-item-label>{{ booking.salon }} · {{ formatBookingDate(booking.start_datetime || booking.requested_start) }}</q-item-label>
              <q-item-label caption>{{ booking.services || 'Услуга не указана' }}<span v-if="booking.master"> · {{ booking.master }}</span></q-item-label>
              <q-item-label caption>{{ bookingStatus(booking.status) }}</q-item-label>
            </q-item-section>
          </q-item>
        </q-list>
        <q-btn v-if="historyNext[period]" flat no-caps color="primary" label="Показать ещё" :loading="historyBusy" @click="loadBookings(period)" />
      </q-card-section>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ApiError } from '@/api/client';
import { YCLIENTS_NETWORK_BOOKING_URL } from '@/utils/yclientsBooking';
import { changeAuthPassword, fetchMyBookings, loginWithEmail, loginWithPassword, requestAuthCode, requestEmailVerification, setAuthPassword, verifyAuthCode, verifyEmail, verifyProfilePhone, type MyBooking } from '@/api/endpoints';
import { useAuthStore } from '@/stores/auth';
import { browserPushPermission, disableBrowserPush, enableBrowserPush, type BrowserPushPermission } from '@/push';

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();
const verificationToken = computed(() => {
  const token = route.query.verify_email;
  return typeof token === 'string' ? token : new URLSearchParams(route.hash.slice(1)).get('verify_email') || '';
});
const activeSection = ref<'profile' | 'bookings'>('bookings');
const loginMode = ref<'phone' | 'email'>('phone');
const phone = ref('');
const profilePhone = ref('');
const profileCode = ref('');
const profileCodeRequested = ref(false);
const profileCooldown = ref(0);
const periods = ['future', 'past'] as const;
const email = ref('');
const profileEmail = ref('');
const emailChangePassword = ref('');
const password = ref('');
const newPassword = ref('');
const code = ref('');
const step = ref<'choose' | 'password' | 'sms'>('choose');
const codeRequested = ref(false);
const busy = ref(false);
const error = ref('');
const notice = ref('');
const cooldown = ref(0);
const history = ref<{ future: MyBooking[]; past: MyBooking[] }>({ future: [], past: [] });
const historyNext = ref<{ future: number | null; past: number | null }>({ future: 1, past: 1 });
const historyBusy = ref(false);
const historyError = ref('');
let historyVersion = 0;
const showChange = ref(false);
const pushBusy = ref(false);
const pushPermission = ref<BrowserPushPermission>('unsupported');
const permissionLabel = computed(() => ({
  granted: 'разрешено', denied: 'запрещено', default: 'ещё не запрошено', unsupported: 'не поддерживается',
})[pushPermission.value]);
let timer: ReturnType<typeof setInterval> | undefined;

watch(() => [auth.email, auth.pendingEmail], ([verified, pending]) => {
  profileEmail.value = pending || verified || '';
});
watch(() => [auth.authenticated, ...auth.phones], ([authenticated]) => {
  reloadBookings(Boolean(authenticated));
}, { immediate: true });
onMounted(() => {
  void auth.restore();
  pushPermission.value = browserPushPermission();
  timer = setInterval(() => {
    if (cooldown.value > 0) cooldown.value -= 1;
    if (profileCooldown.value > 0) profileCooldown.value -= 1;
  }, 1000);
});
onUnmounted(() => { if (timer) clearInterval(timer); });

function clearMessage() { error.value = ''; notice.value = ''; }
function resetForm() {
  password.value = ''; newPassword.value = ''; code.value = ''; emailChangePassword.value = '';
  step.value = 'choose'; codeRequested.value = false; clearMessage();
}
function showError(cause: unknown) {
  error.value = cause instanceof ApiError || cause instanceof Error ? cause.message : 'Не удалось выполнить запрос.';
  if (cause instanceof ApiError && cause.status === 429) {
    cooldown.value = cause.retryAfter || 60;
    profileCooldown.value = cause.retryAfter || 60;
  }
}
async function perform(action: () => Promise<void>) {
  if (busy.value) return;
  busy.value = true; clearMessage();
  try { await action(); } catch (cause) { showError(cause); } finally { busy.value = false; }
}
function requestCode() {
  void perform(async () => {
    await requestAuthCode(phone.value);
    codeRequested.value = true;
    cooldown.value = 60;
    notice.value = 'Код запрошен. В режиме разработки он доступен в журнале сервера.';
  });
}
function requestProfileCode() {
  void perform(async () => {
    await requestAuthCode(profilePhone.value);
    profileCodeRequested.value = true;
    profileCooldown.value = 60;
    notice.value = 'Код запрошен. В режиме разработки он доступен в журнале сервера.';
  });
}
function submitProfileCode() {
  void perform(async () => {
    await verifyProfilePhone(profilePhone.value, profileCode.value);
    profileCode.value = '';
    profilePhone.value = '';
    profileCodeRequested.value = false;
    await auth.restore();
    notice.value = 'Телефон подтверждён. Записи на этот номер доступны в профиле.';
  });
}
async function loadBookings(period: 'future' | 'past') {
  const page = historyNext.value[period];
  if (!page || historyBusy.value) return;
  const version = historyVersion;
  historyBusy.value = true;
  historyError.value = '';
  try {
    const result = await fetchMyBookings(period, page);
    if (version !== historyVersion) return;
    history.value[period].push(...result.results);
    historyNext.value[period] = result.next ? page + 1 : null;
  } catch (cause) {
    if (version === historyVersion) historyError.value = cause instanceof ApiError ? cause.message : 'Не удалось загрузить записи.';
  } finally {
    if (version === historyVersion) historyBusy.value = false;
  }
}
async function refreshBookings() {
  await loadBookings('future');
  await loadBookings('past');
}
function reloadBookings(authenticated = auth.authenticated) {
  historyVersion += 1;
  history.value = { future: [], past: [] };
  historyNext.value = { future: 1, past: 1 };
  historyBusy.value = false;
  historyError.value = '';
  if (authenticated && typeof window !== 'undefined') void refreshBookings();
}
function bookingStatus(status: MyBooking['status']) {
  return ({ pending: 'Ожидает подтверждения', confirmed: 'Подтверждена', cancelled: 'Отменена', completed: 'Завершена', no_show: 'Не состоялась' })[status];
}
function formatBookingDate(value: string | null) {
  return value ? new Date(value).toLocaleString('ru-RU', { dateStyle: 'medium', timeStyle: 'short' }) : 'время уточняется';
}
function submitCode() {
  void perform(async () => {
    auth.accept(await verifyAuthCode(phone.value, code.value));
    password.value = ''; code.value = '';
  });
}
function submitPhonePassword() {
  void perform(async () => {
    auth.accept(await loginWithPassword(phone.value, password.value));
    password.value = '';
  });
}
function submitEmailLogin() {
  void perform(async () => {
    auth.accept(await loginWithEmail(email.value, password.value));
    password.value = '';
  });
}
function requestVerification() {
  void perform(async () => {
    await requestEmailVerification(profileEmail.value, emailChangePassword.value);
    emailChangePassword.value = '';
    await auth.restore();
    notice.value = 'Если адрес доступен, письмо со ссылкой отправлено.';
  });
}
function submitEmailVerification() {
  void perform(async () => {
    await verifyEmail(verificationToken.value);
    await router.replace({ path: '/login', query: {}, hash: '' });
    await auth.restore();
    loginMode.value = 'email';
    notice.value = 'Email подтверждён. Теперь можно войти с ним и паролем.';
  });
}
function submitSetPassword() {
  void perform(async () => {
    await setAuthPassword(newPassword.value);
    newPassword.value = ''; auth.hasPassword = true;
    notice.value = 'Пароль установлен.';
  });
}
function submitChangePassword() {
  void perform(async () => {
    await changeAuthPassword(password.value, newPassword.value);
    password.value = ''; newPassword.value = ''; showChange.value = false;
    notice.value = 'Пароль изменён.';
  });
}
async function updatePush(enabled: boolean) {
  if (pushBusy.value) return;
  pushBusy.value = true;
  clearMessage();
  try {
    if (enabled) await enableBrowserPush(); else await disableBrowserPush();
    auth.pushEnabled = enabled;
  } catch (cause) {
    await auth.restore();
    showError(cause);
  } finally {
    pushPermission.value = browserPushPermission();
    pushBusy.value = false;
  }
}
async function connectDevicePush() {
  if (pushBusy.value) return;
  pushBusy.value = true;
  clearMessage();
  try {
    await enableBrowserPush();
    notice.value = 'Подписка этого устройства сохранена.';
  } catch (cause) {
    showError(cause);
  } finally {
    pushPermission.value = browserPushPermission();
    pushBusy.value = false;
  }
}
async function logout() {
  try { await auth.logout(); } catch { /* Local sign-out still completes. */ }
  resetForm();
}
</script>
