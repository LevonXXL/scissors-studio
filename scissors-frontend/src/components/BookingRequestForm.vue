<template>
  <q-card flat bordered class="q-pa-md q-mx-auto" style="max-width: 720px">
    <div v-if="loading" class="text-center q-pa-lg"><q-spinner color="primary" size="3em" /></div>
    <template v-else>
      <q-banner v-if="authReady && auth.authenticated && !auth.phone" class="bg-amber-1 text-dark q-mb-md">
        В профиле не указан подтверждённый телефон. Укажите контактный номер в форме ниже, чтобы администратор мог связаться с вами.
      </q-banner>
      <div class="q-gutter-md">
        <q-select :model-value="salonId" @update:model-value="selectSalon" outlined emit-value map-options label="Салон" :options="salonOptions" />
        <q-select
          v-model="serviceIds" outlined multiple emit-value map-options use-chips
          label="Услуга или услуги" :options="serviceOptions" :disable="!salonId || optionsBusy"
        />
        <q-select
          v-model="masterId" outlined emit-value map-options clearable
          label="Предпочтительный мастер (необязательно)" :options="masterOptions"
          :disable="!salonId || optionsBusy"
        />
        <div v-if="serviceIds.length && !masterOptions.length" class="text-caption text-grey-7">
          Для выбранных услуг нет общего мастера. Можно оставить пожелание без выбора специалиста.
        </div>
        <div class="text-caption text-grey-7">Время укажите по Москве. Заявка пока не резервирует интервал.</div>
        <q-btn-toggle v-model="timeMode" no-caps toggle-color="primary" :options="[
          { label: 'Конкретное время', value: 'exact' },
          { label: 'Диапазон', value: 'range' },
        ]" />
        <q-input v-model="requestedStart" outlined type="datetime-local" label="Желаемые дата и время" />
        <q-input v-if="timeMode === 'range'" v-model="requestedEnd" outlined type="datetime-local" label="До какой даты и времени удобно" />
        <q-input v-model.trim="name" outlined label="Ваше имя" autocomplete="name" maxlength="255" />
        <q-select v-if="authReady && auth.phones.length > 1" v-model="selectedPhone" outlined emit-value map-options label="Контактный телефон" :options="auth.phones.map((value) => ({ label: value, value }))" />
        <p v-else-if="authReady && auth.phone" class="q-my-none">Телефон из профиля: {{ auth.phone }}</p>
        <q-input v-else v-model.trim="phone" outlined type="tel" autocomplete="tel" label="Контактный телефон" placeholder="+7 999 123-45-67" />
        <q-input v-model.trim="comment" outlined type="textarea" label="Комментарий (необязательно)" maxlength="1000" />
        <q-banner v-if="error" class="bg-red-1 text-negative">{{ error }}</q-banner>
        <q-banner v-if="success" class="bg-green-1 text-positive">{{ success }}</q-banner>
        <q-btn unelevated no-caps color="primary" label="Отправить заявку" :loading="submitting" :disable="!canSubmit || !!success" @click="submit" />
        <q-btn v-if="success && showReturnLink && auth.authenticated" flat no-caps color="primary" label="К моим записям" to="/login" />
      </div>
    </template>
  </q-card>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { ApiError } from '@/api/client';
import { createBookingRequest, fetchBookingOptions, fetchSalons, type BookingOptions } from '@/api/endpoints';
import type { Salon } from '@/api/types';
import { useAuthStore } from '@/stores/auth';

defineProps<{ showReturnLink?: boolean }>();
const emit = defineEmits<{ created: [detail: string] }>();
const route = useRoute();
const auth = useAuthStore();
const authReady = ref(false);
const loading = ref(true);
const optionsBusy = ref(false);
const submitting = ref(false);
const salons = ref<Salon[]>([]);
const options = ref<BookingOptions>({ services: [], masters: [] });
const salonId = ref<number | null>(null);
const serviceIds = ref<number[]>([]);
const masterId = ref<number | null>(null);
const timeMode = ref<'exact' | 'range'>('exact');
const requestedStart = ref('');
const requestedEnd = ref('');
const name = ref('');
const phone = ref('');
const selectedPhone = ref('');
const comment = ref('');
const error = ref('');
const success = ref('');
const salonOptions = computed(() => salons.value.map((salon) => ({ label: salon.name, value: salon.id })));
const serviceOptions = computed(() => options.value.services
  .filter((service) => !masterId.value || service.master_ids.includes(masterId.value))
  .map((service) => ({ label: `${service.category} · ${service.title}`, value: service.id })));
const masterOptions = computed(() => options.value.masters
  .filter((master) => serviceIds.value.every((id) => options.value.services.find((service) => service.id === id)?.master_ids.includes(master.id)))
  .map((master) => ({ label: master.name, value: master.id })));
const canSubmit = computed(() => !!salonId.value && serviceIds.value.length > 0 && !!requestedStart.value &&
  (timeMode.value === 'exact' || !!requestedEnd.value) && !!name.value &&
  (!auth.phone || authReady.value) && (!!auth.phone || !!phone.value) && !optionsBusy.value);

watch(() => auth.phone, (value) => { selectedPhone.value = value; }, { immediate: true });

onMounted(async () => {
  try {
    if (!auth.authenticated) await auth.restore();
    authReady.value = true;
    salons.value = await fetchSalons();
    await applyRouteSelection();
    if (!salons.value.length) error.value = 'Сейчас нет доступных салонов.';
  } catch (cause) {
    error.value = cause instanceof ApiError ? cause.message : 'Не удалось загрузить салоны.';
  } finally {
    authReady.value = true;
    loading.value = false;
  }
});

let optionsRequest = 0;
async function loadSalonOptions(id: number | null) {
  const requestId = ++optionsRequest;
  salonId.value = id;
  serviceIds.value = [];
  masterId.value = null;
  options.value = { services: [], masters: [] };
  if (!id) return;
  optionsBusy.value = true;
  error.value = '';
  try {
    const loaded = await fetchBookingOptions(id);
    if (requestId === optionsRequest) options.value = loaded;
  } catch (cause) {
    if (requestId === optionsRequest) error.value = cause instanceof ApiError ? cause.message : 'Не удалось загрузить услуги.';
  } finally {
    if (requestId === optionsRequest) optionsBusy.value = false;
  }
}

function queryValue(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function matchesSelection(loaded: BookingOptions, service: string, master: string): boolean {
  const selectedService = loaded.services.find((item) => String(item.id) === service);
  const selectedMaster = loaded.masters.find((item) => String(item.id) === master || item.slug === master);
  return (!service || !!selectedService) && (!master || !!selectedMaster)
    && (!selectedService || !selectedMaster || selectedService.master_ids.includes(selectedMaster.id));
}

async function applyRouteSelection() {
  if (!salons.value.length) return;
  const salon = queryValue(route.query.salon);
  const service = queryValue(route.query.service);
  const master = queryValue(route.query.master);
  const explicitSalon = salons.value.find((item) => item.slug === salon || String(item.id) === salon);
  if (salon && !explicitSalon) {
    await loadSalonOptions(salons.value[0]?.id ?? null);
    error.value = 'Указанный салон недоступен.';
    return;
  }
  const candidates = explicitSalon ? [explicitSalon] : salons.value;
  for (const candidate of candidates) {
    await loadSalonOptions(candidate.id);
    if (options.value.services.length || options.value.masters.length) {
      if (matchesSelection(options.value, service, master)) {
        serviceIds.value = service ? [Number(service)] : [];
        const selectedMaster = options.value.masters.find((item) => String(item.id) === master || item.slug === master);
        masterId.value = selectedMaster?.id ?? null;
        return;
      }
    }
    if (explicitSalon || (!service && !master)) break;
  }
  if (service || master) error.value = 'Указанная услуга или мастер недоступны в выбранном салоне.';
}

function selectSalon(id: number | null) {
  void loadSalonOptions(id);
}

watch(() => [route.query.salon, route.query.service, route.query.master], () => {
  if (salons.value.length) void applyRouteSelection();
});

watch(serviceIds, (ids) => {
  if (masterId.value && ids.some((id) => !options.value.services.find((service) => service.id === id)?.master_ids.includes(masterId.value!))) {
    masterId.value = null;
  }
});

function moscowDateTime(value: string): string {
  return `${value}:00+03:00`;
}

async function submit() {
  if (!canSubmit.value || submitting.value || !salonId.value) return;
  error.value = '';
  submitting.value = true;
  try {
    const result = await createBookingRequest({
      salon: salonId.value,
      service_ids: serviceIds.value,
      preferred_master: masterId.value,
      requested_start: moscowDateTime(requestedStart.value),
      requested_end: timeMode.value === 'range' ? moscowDateTime(requestedEnd.value) : null,
      name: name.value,
      phone: auth.phone ? selectedPhone.value : phone.value,
      comment: comment.value,
    });
    success.value = result.detail;
    emit('created', result.detail);
  } catch (cause) {
    error.value = cause instanceof ApiError ? cause.message : 'Не удалось отправить заявку.';
  } finally {
    submitting.value = false;
  }
}
</script>
