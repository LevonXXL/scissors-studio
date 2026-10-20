import type { MessengerLink } from './contacts';

export interface FeedbackDraft {
  name: string;
  phone: string;
  message: string;
}

export function formatFeedbackMessage(draft: FeedbackDraft): string {
  const name = draft.name.trim();
  const phone = draft.phone.trim();
  const message = draft.message.trim();
  if (!message) return '';

  const lines = ['Обращение с сайта Scissors Studio'];
  if (name || phone) {
    lines.push('');
    if (name) lines.push(`Имя: ${name}`);
    if (phone) lines.push(`Телефон: ${phone}`);
  }
  lines.push('', 'Сообщение:', message);
  return lines.join('\n');
}

export function telegramShareHref(text: string, siteUrl: string): string {
  const url = new URL('https://t.me/share/url');
  url.searchParams.set('url', siteUrl);
  url.searchParams.set('text', text);
  return url.toString();
}

export function messengerHref(link: MessengerLink, draft: FeedbackDraft, siteUrl: string): string {
  const text = formatFeedbackMessage(draft);
  if (!text) return link.href;

  if (link.label === 'MAX') {
    // MAX's documented examples encode spaces as %20, not form-style +.
    return `https://max.ru/:share?text=${encodeURIComponent(text)}`;
  }

  const url = new URL(link.href);
  if (link.label === 'WhatsApp' && url.hostname === 'wa.me' && /^\/\d+$/.test(url.pathname)) {
    url.searchParams.set('text', text);
    return url.toString();
  }
  if (link.label === 'Telegram') {
    const directChat = url.hostname === 't.me' && (
      /^\/\+\d+$/.test(url.pathname) || /^\/[A-Za-z][A-Za-z0-9_]{4,31}$/.test(url.pathname)
    );
    if (directChat) {
      url.searchParams.set('text', text);
      return url.toString();
    }
    return telegramShareHref(text, siteUrl);
  }
  return link.href;
}

export function primaryMessengerHref(link: MessengerLink, draft: FeedbackDraft, siteUrl: string): string {
  return link.label === 'MAX' ? link.href : messengerHref(link, draft, siteUrl);
}
