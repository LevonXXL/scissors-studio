import type { Application } from 'express';

export function registerMonitoringRoutes(app: Application, isReady: () => boolean) {
  app.get('/health/', (_request, response) => {
    response.status(200).type('text/plain').set('Cache-Control', 'no-store').send('ok');
  });

  app.get('/ready/', (_request, response) => {
    const ready = isReady();
    response
      .status(ready ? 200 : 503)
      .type('text/plain')
      .set('Cache-Control', 'no-store')
      .send(ready ? 'ready' : 'not ready');
  });
}
