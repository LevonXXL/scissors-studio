import type { Salon } from '@/api/types';

/** Публичный адрес сайта без завершающего слэша — нужен для canonical, og:url и JSON-LD. */
export function siteUrl(): string {
  const raw = (import.meta.env.VITE_SITE_URL as string | undefined) || 'https://scissors-studio.ru';
  return raw.replace(/\/+$/, '');
}

export function absoluteUrl(path: string): string {
  return `${siteUrl()}${path.startsWith('/') ? path : `/${path}`}`;
}

/**
 * Описание салона приходит из YCLIENTS как HTML. Выводить его через v-html
 * нельзя: это внешние данные, и вместе с ними на страницу попал бы любой
 * <script>/onerror. Вместо чистки HTML-регулярками разбираем его в обычные
 * абзацы текста — Vue сам экранирует вывод, XSS невозможен по построению.
 */
export function htmlToParagraphs(html: string | null | undefined): string[] {
  if (!html) return [];
  const text = html
    .replace(/<\s*(script|style)[^>]*>[\s\S]*?<\s*\/\s*\1\s*>/gi, ' ')
    .replace(/<\s*br\s*\/?>/gi, '\n')
    .replace(/<\s*\/\s*(p|div|li|h[1-6]|ul|ol)\s*>/gi, '\n\n')
    .replace(/<[^>]*>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");
  return text
    .split(/\n{2,}|\n/)
    .map((p) => p.replace(/\s+/g, ' ').trim())
    .filter(Boolean);
}

export function truncate(text: string, max = 155): string {
  if (text.length <= max) return text;
  const cut = text.slice(0, max - 1);
  const lastSpace = cut.lastIndexOf(' ');
  return `${cut.slice(0, lastSpace > 80 ? lastSpace : cut.length).replace(/[,.;:\s]+$/, '')}…`;
}

const ALL_DAYS = [
  'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday',
] as const;

/**
 * "Ежедневно 10:00 — 22:00" → openingHoursSpecification для schema.org.
 * Распознаём только этот однозначный формат; всё остальное пропускаем —
 * неверные часы в структурированных данных хуже, чем их отсутствие.
 */
export function parseDailyHours(text: string | null | undefined) {
  const m = text?.match(/ежедневно\D*(\d{1,2}):(\d{2})\s*[—–-]\s*(\d{1,2}):(\d{2})/i);
  if (!m) return null;
  const pad = (h: string, min: string) => `${h.padStart(2, '0')}:${min}`;
  return [{
    '@type': 'OpeningHoursSpecification',
    dayOfWeek: [...ALL_DAYS],
    opens: pad(m[1]!, m[2]!),
    closes: pad(m[3]!, m[4]!),
  }];
}

/** JSON для <script type="application/ld+json">: "<" экранируется, иначе "</script>" в данных ломает разметку. */
export function toJsonLd(data: unknown): string {
  return JSON.stringify(data).replace(/</g, '\\u003c');
}

export function buildSalonJsonLd(opts: {
  salon: Salon;
  path: string;
  city?: string;
  description: string;
}) {
  const { salon, path, city, description } = opts;
  const url = absoluteUrl(path);
  const lat = parseFloat(salon.latitude);
  const lon = parseFloat(salon.longitude);
  const hours = parseDailyHours(salon.working_hours);

  return {
    '@context': 'https://schema.org',
    '@type': 'BeautySalon',
    '@id': `${url}#salon`,
    name: `Scissors by Stets — ${salon.name}`,
    url,
    description,
    ...(salon.phone ? { telephone: salon.phone } : {}),
    ...(salon.photos.length ? { image: salon.photos.slice(0, 6).map((p) => p.image) } : {}),
    address: {
      '@type': 'PostalAddress',
      streetAddress: salon.address,
      ...(city ? { addressLocality: city } : {}),
      addressCountry: 'RU',
    },
    ...(Number.isFinite(lat) && Number.isFinite(lon) && (lat !== 0 || lon !== 0)
      ? { geo: { '@type': 'GeoCoordinates', latitude: lat, longitude: lon } }
      : {}),
    ...(hours ? { openingHoursSpecification: hours } : {}),
  };
}

export function buildBreadcrumbJsonLd(items: { name: string; path: string }[]) {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((item, i) => ({
      '@type': 'ListItem',
      position: i + 1,
      name: item.name,
      item: absoluteUrl(item.path),
    })),
  };
}
