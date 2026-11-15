import { defineSsrMiddleware } from "#q-app";
import type {
  SsrRenderRedirectError,
  SsrRenderRouteNotFoundError
} from "#q-app";

const unavailableHtml = `<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Страница временно недоступна — Scissors Studio</title>
  <style>
    body { margin: 0; min-height: 100vh; display: grid; place-items: center; font: 16px/1.5 Arial, sans-serif; color: #242424; background: #f7f5f3; }
    main { padding: 32px; text-align: center; }
    h1 { font-size: clamp(24px, 5vw, 36px); }
  </style>
</head>
<body><main><h1>Страница временно недоступна</h1><p>Попробуйте открыть её позже.</p></main></body>
</html>`;

function isRedirectError(err: unknown): err is SsrRenderRedirectError {
  return (
    typeof err === "object" &&
    err !== null &&
    "redirectUrl" in err &&
    "redirectHttpStatusCode" in err
  );
}

function isRouteNotFoundError(
  err: unknown
): err is SsrRenderRouteNotFoundError {
  return typeof err === "object" && err !== null && "routeNotFound" in err;
}

function isApiUnavailableError(err: unknown): err is Error & { status: number } {
  return err instanceof Error && 'status' in err && typeof err.status === 'number'
    && (err.status === 0 || err.status >= 500);
}

/**
 * This middleware should execute as last one
 * since it captures everything and tries to
 * render the page with Vue
 */
export default defineSsrMiddleware(({ app, resolve, render, serve }) => {
  /**
   * We capture any other Express route and hand it
   * over to Vue and Vue Router to render our page
   */
  app.get(resolve.urlPath("{*path}"), async (req, res) => {
    res.setHeader("Content-Type", "text/html");

    try {
      const renderedHtml = await render({ req, res, nonce: res.locals.cspNonce });
      res.send(renderedHtml);
    } catch (err) {
      if (isRouteNotFoundError(err)) {
        /**
         * Hmm, Vue Router could not find the requested route
         * and it does not have a "catch-all" route
         */
        res.status(404).send("404 | Page Not Found");
        return;
      }

      if (isRedirectError(err)) {
        /**
         * We were told to redirect to another URL
         */
        res.redirect(err.redirectHttpStatusCode, err.redirectUrl);
        return;
      }

      if (isApiUnavailableError(err)) {
        console.error('SSR API unavailable:', err.message);
        res.setHeader('Cache-Control', 'no-store');
        res.status(503).send(unavailableHtml);
        return;
      }

      if (import.meta.env.QUASAR_DEV) {
        /**
         * Well, we treat any other code as error;
         * if we're in dev mode, then we can use Quasar CLI
         * to display a nice error page that contains the stack
         * and other useful information
         *
         * Note that serve.devError is available on dev only
         */
        console.error('SSR ORIGINAL ERROR:', err)
        console.error('SSR ORIGINAL STACK:', err instanceof Error ? err.stack : err)
        const { errorHeaders, errorHtml } = serve.devError({ err, req });
        res.set(errorHeaders).status(500).send(errorHtml);
        return;
      }

      if (import.meta.env.QUASAR_DEBUG) {
        console.error(
          err instanceof Error ? err.stack : (err ?? "Unknown error")
        );
      }

      /**
       * Render Error Page on production or
       * alternatively, create a route (/src/routes) for an error page and redirect to it
       * (just make sure that route won't crash too, otherwise you'll end up in an infinite loop!)
       */
      res.status(500).send("500 | Internal Server Error");
    }
  });
});
