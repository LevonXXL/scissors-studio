import { ApiError } from '@/api/client';
import { deletePushSubscription, getPushPublicKey, savePushSubscription, setPushPreference } from '@/api/endpoints';

export type BrowserPushPermission = NotificationPermission | 'unsupported';

export function browserPushPermission(): BrowserPushPermission {
  if (typeof window === 'undefined' || !('Notification' in window) || !('PushManager' in window) || !('serviceWorker' in navigator)) {
    return 'unsupported';
  }
  return Notification.permission;
}

function keyBytes(value: string): Uint8Array<ArrayBuffer> {
  const base64 = (value + '='.repeat((4 - value.length % 4) % 4)).replace(/-/g, '+').replace(/_/g, '/');
  return Uint8Array.from(atob(base64), (char) => char.charCodeAt(0));
}

async function registration(): Promise<ServiceWorkerRegistration> {
  if (browserPushPermission() === 'unsupported') throw new Error('Этот браузер не поддерживает push-уведомления.');
  const existing = await navigator.serviceWorker.getRegistration();
  if (!existing) throw new Error('Push доступен после установки PWA-версии сайта.');
  return navigator.serviceWorker.ready;
}

export async function enableBrowserPush(): Promise<void> {
  const serviceWorker = await registration();
  const publicKey = await getPushPublicKey();
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') throw new Error('Разрешите уведомления в настройках браузера.');
  let subscription = await serviceWorker.pushManager.getSubscription();
  if (!subscription) {
    subscription = await serviceWorker.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(publicKey) });
  }
  await setPushPreference(true);
  try {
    await savePushSubscription(subscription);
  } catch (cause) {
    if (cause instanceof ApiError && cause.status === 409) {
      await subscription.unsubscribe();
      subscription = await serviceWorker.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(publicKey) });
      await savePushSubscription(subscription);
      return;
    }
    throw cause;
  }
}

export async function disableBrowserPush(): Promise<void> {
  await setPushPreference(false);
  if (browserPushPermission() === 'unsupported') return;
  const serviceWorker = await navigator.serviceWorker.getRegistration();
  const subscription = await serviceWorker?.pushManager.getSubscription();
  if (subscription) {
    try { await subscription.unsubscribe(); } catch { /* Server preference is already disabled. */ }
  }
}

export async function removeCurrentBrowserSubscription(): Promise<void> {
  if (browserPushPermission() === 'unsupported') return;
  const serviceWorker = await navigator.serviceWorker.getRegistration();
  const subscription = await serviceWorker?.pushManager.getSubscription();
  if (!subscription) return;
  try { await deletePushSubscription(subscription); } catch { /* Unsubscribe locally even if the server is offline. */ }
  try { await subscription.unsubscribe(); } catch { /* Expired subscriptions are removed after push-provider 404/410. */ }
}
