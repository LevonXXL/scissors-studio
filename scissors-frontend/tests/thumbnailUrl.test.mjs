import assert from 'node:assert/strict';
import { test } from 'node:test';

import { getThumbnailUrl, mediaAssetUrl, staticAssetUrl } from '../src/utils/assetUrl.ts';

const media = 'https://static.scissors-studio.online/media/';
const api = 'https://api.studio.scissors.group/api/v1';

test('public images use STATIC_URL only when it is configured', () => {
  assert.equal(staticAssetUrl('/img/home/hero.png', ''), '/img/home/hero.png');
  assert.equal(staticAssetUrl('/img/home/hero.png', 'https://static.scissors-studio.online/'),
    'https://static.scissors-studio.online/img/home/hero.png');
  assert.equal(staticAssetUrl('/logo/scissors.png', 'https://static.scissors-studio.online/static/'),
    'https://static.scissors-studio.online/static/logo/scissors.png');
  assert.equal(staticAssetUrl('https://images.example.com/photo.jpg', media),
    'https://images.example.com/photo.jpg');
});

test('Django images use MEDIA_URL without changing unrelated external images', () => {
  assert.equal(mediaAssetUrl('https://api.studio.scissors.group/media/filer_public/photo.jpg', media, api),
    'https://static.scissors-studio.online/media/filer_public/photo.jpg');
  assert.equal(mediaAssetUrl('/media/filer_public/photo.jpg', media, api),
    'https://static.scissors-studio.online/media/filer_public/photo.jpg');
  assert.equal(mediaAssetUrl('https://static.scissors-studio.online/media/filer_public/photo.jpg', media, api),
    'https://static.scissors-studio.online/media/filer_public/photo.jpg');
  assert.equal(mediaAssetUrl('https://images.example.com/media/filer_public/photo.jpg', media, api),
    'https://images.example.com/media/filer_public/photo.jpg');
});

test('builds thumbnail URL for Filer images on the configured media host', () => {
  assert.equal(
    getThumbnailUrl('https://static.scissors-studio.online/media/filer_public/11/59/11599118-ab2b-4776-ac37-3e2e603752d9/1.png', 400, media, api),
    'https://static.scissors-studio.online/thumbnail/400/filer_public/11/59/11599118-ab2b-4776-ac37-3e2e603752d9/1.png',
  );
  assert.equal(
    getThumbnailUrl('https://api.studio.scissors.group/media/filer_public/salon/photo.jpg', 300, media, api),
    'https://static.scissors-studio.online/thumbnail/300/filer_public/salon/photo.jpg',
  );
  assert.equal(
    getThumbnailUrl('/media/filer_public/%D1%84%D0%BE%D1%82%D0%BE/a%20b.jpg', 600, media, api),
    'https://static.scissors-studio.online/thumbnail/600/filer_public/%D1%84%D0%BE%D1%82%D0%BE/a%20b.jpg',
  );
  assert.equal(
    getThumbnailUrl('https://static.scissors-studio.online/media/filer_public/a.jpg', 300, media, api),
    'https://static.scissors-studio.online/thumbnail/300/filer_public/a.jpg',
  );
});

test('leaves external, non-Filer and already generated images unchanged', () => {
  for (const image of [
    'https://cdn.example.com/media/filer_public/photo.jpg',
    'https://api.scissors-studio.ru/media/page/photo.jpg',
    'https://api.scissors-studio.ru/thumbnail/300/filer_public/photo.jpg',
    '/logo/scissors-512x512.png',
  ]) {
    assert.equal(getThumbnailUrl(image, 300, media), image);
  }
});

test('rejects invalid dimensions and configuration without changing source', () => {
  const image = '/media/filer_public/photo.jpg';
  const original = 'https://static.scissors-studio.online/media/filer_public/photo.jpg';
  assert.equal(getThumbnailUrl(image, 0, media), original);
  assert.equal(getThumbnailUrl(image, 2001, media), original);
  assert.equal(getThumbnailUrl(image, 300, ''), image);
});
