import assert from 'node:assert/strict';
import { test } from 'node:test';

import { messengerLinks } from '../src/data/contacts.ts';
import { formatFeedbackMessage, messengerHref, primaryMessengerHref, telegramShareHref } from '../src/data/feedbackMessenger.ts';

const siteUrl = 'https://scissors-studio.ru/';
const byName = (name) => messengerLinks.find((link) => link.label === name);
const draft = { name: 'Алексей', phone: '+7 900 123-45-67', message: 'Стрижка & уход?\nДа #1' };

test('formats only filled fields using current form values', () => {
  assert.equal(formatFeedbackMessage(draft),
    'Обращение с сайта Scissors Studio\n\nИмя: Алексей\nТелефон: +7 900 123-45-67\n\nСообщение:\nСтрижка & уход?\nДа #1');
  assert.equal(formatFeedbackMessage({ name: ' ', phone: '', message: 'Вопрос' }),
    'Обращение с сайта Scissors Studio\n\nСообщение:\nВопрос');
  assert.equal(formatFeedbackMessage({ name: '', phone: '', message: ' ' }), '');
  assert.match(new URL(messengerHref(byName('WhatsApp'), { ...draft, message: 'Новый вопрос' }, siteUrl)).searchParams.get('text'), /Новый вопрос/);
  assert.equal(formatFeedbackMessage({ name: 'Алексей', phone: '', message: ' ' }), '');
  assert.match(formatFeedbackMessage({ name: '', phone: 'client@example.com', message: 'Вопрос' }), /Email: client@example.com/);
});

test('WhatsApp preserves support number and existing query while encoding text once', () => {
  const link = { ...byName('WhatsApp'), href: 'https://wa.me/79260717163?source=site&text=old' };
  const url = new URL(messengerHref(link, draft, siteUrl));
  assert.equal(url.pathname, '/79260717163');
  assert.equal(url.searchParams.get('source'), 'site');
  assert.equal(url.searchParams.getAll('text').length, 1);
  assert.equal(url.searchParams.get('text'), formatFeedbackMessage(draft));
  assert.match(url.search, /%2B7/);
  assert.match(url.search, /%26/);
  assert.match(url.search, /%3F/);
  assert.match(url.search, /%23/);
  assert.match(url.search, /%0A/);
  assert.doesNotMatch(url.search, /%25D0/);
});

test('Telegram phone chat gets text and share chooser includes site URL', () => {
  const link = { ...byName('Telegram'), href: 'https://t.me/+79260717163?source=site&text=old' };
  const direct = new URL(messengerHref(link, draft, siteUrl));
  assert.equal(direct.pathname, '/+79260717163');
  assert.equal(direct.searchParams.get('source'), 'site');
  assert.equal(direct.searchParams.getAll('text').length, 1);
  assert.equal(direct.searchParams.get('text'), formatFeedbackMessage(draft));

  const share = new URL(telegramShareHref(formatFeedbackMessage(draft), siteUrl));
  assert.equal(share.pathname, '/share/url');
  assert.equal(share.searchParams.get('url'), siteUrl);
  assert.equal(share.searchParams.get('text'), formatFeedbackMessage(draft));

  const unsupported = { ...byName('Telegram'), href: 'https://t.me/+privateInviteHash' };
  assert.equal(new URL(messengerHref(unsupported, draft, siteUrl)).pathname, '/share/url');
});

test('MAX opens the original support chat primarily and offers a share chooser separately', () => {
  const link = byName('MAX');
  assert.equal(primaryMessengerHref(link, draft, siteUrl), link.href);
  const url = new URL(messengerHref(link, draft, siteUrl));
  assert.equal(url.pathname, '/:share');
  assert.equal(url.searchParams.get('text'), formatFeedbackMessage(draft));
  assert.match(url.search, /%20/);
  assert.doesNotMatch(url.search, /\+/);
  assert.doesNotMatch(url.search, /%25D0/);
  assert.match(link.href, /^https:\/\/max\.ru\/u\//);
  assert.equal(messengerHref(link, { name: '', phone: '', message: '' }, siteUrl), link.href);
  assert.equal(primaryMessengerHref(byName('Telegram'), draft, siteUrl), messengerHref(byName('Telegram'), draft, siteUrl));
});

test('empty draft retains contact links; messenger click does not invoke backend', () => {
  const empty = { name: '', phone: '', message: '' };
  for (const link of messengerLinks) {
    assert.equal(messengerHref(link, empty, siteUrl), link.href);
  }
});
