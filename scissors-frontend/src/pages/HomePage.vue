<template>
  <q-page class="home-page">
    <section class="home-hero">
      <div class="site-page home-hero__inner">
        <div class="home-hero__copy">
          <div class="home-eyebrow">СЕТЬ САЛОНОВ КРАСОТЫ SCISSORS STUDIO —</div>
          <h1>{{ homeTitle }}</h1>
          <p>{{ homeIntro }}</p>
          <q-btn unelevated no-caps label="Онлайн-запись" :href="YCLIENTS_NETWORK_BOOKING_URL"
            target="_blank" rel="noopener noreferrer" class="home-button" />
        </div>
        <img class="home-hero__image" :src="publicAssetUrl('/img/home/hero.png')" alt="Образ Scissors Studio" />
      </div>
    </section>

    <section class="site-page home-section" aria-labelledby="services-heading">
      <div class="services-grid">
        <div class="services-intro">
          <div class="home-eyebrow">Услуги</div>
          <h2 id="services-heading">Всё для вашей красоты в одном месте</h2>
          <q-btn outline no-caps label="Ко всем услугам" to="/uslugi" class="home-button home-button--outline" />
        </div>
        <router-link v-for="service in homeServices" :key="service.id" :to="`/${service.url_path}`" class="service-card">
          <img :src="service.image_url ? mediaPreviewUrl(service.image_url, 400) : publicAssetUrl(service.image_path)" :alt="service.title" loading="lazy" />
          <div class="service-card__copy">
            <h3>{{ service.title }}</h3>
            <p>{{ service.meta_description }}</p>
          </div>
        </router-link>
      </div>
    </section>

    <section class="site-page home-section" aria-labelledby="works-heading">
      <div class="home-section__heading">
        <div class="home-eyebrow">Примеры работ</div>
        <h2 id="works-heading">Примеры работ наших мастеров</h2>
        <router-link to="/team" class="home-text-link">Команда и портфолио →</router-link>
      </div>
      <div class="image-grid image-grid--works">
        <img v-for="(image, index) in workImages" :key="image" :src="publicAssetUrl(image)" :alt="`Работа мастера Scissors Studio ${index + 1}`" loading="lazy" />
      </div>
    </section>

    <section class="site-page home-section" aria-labelledby="popular-heading">
      <div class="home-section__heading">
        <div class="home-eyebrow">Востребованные услуги</div>
        <h2 id="popular-heading">Востребованные услуги</h2>
        <router-link to="/uslugi" class="home-text-link">Все услуги и цены →</router-link>
      </div>
      <div class="image-grid image-grid--popular">
        <router-link v-for="(image, index) in popularImages" :key="image" to="/uslugi/hair" :aria-label="`Услуги для волос — пример ${index + 1}`">
          <img :src="publicAssetUrl(image)" :alt="`Пример востребованной услуги ${index + 1}`" loading="lazy" />
        </router-link>
      </div>
    </section>

    <section class="site-page home-about" aria-labelledby="about-heading">
      <div class="home-about__copy" :style="{ '--home-about-image': `url('${publicAssetUrl('/img/home/about.png')}')` }">
        <div class="home-eyebrow">О компании</div>
        <h2 id="about-heading">Scissors это</h2>
        <p>Более 11 лет мы создаём пространство, где красота и здоровье соединяются с вашим стилем жизни. В основе — лучшие мировые технологии, команда мастеров международного уровня и строгий отбор продуктов, проходящий лишь 20% средств.</p>
        <router-link to="/about" class="home-text-link">О нас →</router-link>
      </div>
      <div class="home-about__stats">
        <div v-for="stat in stats" :key="stat.label"><strong>{{ stat.value }}</strong><span>{{ stat.label }}</span></div>
      </div>
    </section>

    <section class="site-page home-section" aria-labelledby="advantages-heading">
      <div class="home-section__heading">
        <div class="home-eyebrow">О нас</div>
        <h2 id="advantages-heading">Преимущества</h2>
      </div>
      <div class="advantages-grid">
        <div v-for="item in advantages" :key="item.title" class="advantage">
          <h3>{{ item.title }}</h3>
          <img :src="publicAssetUrl(item.icon)" alt="" loading="lazy" />
          <p>{{ item.description }}</p>
        </div>
      </div>
    </section>

    <ReviewsSection title="Отзывы салона" with-images-only />

    <section class="site-page home-consultation" aria-labelledby="consultation-heading">
      <img :src="publicAssetUrl('/img/home/feedback.png')" alt="" loading="lazy" />
      <div>
        <h2 id="consultation-heading">Нужна консультация?</h2>
        <p>Оставьте заявку, ваш бьюти-ассистент свяжется с вами</p>
<!--        <q-btn unelevated no-caps label="Оставить заявку" class="home-button" @click="consultationOpen = true" />-->
        <FeedbackRequestForm />
      </div>
    </section>
    <ConsultationDialog v-model="consultationOpen" />
  </q-page>
</template>

<script lang="ts">
import { definePreFetch } from '#q-app';
import { usePagesStore } from '@/stores/pages-store';
import { useServiceCatalogStore } from '@/stores/serviceCatalog';
import { useSalonsStore } from '@/stores/salons';
import { useReviewsStore } from '@/stores/reviews';

export default {
  preFetch: definePreFetch(async ({ store }) => {
    await Promise.all([
      usePagesStore(store).load(''),
      useServiceCatalogStore(store).loadRootCategories(),
      useSalonsStore(store).loadList(),
      useReviewsStore(store).load({ withImages: true }),
    ]);
  }),
};
</script>

<script setup lang="ts">
import { useMeta } from 'quasar';
import { computed, ref } from 'vue';
import { advantages, popularImages, stats, workImages } from '@/data/home';
import ConsultationDialog from '@/components/ConsultationDialog.vue';
import ReviewsSection from '@/components/ReviewsSection.vue';
import { mediaPreviewUrl, publicAssetUrl } from '@/config/urls';
import { YCLIENTS_NETWORK_BOOKING_URL } from '@/utils/yclientsBooking';
import FeedbackRequestForm from "@/components/FeedbackRequestForm.vue";

const fallbackTitle = 'Стратегический подход к вашему образу';
const fallbackIntro = 'У нас можно полностью довериться профессионалам: персональная бьюти-стратегия, современный подход и точность исполнения гарантируют естественный, уверенный и безупречный результат.';
const pagesStore = usePagesStore();
const homePage = computed(() => pagesStore.byPath[''] ?? null);
const homeTitle = computed(() => homePage.value?.title && homePage.value.title !== 'Главная' ? homePage.value.title : fallbackTitle);
const homeIntro = computed(() => {
  const content = homePage.value?.content?.trim();
  if (!content) return fallbackIntro;
  // До обновления БД содержимое главной может храниться старой HTML-разметкой.
  const paragraph = content.match(/<p\b[^>]*>([\s\S]*?)<\/p>/i)?.[1] ?? content;
  return paragraph.replace(/<[^>]*>/g, '').replace(/\s+/g, ' ').trim() || fallbackIntro;
});
const consultationOpen = ref(false);
const serviceCatalog = useServiceCatalogStore();
const homeServices = computed(() => serviceCatalog.rootCategories);

useMeta(() => ({
  title: homePage.value?.title_tag || `${fallbackTitle} — Scissors Studio`,
  meta: {
    description: {
      name: 'description',
      content: homePage.value?.meta_description || fallbackIntro,
    },
  },
}));
</script>

<style scoped>
.home-page { color: #25201e; }
.home-eyebrow { color: #8c2b12; font-size: 12px; font-weight: 600; letter-spacing: .12em; text-transform: uppercase; }
.home-hero { background: #fff; }
.home-hero__inner { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); min-height: 520px; }
.home-hero__copy { display: flex; flex-direction: column; align-items: flex-start; justify-content: center; min-width: 0; padding: 56px 48px 56px 16px; }
.home-hero h1 { max-width: 540px; margin: 20px 0 24px; font-size: clamp(34px, 4vw, 58px); line-height: 1.1; font-weight: 500; }
.home-hero p { max-width: 510px; margin: 0 0 24px; font-size: 17px; line-height: 1.6; }
.home-hero__image { display: block; width: 100%; max-width: 100%; min-width: 0; height: 100%; min-height: 520px; object-fit: cover; }
.home-button { background: #8c2b12 !important; color: #fff !important; }
.home-button:hover { background: #a54127 !important; }
.home-button--outline { background: transparent !important; color: #8c2b12 !important; }
.home-button--outline:hover { color: #fff !important; }
.home-section { padding: 64px 16px; }
.home-section__heading { display: flex; align-items: end; justify-content: space-between; flex-wrap: wrap; gap: 12px 24px; margin-bottom: 24px; }
.home-section__heading .home-eyebrow { width: 100%; }
.home-section h2, .home-about h2, .home-consultation h2 { margin: 0; font-size: clamp(28px, 3vw, 42px); line-height: 1.15; font-weight: 500; }
.home-text-link { color: #8c2b12; font-weight: 600; }
.services-grid { display: grid; grid-template-columns: repeat(12, 1fr); gap: 16px; }
.services-intro, .service-card { min-height: 350px; }
.services-intro { grid-column: span 4; display: flex; flex-direction: column; align-items: flex-start; justify-content: space-between; padding: 24px; background: #f4efed; }
.services-intro h2 { margin: auto 0 20px; }
.service-card { grid-column: span 4; position: relative; display: block; overflow: hidden; color: #fff; background: #8c2b12; }
.service-card:nth-child(n + 4) { grid-column: span 3; min-height: 300px; }
.service-card img { width: 100%; height: 100%; position: absolute; inset: 0; object-fit: cover; transition: transform .25s ease; }
.service-card:hover img { transform: scale(1.04); }
.service-card::after { content: ''; position: absolute; inset: 35% 0 0; background: linear-gradient(transparent, rgba(35, 15, 10, .85)); }
.service-card__copy { position: absolute; z-index: 1; left: 20px; right: 20px; bottom: 18px; }
.service-card h3 { margin: 0 0 6px; font-size: 22px; font-weight: 500; }
.service-card p { margin: 0; font-size: 13px; line-height: 1.35; }
.image-grid { display: grid; gap: 16px; }
.image-grid--works { grid-template-columns: repeat(4, 1fr); }
.image-grid--popular { grid-template-columns: repeat(3, 1fr); }
.image-grid img { display: block; width: 100%; aspect-ratio: 4 / 5; object-fit: cover; }
.home-about { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); margin-block: 64px; padding-inline: 16px; }
.home-about__copy { display: flex; flex-direction: column; align-items: flex-start; justify-content: flex-end; min-width: 0; min-height: 460px; padding: 36px; color: #fff; background: linear-gradient(90deg, rgba(32, 13, 10, .8), rgba(32, 13, 10, .42)), var(--home-about-image) center / cover no-repeat; }
.home-about__copy .home-eyebrow, .home-about__copy .home-text-link { color: #fff; }
.home-about__copy h2 { margin: 16px 0; }
.home-about__copy p { font-size: 16px; line-height: 1.65; }
.home-about__stats { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); align-content: center; gap: 24px; min-width: 0; padding: 36px; background: #f4efed; }
.home-about__stats div { display: flex; flex-direction: column; }
.home-about__stats strong { color: #8c2b12; font-size: 38px; line-height: 1.1; font-weight: 500; }
.home-about__stats span { font-size: 13px; }
.advantages-grid { display: grid; grid-template-columns: repeat(12, 1fr); gap: 28px; }
.advantage { grid-column: span 4; padding: 16px 0; border-top: 1px solid #d8c8c2; }
.advantage:nth-child(n + 4) { grid-column: span 3; }
.advantage h3 { margin: 0 0 16px; font-size: 17px; font-weight: 600; }
.advantage img { width: 40px; height: 40px; object-fit: contain; }
.advantage p { margin: 16px 0 0; font-size: 14px; line-height: 1.5; }
.home-consultation { display: grid; grid-template-columns: 42% 1fr; align-items: center; gap: 32px; padding: 64px 16px; }
.home-consultation img { width: 100%; max-height: 400px; object-fit: contain; }
.home-consultation p { font-size: 17px; }
@media (max-width: 900px) {
  .home-hero__inner { min-height: 0; }
  .home-hero__copy { padding-right: 24px; }
  .services-intro, .service-card, .service-card:nth-child(n + 4), .advantage, .advantage:nth-child(n + 4) { grid-column: span 6; }
  .image-grid--works { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 600px) {
  .home-hero__inner { grid-template-columns: minmax(0, 1fr); }
  .home-about, .home-consultation { grid-template-columns: 1fr; }
  .home-hero__copy { padding: 48px 16px; }
  .home-hero__image { min-height: 260px; max-height: 350px; }
  .home-section { padding-block: 48px; }
  .services-intro, .service-card, .service-card:nth-child(n + 4), .advantage, .advantage:nth-child(n + 4) { grid-column: span 12; }
  .services-intro { min-height: 220px; }
  .service-card, .service-card:nth-child(n + 4) { min-height: 320px; }
  .image-grid--popular { grid-template-columns: 1fr; }
  .home-about { margin-block: 48px; }
  .home-about__copy { min-height: 430px; padding: 24px; }
  .home-about__stats { padding: 24px; }
  .home-consultation { gap: 16px; padding-block: 48px; }
}

.advantages-grid .advantage {
  padding-left: 24px;
  box-sizing: border-box;
}

.advantages-grid .advantage:nth-child(even) {
  background-color: var(--q-primary);
  color: #fff;
}

.advantages-grid .advantage:nth-child(even) h3,
.advantages-grid .advantage:nth-child(even) p {
  color: #fff;
}

.advantages-grid .advantage:nth-child(even) img {
  filter: brightness(0) invert(1);
}
</style>
