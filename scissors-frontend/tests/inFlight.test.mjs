import assert from 'node:assert/strict';
import test from 'node:test';
import { dedupeInFlight } from '../src/utils/inFlight.ts';

test('dedupeInFlight shares overlapping work for the same owner and key', async () => {
  const owner = {};
  let calls = 0;
  let finish;
  const pending = new Promise((resolve) => { finish = resolve; });

  const first = dedupeInFlight(owner, 'menu', () => {
    calls += 1;
    return pending;
  });
  const second = dedupeInFlight(owner, 'menu', () => {
    calls += 1;
    return Promise.resolve('unexpected');
  });

  assert.equal(first, second);
  await Promise.resolve();
  assert.equal(calls, 1);
  finish('loaded');
  assert.deepEqual(await Promise.all([first, second]), ['loaded', 'loaded']);
});

test('dedupeInFlight isolates store instances and clears rejected work', async () => {
  const firstOwner = {};
  const secondOwner = {};
  const failure = new Error('failed');

  await assert.rejects(dedupeInFlight(firstOwner, 'data', () => Promise.reject(failure)), failure);
  assert.equal(await dedupeInFlight(firstOwner, 'data', async () => 'retry'), 'retry');
  assert.equal(await dedupeInFlight(secondOwner, 'data', async () => 'separate'), 'separate');
});
