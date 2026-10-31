import { defineStore } from 'pinia';
import { ref } from 'vue';

const STORAGE_KEY = 'scissors_cookie_consent';
const POLICY_VERSION = 1;
const CONSENT_TTL = 365 * 24 * 60 * 60 * 1000;
const counterId = Number(import.meta.env.VITE_YANDEX_METRIKA_ID || 0);

interface ConsentRecord {
  analytics: boolean;
  savedAt: number;
  version: number;
}

type MetrikaFunction = ((id: number, method: string, ...args: unknown[]) => void) & {
  a?: IArguments[];
  l?: number;
};

declare global {
  interface Window {
    ym?: MetrikaFunction;
  }
}

function validConsent(value: unknown): value is ConsentRecord {
  if (!value || typeof value !== 'object') return false;
  const record = value as Partial<ConsentRecord>;
  return record.version === POLICY_VERSION
    && typeof record.analytics === 'boolean'
    && typeof record.savedAt === 'number'
    && record.savedAt <= Date.now()
    && Date.now() - record.savedAt < CONSENT_TTL;
}

function clearMetrikaStorage(): void {
  const cookieNames = document.cookie.split(';').map((cookie) => cookie.trim().split('=')[0] || '')
    .filter((name) => name.startsWith('_ym_') || name === 'ymex');
  const host = window.location.hostname;
  const parent = host.split('.').slice(-2).join('.');
  for (const name of cookieNames) {
    for (const domain of ['', host, parent]) {
      document.cookie = `${name}=; Max-Age=0; Path=/${domain ? `; Domain=${domain}` : ''}`;
    }
  }
  for (const storage of [window.localStorage, window.sessionStorage]) {
    for (let index = storage.length - 1; index >= 0; index -= 1) {
      const key = storage.key(index);
      if (key?.startsWith('_ym_') || key === 'ymex') storage.removeItem(key);
    }
  }
}

export const useCookieStore = defineStore('cookies', () => {
  const consent = ref<ConsentRecord | null>(null);
  const showBanner = ref(false);
  const showModal = ref(false);
  const currentPath = ref('/');
  let scriptLoading = false;
  let scriptLoaded = false;
  let initialized = false;

  function hit(path: string): void {
    currentPath.value = path.startsWith('/') ? path.split(/[?#]/, 1)[0] || '/' : '/';
    if (!consent.value?.analytics || !initialized || !window.ym) return;
    window.ym(counterId, 'hit', `${window.location.origin}${currentPath.value}`);
  }

  function initializeCounter(): void {
    if (!consent.value?.analytics || initialized || !window.ym) return;
    window.ym(counterId, 'init', {
      defer: true,
      clickmap: false,
      trackLinks: false,
      webvisor: false,
      accurateTrackBounce: false,
      sendTitle: false,
    });
    initialized = true;
    hit(currentPath.value);
  }

  function startMetrika(): void {
    if (typeof window === 'undefined' || !Number.isSafeInteger(counterId) || counterId <= 0) return;
    if (!consent.value?.analytics || initialized || scriptLoading) return;
    if (scriptLoaded) {
      initializeCounter();
      return;
    }

    window.ym ||= function (...args: [number, string, ...unknown[]]) {
      (window.ym!.a ||= []).push(arguments);
    } as MetrikaFunction;
    window.ym.l = Date.now();

    const script = document.createElement('script');
    script.src = 'https://mc.yandex.ru/metrika/tag.js';
    script.async = true;
    scriptLoading = true;
    script.onload = () => {
      scriptLoading = false;
      scriptLoaded = true;
      initializeCounter();
    };
    script.onerror = () => {
      scriptLoading = false;
      script.remove();
      console.warn('Не удалось загрузить Яндекс Метрику.');
    };
    document.head.appendChild(script);
  }

  function stopMetrika(): void {
    if (initialized) window.ym?.(counterId, 'destruct');
    initialized = false;
    clearMetrikaStorage();
  }

  function loadFromStorage(): void {
    if (typeof window === 'undefined') return;
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      const saved: unknown = raw ? JSON.parse(raw) : null;
      if (validConsent(saved)) {
        consent.value = saved;
        showBanner.value = false;
        if (saved.analytics) startMetrika();
        return;
      }
      if (raw) window.localStorage.removeItem(STORAGE_KEY);
    } catch {
      // Если хранилище браузера недоступно, выбор остаётся только на эту вкладку.
    }
    showBanner.value = true;
  }

  function saveConsent(analytics: boolean): void {
    if (typeof window === 'undefined') return;
    const record: ConsentRecord = { analytics, savedAt: Date.now(), version: POLICY_VERSION };
    consent.value = record;
    showBanner.value = false;
    showModal.value = false;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(record));
    } catch {
      // Согласие действует в текущей вкладке, даже если localStorage отключён.
    }
    if (analytics) startMetrika();
    else stopMetrika();
  }

  function openSettings(): void {
    showModal.value = true;
  }

  return {
    consent,
    showBanner,
    showModal,
    loadFromStorage,
    acceptNecessaryOnly: () => saveConsent(false),
    acceptAll: () => saveConsent(true),
    saveCustomSettings: saveConsent,
    openSettings,
    hit,
  };
});
