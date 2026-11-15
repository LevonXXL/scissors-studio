import type { RouteRecordRaw } from "vue-router";

// Old YCLIENTS duplicate slugs remain usable after normalize_master_urls.
const legacyMasterRedirects = [
  ['anna-vreneva-2', 'anna-vreneva'],
  ['denis-petrov-3', 'denis-petrov'],
  ['diana-2', 'diana'],
  ['gadeliya-kotelova-3', 'gadeliya-kotelova'],
  ['irina-bludova-2', 'irina-bludova'],
  ['lana-apostolova-2', 'lana-apostolova'],
  ['marina-kolchanova-2', 'marina-kolchanova'],
  ['mariya-kim-2', 'mariya-kim'],
  ['mihail-stets-3', 'mihail-stets'],
  ['oksana-rysovets-2', 'oksana-rysovets'],
  ['petr-cheban-2', 'petr-cheban'],
  ['rekrut-polina-3', 'rekrut-polina'],
  ['svetlana-mironova-2', 'svetlana-mironova'],
  ['vera-muhtarova-3', 'vera-muhtarova'],
  ['vyatchanina-olga-3', 'vyatchanina-olga'],
  ['yuliya-svetskaya-2', 'yuliya-svetskaya'],
].map(([oldSlug, newSlug]) => ({ path: `team/${oldSlug}`, redirect: `/team/${newSlug}` }));

const routes: RouteRecordRaw[] = [
  {
    path: "/master-app",
    component: () => import("@/pages/MasterMiniAppPage.vue"),
  },
  {
    path: "/",
    component: () => import("@/layouts/MainLayout.vue"),
    children: [
      { path: "", component: () => import("@/pages/HomePage.vue") },
      { path: "about", component: () => import("@/pages/AboutPage.vue") },
      { path: "team", component: () => import("@/pages/TeamPage.vue") },
      { path: "salons", component: () => import("@/pages/SalonsPage.vue") },
      {
        path: "salons/:slug",
        component: () => import("@/pages/SalonPage.vue"),
        props: true,
      },
      { path: "moscow", redirect: "/salons/moscow" },
      { path: "zelenograd", redirect: "/salons/zelenograd" },
      { path: "price-list", redirect: "/uslugi" },
      { path: "price-list_zelenograd", redirect: "/uslugi" },
      { path: "services/:pathMatch(.*)*", redirect: "/uslugi" },
      ...legacyMasterRedirects,
      { path: "vacancy", component: () => import("@/pages/VacancyPage.vue") },
      { path: "policy", redirect: "/privacy" },
      { path: "login", component: () => import("@/pages/AuthPage.vue") },
      { path: "booking", component: () => import("@/pages/BookingPage.vue") },
      { path: "search", component: () => import("@/pages/SearchPage.vue") },

      // Каталог CMS-страниц (этап 2 — контент из DRF). Обязательно последний
      // среди children — ловит всё, что не покрыто явными маршрутами выше.
      {
        path: ":pathMatch(.*)*",
        component: () => import("@/pages/PageView.vue"),
      },
    ],
  },

  {
    path: "/:catchAll(.*)*",
    component: () => import("@/pages/ErrorNotFound.vue"),
  },
];

export default routes;
