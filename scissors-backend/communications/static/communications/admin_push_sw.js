self.addEventListener('push', (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch (_) { data = {}; }
  event.waitUntil(self.registration.showNotification(data.title || 'Scissors Studio', {
    body: data.body || 'Новое уведомление',
    data: { url: data.url || '/admin/' },
  }));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const target = new URL(event.notification.data?.url || '/admin/', self.location.origin);
  if (target.origin !== self.location.origin || !target.pathname.startsWith('/admin/')) return;
  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    const existing = windows.find((client) => client.url === target.href);
    if (existing) return existing.focus();
    return self.clients.openWindow(target.href);
  })());
});
