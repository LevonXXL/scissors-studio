import assert from 'node:assert/strict';
import { test } from 'node:test';

import { getThumbnailUrl } from '../src/utils/thumbnailUrl.ts';

const media = 'https://api.scissors-studio.ru/media/';

test('builds thumbnail URL for Filer images on the configured media host', () => {
  assert.equal(
    getThumbnailUrl('https://api.scissors-studio.ru/media/filer_public/salon/photo.jpg', 300, media),
    'https://api.scissors-studio.ru/thumbnail/300/filer_public/salon/photo.jpg',
  );
  assert.equal(
    getThumbnailUrl('/media/filer_public/%D1%84%D0%BE%D1%82%D0%BE/a%20b.jpg', 600, media),
    'https://api.scissors-studio.ru/thumbnail/600/filer_public/%D1%84%D0%BE%D1%82%D0%BE/a%20b.jpg',
  );
  assert.equal(
    getThumbnailUrl('https://static.scissors.online/media/filer_public/a.jpg', 300, 'https://static.scissors.online/media/'),
    'https://static.scissors.online/thumbnail/300/filer_public/a.jpg',
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
  assert.equal(getThumbnailUrl(image, 0, media), image);
  assert.equal(getThumbnailUrl(image, 2001, media), image);
  assert.equal(getThumbnailUrl(image, 300, ''), image);
});
