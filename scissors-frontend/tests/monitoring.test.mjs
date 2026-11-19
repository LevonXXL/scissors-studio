import assert from 'node:assert/strict';
import { once } from 'node:events';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import express from '../src-ssr/node_modules/express/index.js';
import { registerMonitoringRoutes } from '../src-ssr/monitoring.ts';

async function withMonitoringServer(isReady, callback) {
  const app = express();
  registerMonitoringRoutes(app, isReady);
  const server = app.listen(0, '127.0.0.1');
  await once(server, 'listening');
  try {
    await callback(server.address().port);
  } finally {
    server.close();
    await once(server, 'close');
  }
}

test('SSR health endpoint responds with a minimal 200', async () => {
  await withMonitoringServer(() => true, async (port) => {
    const response = await fetch(`http://127.0.0.1:${port}/health/`);
    assert.equal(response.status, 200);
    assert.equal(await response.text(), 'ok');
    assert.equal(response.headers.get('cache-control'), 'no-store');
  });
});

test('SSR readiness returns 503 until the listener is ready', async () => {
  let ready = false;
  await withMonitoringServer(() => ready, async (port) => {
    let response = await fetch(`http://127.0.0.1:${port}/ready/`);
    assert.equal(response.status, 503);
    assert.equal(await response.text(), 'not ready');

    ready = true;
    response = await fetch(`http://127.0.0.1:${port}/ready/`);
    assert.equal(response.status, 200);
    assert.equal(await response.text(), 'ready');
  });
});

test('public Angie hosts return 404 for monitoring paths instead of proxying them', async () => {
  const configRoot = new URL('../../ops/security/angie/', import.meta.url);
  for (const filename of ['scissors-frontend.conf', 'scissors-api.conf', 'scissors-admin.conf']) {
    const config = await readFile(new URL(filename, configRoot), 'utf8');
    assert.match(config, /location = \/health\/\s*\{\s*return 404;\s*\}/, filename);
    assert.match(config, /location = \/ready\/\s*\{\s*return 404;\s*\}/, filename);
  }
});

test('backend and SSR listen on loopback only', async () => {
  const backendUnit = await readFile(new URL('../../ops/security/scissors-backend.service', import.meta.url), 'utf8');
  const ssrServer = await readFile(new URL('../src-ssr/server.ts', import.meta.url), 'utf8');
  assert.match(backendUnit, /--bind 127\.0\.0\.1:8553/);
  assert.match(ssrServer, /server\.listen\(port, '127\.0\.0\.1'/);
});
