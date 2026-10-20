import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    children: [
      { path: '', component: () => import('@/pages/HomePage.vue') },
      { path: 'about', component: () => import('@/pages/AboutPage.vue') },
      { path: 'team', component: () => import('@/pages/TeamPage.vue') },
      { path: 'salons', component: () => import('@/pages/SalonsPage.vue') },
      { path: 'salons/:slug', component: () => import('@/pages/SalonPage.vue'), props: true },
      { path: 'moscow', redirect: '/salons/moscow' },
      { path: 'zelenograd', redirect: '/salons/zelenograd' },
      { path: 'price-list', component: () => import('@/pages/PriceListPage.vue') },
      { path: 'price-list_zelenograd', component: () => import('@/pages/PriceListPage.vue') },
      { path: 'vacancy', component: () => import('@/pages/VacancyPage.vue') },
      { path: 'policy', redirect: '/privacy' },
      { path: 'login', component: () => import('@/pages/AuthPage.vue') },
      { path: 'uslugi/:slug', component: () => import('@/pages/ServicePage.vue') },

      // Каталог CMS-страниц (этап 2 — контент из DRF). Обязательно последний
      // среди children — ловит всё, что не покрыто явными маршрутами выше.
      { path: ':pathMatch(.*)*', component: () => import('@/pages/PageView.vue') },
    ],
  },

  {
    path: '/:catchAll(.*)*',
    component: () => import('@/pages/ErrorNotFound.vue'),
  },
];

export default routes;
