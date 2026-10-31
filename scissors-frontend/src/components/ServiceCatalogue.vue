<template>
  <section class="service-catalogue">
    <div v-if="mode === 'category'" class="catalogue-category-hero"
      :class="{ 'catalogue-category-hero--text-only': !category?.image_url }">
      <div class="catalogue-category-hero__copy">
        <h1>{{ category?.title || pageTitle }}</h1>
        <div v-if="pageContent" class="page-content" v-html="pageContent" />
        <p>Наша задача - создать тот образ, который будет соответствовать вашему восприятию себя, образу жизни и задачам.</p>
        <template v-if="availableSalons.length > 1">
          <p>Цены отличаются в разных салонах, выберите сначала салон, затем услугу и мастера или свяжитесь с нами и мы поможем.</p>
          <p>Категорию выбранного мастера смотрите в карточке мастера.</p>
        </template>
      </div>
      <img v-if="category?.image_url" class="catalogue-category-hero__image"
        :src="mediaPreviewUrl(category.image_url, 400)" :alt="category.title" />
    </div>
    <div v-if="mode !== 'root' && availableSalons.length > 1" class="row q-gutter-sm q-my-lg">
      <q-btn v-for="salon in availableSalons" :key="salon.id" no-caps
        :outline="selectedSalon !== salonKey(salon)" color="primary" :label="salon.name"
        @click="selectSalon(salon)" />
    </div>
    <p v-else-if="mode !== 'root' && availableSalons.length === 1" class="q-my-lg">
      Цены приведены для салона «{{ availableSalons[0]?.name }}».
    </p>
    <div v-if="mode === 'root'" class="catalogue-grid">
      <router-link v-for="category in categories" :key="category.id" class="catalogue-card"
        :to="`/${category.url_path}`">
        <img v-if="category.image_url" :src="mediaPreviewUrl(category.image_url, 400)" :alt="category.title" />
        <h2>{{ category.title }}</h2>
      </router-link>
    </div>
    <template v-else-if="category">
      <p v-if="!category.services.length" class="q-mt-lg">Для выбранного салона услуги этого раздела пока не опубликованы.</p>
      <q-list v-if="groups.length" :bordered="groups.length > 1" :separator="groups.length > 1"
        class="rounded-borders q-mt-lg">
        <component :is="groups.length > 1 ? QExpansionItem : 'div'" v-for="group in groups"
          :key="`${props.path}/${group.name}`" v-bind="groups.length > 1 ? {
            label: group.name || category.title,
            modelValue: serviceStore.isGroupOpen(props.path, group.name, mode === 'service'),
            'onUpdate:modelValue': (open: boolean) => serviceStore.setGroupOpen(props.path, group.name, open),
            headerClass: 'catalogue-group-header text-h6 text-weight-medium',
            expandIconClass: 'text-white',
          } : {}">
          <q-card flat><q-card-section>
            <h2 v-if="groups.length === 1 && group.name" class="text-h5 q-mt-none q-mb-md">{{ group.name }}</h2>
            <template v-for="subgroup in group.subgroups" :key="subgroup.name">
              <h3 v-if="subgroup.name" class="text-h6 q-mt-lg q-mb-sm">{{ subgroup.name }}</h3>
              <article v-for="service in subgroup.services" :key="service.id" class="catalogue-service">
                <button v-if="service.image && mode !== 'service'" type="button"
                  class="catalogue-service__image-button" :aria-label="`Открыть фото услуги «${service.title}»`"
                  @click="openImage(service.image, service.title)">
                  <img class="catalogue-service__image"
                    :src="mediaPreviewUrl(service.image, 400)" :alt="service.title" loading="lazy" />
                </button>
                <div class="catalogue-service__details">
                  <h4 class="text-subtitle1 text-weight-medium q-my-sm">{{ service.title }}</h4>
                  <p v-if="service.description">{{ service.description }}</p>
                  <p v-if="service.duration_display" class="text-grey-7">{{ service.duration_display }}</p>
                  <div v-if="service.prices.length" class="price-grid">
                    <div v-for="price in service.prices" :key="price.level">
                      <div class="text-caption text-grey-7">{{ levelLabel(price.level) }}</div>
                      <strong class="text-primary">{{ formatPrice(price.amount) }} ₽</strong>
                    </div>
                  </div>
                  <p v-if="service.conditions" class="q-mt-md" style="white-space:pre-line">{{ service.conditions }}</p>
                  <p v-if="service.masters.length" class="text-caption q-mt-md">
                    Специалисты: <span v-for="(master, index) in service.masters" :key="master.id">{{ index ? ', ' : '' }}{{ master.name }}<span v-if="master.amount !== null"> — {{ formatPrice(master.amount) }} ₽</span><span v-else> — цена для мастера уточняется</span></span>
                  </p>
                  <div class="row q-gutter-sm q-mt-md">
                    <q-btn v-if="mode !== 'service'" flat no-caps color="primary" label="Подробнее" :to="`/${service.url_path}`" />
                    <q-btn v-if="selectedSalonRecord" no-caps color="primary" label="Онлайн-запись"
                      :href="salonBookingUrl(selectedSalonRecord)" target="_blank" rel="noopener noreferrer" />
                  </div>
                </div>
              </article>
            </template>
          </q-card-section></q-card>
        </component>
      </q-list>
    </template>
    <p v-else-if="!loading" class="q-mt-lg">Услуги этого раздела пока не опубликованы.</p>
    <div v-if="loading" class="text-center q-pa-lg"><q-spinner color="primary" /></div>
    <section v-if="mode === 'category' && category && !loading" class="catalogue-feedback" aria-labelledby="catalogue-feedback-title">
      <img :src="publicAssetUrl('/img/home/feedback.png')"
        alt="" loading="lazy" />
      <div class="catalogue-feedback__form">
        <h2 id="catalogue-feedback-title">Нужна консультация?</h2>
        <p>Оставьте заявку, ваш бьюти-ассистент свяжется с вами.</p>
        <FeedbackRequestForm />
      </div>
    </section>
    <ImageLightbox v-model="lightboxOpen" :images="lightboxImages" />
  </section>
</template>

<script setup lang="ts">
import { computed, onServerPrefetch, watch, onMounted, ref } from 'vue';
import { QExpansionItem } from 'quasar';
import { useServiceCatalogStore } from '@/stores/serviceCatalog';
import { useSalonStore, type SalonSlug } from '@/stores/salon';
import { mediaImageUrl, mediaPreviewUrl, publicAssetUrl } from '@/config/urls';
import { salonBookingUrl } from '@/utils/yclientsBooking';
import FeedbackRequestForm from '@/components/FeedbackRequestForm.vue';
import ImageLightbox from '@/components/ImageLightbox.vue';

interface Price { level: string; amount: string }
interface MasterPrice { id: number; name: string; level: string; amount: string | null }
interface Service { id: number; title: string; description: string; group_title: string; subgroup_title: string; conditions: string; duration_display: string; url_path: string; image: string; prices: Price[]; masters: MasterPrice[] }
interface Category { id: number; title: string; code: string; image_url: string; group_images: { name: string; url: string }[]; url_path: string; services: Service[] }
interface Salon { id: number; name: string; slug: string; yclients_booking_url: string }

const props = defineProps<{ path: string; pageTitle?: string; pageContent?: string }>();
const salonStore = useSalonStore();
const serviceStore = useServiceCatalogStore();

const salons = computed(() => serviceStore.salons);
const categories = computed(() => serviceStore.rootCategories);
const salonCatalogues = computed(() => serviceStore.salonCatalogues);
const loading = computed(() => serviceStore.loading);
const lightboxOpen = ref(false);
const lightboxImages = ref<{ src: string; alt: string }[]>([]);

function openImage(source: string, alt: string) {
  lightboxImages.value = [{ src: mediaImageUrl(source), alt }];
  lightboxOpen.value = true;
}

const segments = computed(() => props.path.split('/').filter(Boolean));
const mode = computed(() => segments.value.length < 2 ? 'root' : segments.value.length === 2 ? 'category' : 'service');
const selectedSalon = computed(() => salonStore.selectedSalonSlug || 'moscow');
const salonKey = (salon: Salon): SalonSlug | null => {
  if (salon.slug.includes('zelenograd')) return 'zelenograd';
  if (salon.slug.includes('krasnye-vorota')) return 'moscow';
  return null;
};
const selectableSalons = computed(() => salons.value.filter(s => salonKey(s) !== null));
const categoryPath = computed(() => segments.value.slice(0, 2).join('/'));
const availableSalonEntries = computed(() => salonCatalogues.value.filter(({ categories: items }) => {
  const item = items.find(c => c.url_path === categoryPath.value);
  return item && (mode.value !== 'service' || item.services.some(s => s.url_path === props.path));
}));
const availableSalons = computed(() => availableSalonEntries.value.map(entry => entry.salon));
const selectedSalonRecord = computed(() =>
  availableSalons.value.find(s => salonKey(s) === selectedSalon.value) || availableSalons.value[0],
);
function selectSalon(salon: Salon) {
  const key = salonKey(salon);
  if (key) salonStore.setSalon(key);
}
const category = computed(() => availableSalonEntries.value
  .find(entry => entry.salon.id === selectedSalonRecord.value?.id)
  ?.categories.find(c => c.url_path === categoryPath.value));
const services = computed(() => mode.value === 'service'
  ? category.value?.services.filter(s => s.url_path === props.path) || []
  : category.value?.services || []);
const groups = computed(() => {
  const result: { name: string; subgroups: { name: string; services: Service[] }[] }[] = [];
  for (const service of services.value) {
    let group = result.find(g => g.name === service.group_title);
    if (!group) {
      group = {
        name: service.group_title,
        subgroups: [],
      };
      result.push(group);
    }
    let subgroup = group.subgroups.find(g => g.name === service.subgroup_title);
    if (!subgroup) { subgroup = { name: service.subgroup_title, services: [] }; group.subgroups.push(subgroup); }
    subgroup.services.push(service);
  }
  return result;
});
const labels: Record<string, string> = { universal: 'Универсал', modeler: 'Модельер', stylist: 'Стилист', top_stylist: 'Топ-стилист', art_director: 'Арт-директор', nail_master: 'Мастер', top_nail_master: 'Топ-мастер', '': 'Стоимость' };
const levelLabel = (level: string) => labels[level] || level;
const formatPrice = (value: string | null) => value == null ? '' : Number(value).toLocaleString('ru-RU', { maximumFractionDigits: 0 });

// Route preFetch fills Pinia before SSR rendering and client navigation.
onServerPrefetch(() => serviceStore.loadForPath(props.path));

// Переход между страницами при изменении props.path.
watch(
  () => props.path,
  (path) => {
    void serviceStore.loadForPath(path).catch((error) => {
      console.error('Не удалось загрузить каталог услуг:', error);
    });
  },
);

// Also supports a client-only offline shell; hydrated SSR state makes this a no-op.
onMounted(() => {
  void serviceStore.loadForPath(props.path).catch((error) => {
    console.error('Не удалось загрузить каталог услуг:', error);
  });
});
</script>

<style scoped>
.catalogue-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
.catalogue-card { color: inherit; text-decoration: none; background: #f4efed; }
.catalogue-card img { display: block; width: 100%; aspect-ratio: 4 / 5; object-fit: cover; }
.catalogue-card h2 { font-size: 22px; margin: 18px; }
.catalogue-category-hero { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 42%); gap: clamp(24px, 5vw, 72px); align-items: center; margin: 24px 0 48px; }
.catalogue-category-hero--text-only { grid-template-columns: 1fr; }
.catalogue-category-hero__copy { max-width: 620px; font-size: 18px; line-height: 1.6; }
.catalogue-category-hero__copy h1 { margin: 0 0 32px; }
.catalogue-category-hero__copy p { margin: 0 0 20px; }
.catalogue-category-hero__copy :deep(.page-content > :last-child) { margin-bottom: 20px; }
.catalogue-category-hero__image { display: block; width: 100%; aspect-ratio: 4 / 5; object-fit: cover; }
.catalogue-feedback { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); margin: 96px 0 32px; background: #f0f0f0; }
.catalogue-feedback > img { display: block; width: 100%; height: 100%; min-height: 520px; object-fit: cover; }
.catalogue-feedback__form { padding: clamp(24px, 4vw, 64px); }
.catalogue-feedback__form h2 { margin: 0 0 12px; text-transform: uppercase; }
.catalogue-feedback__form > p { margin: 0 0 32px; }
:deep(.catalogue-group-header) { background: var(--q-primary); color: #fff; }
.catalogue-service { display: grid; grid-template-columns: minmax(160px, 28%) minmax(0, 1fr); gap: 24px; }
.catalogue-service__image-button { display: block; width: 100%; padding: 0; border: 0; background: none; cursor: zoom-in; align-self: start; }
.catalogue-service__image-button:focus-visible { outline: 3px solid var(--q-primary); outline-offset: 2px; }
.catalogue-service__image { display: block; width: 100%; aspect-ratio: 4 / 3; object-fit: cover; border-radius: 4px; }
.catalogue-service__details { grid-column: 2; min-width: 0; }
.catalogue-service__details:first-child { grid-column: 1 / -1; }
.catalogue-service + .catalogue-service { border-top: 1px solid #e4dfdc; margin-top: 20px; padding-top: 20px; }
.price-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; border-top: 1px solid #e4dfdc; margin-top: 20px; padding-top: 16px; }
@media (max-width: 700px) {
  .catalogue-grid, .price-grid, .catalogue-service, .catalogue-category-hero, .catalogue-feedback { grid-template-columns: 1fr; }
  .catalogue-service__details { grid-column: 1; }
  .catalogue-category-hero { margin-bottom: 32px; }
  .catalogue-category-hero__copy { font-size: 16px; }
  .catalogue-feedback { margin-top: 56px; }
  .catalogue-feedback > img { height: 320px; min-height: 0; }
}
</style>
