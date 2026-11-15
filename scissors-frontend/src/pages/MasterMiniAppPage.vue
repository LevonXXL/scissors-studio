<template>
  <q-layout view="hHh lpR fFf" class="mini-app">
    <q-header class="bg-white text-dark mini-app-header">
      <q-toolbar class="q-px-md">
        <img
          class="mini-app-brand-logo"
          :src="staticAssetUrl('/icons/favicon-96x96.png')"
          alt=""
          width="40"
          height="40"
        />
        <q-toolbar-title class="text-weight-bold"
          >Scissors Studio</q-toolbar-title
        >
      </q-toolbar>
    </q-header>
    <q-page-container>
      <q-page class="q-pa-md">
        <div class="mini-app-content">
          <q-banner
            v-if="error"
            rounded
            class="bg-red-1 text-negative q-mb-md"
            >{{ error }}</q-banner
          >
          <q-banner
            v-if="notice"
            rounded
            class="bg-green-1 text-positive q-mb-md"
            >{{ notice }}</q-banner
          >
          <q-linear-progress v-if="loading" indeterminate color="primary" />

          <template v-if="profile">
            <q-card flat bordered class="q-mb-md">
              <q-card-section class="row items-center no-wrap q-gutter-md">
                <q-avatar square size="64px" color="grey-2" text-color="grey-7">
                  <img
                    v-if="profile.photo_url"
                    :src="profile.photo_url"
                    alt="Фото мастера"
                  />
                  <q-icon v-else name="person" size="32px" />
                </q-avatar>
                <div>
                  <div class="text-h6">{{ profile.name }}</div>
                  <div class="text-caption text-grey-7">
                    Ваш профиль Scissors Studio
                  </div>
                </div>
              </q-card-section>
            </q-card>

            <q-tabs
              v-model="section"
              dense
              align="justify"
              active-color="primary"
              indicator-color="primary"
              class="q-mb-md"
            >
              <q-tab name="profile" label="Профиль" no-caps />
              <q-tab name="gallery" label="Галерея" no-caps />
              <q-tab name="services" label="Услуги" no-caps />
              <q-tab name="works" label="Работы" no-caps />
            </q-tabs>

            <q-card v-if="section === 'profile'" flat bordered>
              <q-card-section class="q-gutter-md">
                <div class="text-subtitle1 text-weight-medium">Описание</div>
                <q-input
                  v-model="bioDraft"
                  type="textarea"
                  outlined
                  autogrow
                  maxlength="2000"
                  counter
                  label="Расскажите о себе"
                />
                <q-btn
                  unelevated
                  color="primary"
                  no-caps
                  label="Сохранить описание"
                  :loading="busy"
                  @click="saveBio"
                />
                <q-separator />
                <div class="text-subtitle1 text-weight-medium">
                  Содержимое страницы мастера
                </div>
                <q-editor
                  v-model="contentDraft"
                  min-height="180px"
                  :toolbar="[
                    ['bold', 'italic', 'underline', 'strike'],
                    ['unordered', 'ordered'],
                    ['link'],
                  ]"
                />
                <q-btn
                  unelevated
                  color="primary"
                  no-caps
                  label="Сохранить страницу"
                  :loading="busy"
                  @click="saveContent"
                />
                <q-separator />
                <div class="text-subtitle1 text-weight-medium">
                  Фото профиля
                </div>
                <q-file
                  v-model="profileFile"
                  outlined
                  accept="image/jpeg,image/png,image/webp,image/gif"
                  label="Выбрать фотографию"
                />
                <q-btn
                  outline
                  color="primary"
                  no-caps
                  label="Загрузить фото"
                  :disable="!profileFile"
                  :loading="busy"
                  @click="upload('profile')"
                />
              </q-card-section>
            </q-card>

            <q-card v-else-if="section === 'gallery'" flat bordered>
              <q-card-section class="q-gutter-md">
                <div class="text-subtitle1 text-weight-medium">
                  Общая галерея
                </div>
                <q-file
                  v-model="galleryFile"
                  outlined
                  accept="image/jpeg,image/png,image/webp,image/gif"
                  label="Выбрать фотографию"
                />
                <q-input
                  v-model="galleryCaption"
                  outlined
                  maxlength="255"
                  label="Подпись"
                />
                <q-btn
                  unelevated
                  color="primary"
                  no-caps
                  label="Добавить в галерею"
                  :disable="!galleryFile"
                  :loading="busy"
                  @click="upload('gallery')"
                />
                <div v-if="profile.gallery.length" class="mini-app-grid">
                  <div v-for="photo in profile.gallery" :key="photo.id">
                    <q-img :src="photo.url" :ratio="1" rounded />
                    <div class="text-caption q-mt-xs">{{ photo.caption }}</div>
                  </div>
                </div>
                <p v-else class="text-grey-7 q-mb-none">Фотографий пока нет.</p>
              </q-card-section>
            </q-card>

            <q-card v-else-if="section === 'services'" flat bordered>
              <q-card-section class="q-gutter-md">
                <div class="text-subtitle1 text-weight-medium">Мои услуги</div>
                <p class="text-caption text-grey-7 q-mb-none">
                  Доступны услуги с ценой для уровня
                  {{ profile.price_level_display || "Единая цена" }}.
                </p>
                <p v-if="!profile.salons.length" class="text-grey-7 q-mb-none">
                  Сначала привяжите мастера к салону в админке.
                </p>
                <template v-else>
                  <q-select
                    v-model="selectedSalonId"
                    outlined
                    emit-value
                    map-options
                    :options="salonOptions"
                    label="Салон"
                    @update:model-value="onSalonChanged"
                  />
                  <q-select
                    v-model="selectedCategoryId"
                    outlined
                    emit-value
                    map-options
                    :options="categoryOptions"
                    label="Раздел услуг"
                    @update:model-value="onCategoryChanged"
                  />
                  <q-list v-if="categoryAssignments.length" bordered separator>
                    <q-item v-for="item in categoryAssignments" :key="item.id">
                      <q-item-section>
                        <q-item-label>{{ item.title }}</q-item-label>
                        <q-item-label caption>{{ item.category }}</q-item-label>
                      </q-item-section>
                      <q-item-section side>
                        <q-btn
                          flat
                          round
                          icon="delete_outline"
                          color="negative"
                          :aria-label="`Убрать услугу ${item.title}`"
                          :disable="busy"
                          @click="removeService(item.id, item.title)"
                        />
                      </q-item-section>
                    </q-item>
                  </q-list>
                  <p v-else class="text-grey-7 q-mb-none">
                    В этом разделе пока нет выбранных услуг.
                  </p>
                  <q-select
                    :key="`${selectedSalonId}-${selectedCategoryId}`"
                    v-model="serviceToAddId"
                    outlined
                    use-input
                    fill-input
                    hide-selected
                    emit-value
                    map-options
                    input-debounce="300"
                    :options="serviceSearchOptions"
                    :disable="!selectedSalonId || !selectedCategoryId || busy"
                    label="Найти услугу по названию"
                    hint="Введите начало любого слова, например «окра»"
                    @filter="filterAvailableServices"
                  />
                  <q-btn
                    unelevated
                    color="primary"
                    no-caps
                    label="Добавить услугу"
                    :disable="
                      !serviceToAddId || !selectedSalonId || !selectedCategoryId
                    "
                    :loading="busy"
                    @click="addService"
                  />
                </template>
              </q-card-section>
            </q-card>

            <q-card v-else flat bordered>
              <q-card-section class="q-gutter-md">
                <div class="text-subtitle1 text-weight-medium">
                  Примеры работ по услугам
                </div>
                <q-select
                  v-model="selectedServiceId"
                  outlined
                  emit-value
                  map-options
                  :options="serviceOptions"
                  label="Услуга"
                />
                <q-file
                  v-model="workFile"
                  outlined
                  accept="image/jpeg,image/png,image/webp,image/gif"
                  label="Выбрать фотографию"
                />
                <q-input
                  v-model="workCaption"
                  outlined
                  maxlength="255"
                  label="Подпись"
                />
                <q-btn
                  unelevated
                  color="primary"
                  no-caps
                  label="Добавить работу"
                  :disable="!workFile || !selectedServiceId"
                  :loading="busy"
                  @click="upload('work')"
                />
                <div v-if="profile.works.length" class="mini-app-grid">
                  <div v-for="photo in profile.works" :key="photo.id">
                    <q-img :src="photo.url" :ratio="1" rounded />
                    <div class="text-caption q-mt-xs">
                      {{ photo.service_title
                      }}<span v-if="photo.caption"> · {{ photo.caption }}</span>
                    </div>
                  </div>
                </div>
                <p v-else class="text-grey-7 q-mb-none">Работ пока нет.</p>
              </q-card-section>
            </q-card>
          </template>
        </div>
      </q-page>
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useMeta } from "quasar";
import { staticAssetUrl } from "@/utils/assetUrl";
import {
  addMiniAppService,
  fetchMiniAppProfile,
  miniAppError,
  removeMiniAppService,
  saveMiniAppBio,
  saveMiniAppContent,
  searchMiniAppServices,
  uploadMiniAppPhoto,
  type MiniAppProfile,
} from "@/api/telegramMiniApp";

useMeta({ meta: { robots: { name: "robots", content: "noindex,nofollow" } } });

interface TelegramWebApp {
  initData: string;
  ready(): void;
  expand(): void;
}

const loading = ref(true);
const busy = ref(false);
const error = ref("");
const notice = ref("");
const initData = ref("");
const profile = ref<MiniAppProfile | null>(null);
const bioDraft = ref("");
const contentDraft = ref("");
const profileFile = ref<File | null>(null);
const galleryFile = ref<File | null>(null);
const workFile = ref<File | null>(null);
const galleryCaption = ref("");
const workCaption = ref("");
const selectedServiceId = ref<number | null>(null);
const selectedSalonId = ref<number | null>(null);
const selectedCategoryId = ref<number | null>(null);
const serviceToAddId = ref<number | null>(null);
const serviceSearchOptions = ref<{ label: string; value: number }[]>([]);
const section = ref<"profile" | "gallery" | "services" | "works">("profile");
const salonOptions = computed(
  () =>
    profile.value?.salons.map((item) => ({
      label: item.name,
      value: item.id,
    })) ?? [],
);
const categoryOptions = computed(
  () =>
    profile.value?.service_categories
      .filter((item) => item.salon_id === selectedSalonId.value)
      .map((item) => ({
        label: item.title,
        value: item.id,
      })) ?? [],
);
const categoryAssignments = computed(
  () =>
    profile.value?.assignments.filter(
      (item) =>
        item.salon_id === selectedSalonId.value &&
        item.category_id === selectedCategoryId.value,
    ) ?? [],
);
const serviceOptions = computed(
  () =>
    profile.value?.services.map((item) => ({
      label: item.title,
      value: item.id,
    })) ?? [],
);

async function telegramWebApp(): Promise<TelegramWebApp | undefined> {
  if (!(window as Window & { Telegram?: unknown }).Telegram) {
    await new Promise<void>((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "https://telegram.org/js/telegram-web-app.js";
      script.onload = () => resolve();
      script.onerror = () => reject(new Error("Telegram SDK unavailable"));
      document.head.appendChild(script);
    });
  }
  return (window as Window & { Telegram?: { WebApp?: TelegramWebApp } })
    .Telegram?.WebApp;
}

async function refresh(): Promise<void> {
  profile.value = await fetchMiniAppProfile(initData.value);
  bioDraft.value = profile.value.bio;
  contentDraft.value = profile.value.content;
  if (!profile.value.salons.some((item) => item.id === selectedSalonId.value)) {
    selectedSalonId.value = profile.value.salons[0]?.id ?? null;
  }
  if (
    !categoryOptions.value.some(
      (item) => item.value === selectedCategoryId.value,
    )
  ) {
    selectedCategoryId.value = categoryOptions.value[0]?.value ?? null;
  }
}

onMounted(async () => {
  try {
    // Telegram includes signed launch data in the URL fragment. Read it before
    // loading the optional UI SDK so a blocked telegram.org script cannot
    // prevent the private profile request.
    const launchParams = new URLSearchParams(window.location.hash.slice(1));
    initData.value = launchParams.get("tgWebAppData") || "";
    if (!initData.value) {
      const app = await telegramWebApp().catch(() => undefined);
      initData.value = app?.initData || "";
    }
    if (!initData.value) {
      error.value =
        "Telegram не передал данные входа. Откройте кабинет кнопкой в личном чате с ботом.";
      return;
    }
    void telegramWebApp()
      .then((app) => {
        app?.ready();
        app?.expand();
      })
      .catch(() => undefined);
    await refresh();
  } catch (cause) {
    error.value = miniAppError(cause);
  } finally {
    loading.value = false;
  }
});

async function saveBio(): Promise<void> {
  busy.value = true;
  error.value = "";
  notice.value = "";
  try {
    await saveMiniAppBio(initData.value, bioDraft.value);
    await refresh();
    notice.value = "Описание сохранено.";
  } catch (cause) {
    error.value = miniAppError(cause);
  } finally {
    busy.value = false;
  }
}

async function saveContent(): Promise<void> {
  busy.value = true;
  error.value = "";
  notice.value = "";
  try {
    await saveMiniAppContent(initData.value, contentDraft.value);
    await refresh();
    notice.value = "Страница сохранена.";
  } catch (cause) {
    error.value = miniAppError(cause);
  } finally {
    busy.value = false;
  }
}

function onSalonChanged(): void {
  selectedCategoryId.value = categoryOptions.value[0]?.value ?? null;
  onCategoryChanged();
}

function onCategoryChanged(): void {
  serviceToAddId.value = null;
  serviceSearchOptions.value = [];
}

async function filterAvailableServices(
  value: string,
  update: (callback: () => void) => void,
): Promise<void> {
  const salonId = selectedSalonId.value;
  const categoryId = selectedCategoryId.value;
  if (!salonId || !categoryId || value.trim().length < 2) {
    update(() => {
      serviceSearchOptions.value = [];
    });
    return;
  }
  try {
    const results = await searchMiniAppServices(
      initData.value,
      salonId,
      categoryId,
      value.trim(),
    );
    update(() => {
      serviceSearchOptions.value =
        selectedSalonId.value === salonId &&
        selectedCategoryId.value === categoryId
          ? results.map((item) => ({
              value: item.id,
              label: item.title,
            }))
          : [];
    });
  } catch (cause) {
    update(() => {
      serviceSearchOptions.value = [];
    });
    error.value = miniAppError(cause);
  }
}

async function addService(): Promise<void> {
  if (!selectedSalonId.value || !serviceToAddId.value) return;
  busy.value = true;
  error.value = "";
  notice.value = "";
  try {
    await addMiniAppService(
      initData.value,
      selectedSalonId.value,
      serviceToAddId.value,
    );
    serviceToAddId.value = null;
    serviceSearchOptions.value = [];
    await refresh();
    notice.value = "Услуга добавлена.";
  } catch (cause) {
    error.value = miniAppError(cause);
  } finally {
    busy.value = false;
  }
}

async function removeService(
  assignmentId: number,
  title: string,
): Promise<void> {
  if (!window.confirm(`Убрать услугу «${title}» из ваших услуг?`)) return;
  busy.value = true;
  error.value = "";
  notice.value = "";
  try {
    await removeMiniAppService(initData.value, assignmentId);
    await refresh();
    notice.value = "Услуга убрана.";
  } catch (cause) {
    error.value = miniAppError(cause);
  } finally {
    busy.value = false;
  }
}

async function upload(kind: "profile" | "gallery" | "work"): Promise<void> {
  const file =
    kind === "profile"
      ? profileFile.value
      : kind === "gallery"
        ? galleryFile.value
        : workFile.value;
  if (!file || file.size > 10_000_000) {
    error.value = "Выберите изображение до 10 МБ.";
    return;
  }
  if (kind === "work" && !selectedServiceId.value) return;
  busy.value = true;
  error.value = "";
  notice.value = "";
  try {
    await uploadMiniAppPhoto(
      initData.value,
      kind,
      file,
      selectedServiceId.value ?? undefined,
      kind === "gallery" ? galleryCaption.value : workCaption.value,
    );
    await refresh();
    profileFile.value = null;
    galleryFile.value = null;
    workFile.value = null;
    galleryCaption.value = "";
    workCaption.value = "";
    notice.value = "Фотография загружена.";
  } catch (cause) {
    error.value = miniAppError(cause);
  } finally {
    busy.value = false;
  }
}
</script>

<style scoped>
.mini-app {
  background: #f7f7f5;
  min-height: 100vh;
}
.mini-app-header {
  border-bottom: 1px solid #e7e7e5;
}
.mini-app-brand-logo {
  display: block;
  flex: none;
  object-fit: contain;
}
.mini-app-content {
  max-width: 720px;
  margin: 0 auto;
}
.mini-app-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}
</style>
