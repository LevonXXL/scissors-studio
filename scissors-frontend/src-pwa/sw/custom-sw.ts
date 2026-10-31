/*
 * This file (which will be your service worker)
 * is picked up by the build system ONLY if
 * quasar.config file > pwa > workboxMode is set to "InjectManifest"
 */

import { clientsClaim } from "workbox-core";
import type { WorkboxPlugin } from "workbox-core";
import { NavigationRoute, registerRoute } from "workbox-routing";
import {
  cleanupOutdatedCaches,
  PrecacheFallbackPlugin,
  precacheAndRoute
} from "workbox-precaching";
import { NetworkOnly } from "workbox-strategies";

declare const self: ServiceWorkerGlobalScope & typeof globalThis;

void self.skipWaiting();
clientsClaim();

// Use with precache injection
precacheAndRoute(self.__WB_MANIFEST);

cleanupOutdatedCaches();

self.addEventListener('push', (event) => {
  let payload: { title?: string; body?: string; url?: string } = {};
  try { payload = event.data?.json() || {}; } catch { /* Invalid payload shows a generic notice. */ }
  event.waitUntil(self.registration.showNotification(payload.title || 'Scissors Studio', {
    body: payload.body || 'Новое уведомление',
    data: { url: payload.url || '/' },
  }));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const target = new URL(event.notification.data?.url || '/', self.location.origin);
  if (target.origin !== self.location.origin) return;
  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    const existing = windows.find((client) => client.url === target.href);
    if (existing) return existing.focus();
    return self.clients.openWindow(target.href);
  })());
});

if (import.meta.env.QUASAR_PROD) {
  // Online navigations must reach SSR. The precached shell is for offline use.
  registerRoute(
    new NavigationRoute(
      new NetworkOnly({
        plugins: [new PrecacheFallbackPlugin({
          fallbackURL: import.meta.env.QUASAR_PWA_FALLBACK_HTML,
        }) as WorkboxPlugin],
      }),
      {
        denylist: [
          new RegExp(import.meta.env.QUASAR_PWA_SERVICE_WORKER_REGEX),
          /workbox-(.)*\.js$/
        ]
      }
    )
  );
}
