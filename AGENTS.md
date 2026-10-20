# Repository Guidelines

## Project Structure & Module Organization

`scissors-backend/` is a Django project. `scissors_studio/` contains settings and URL configuration; domain apps such as `booking/`, `salons/`, `masters/`, `services/`, `reviews/`, and `sync/` contain models, API code, migrations, and tests. `sync/fixtures/` holds sample integration data. `scissors-frontend/` is a Quasar, Vue 3, and TypeScript app. Put pages in `src/pages/`, reusable UI in `src/components/`, routes in `src/router/`, API clients in `src/api/`, and shared content in `src/data/`. Static files live in `public/`; SSR and PWA entry points live in `src-ssr/` and `src-pwa/`.

## Build, Test, and Development Commands

Run commands from the relevant subdirectory:

- Backend: `python -m pip install -r requirements.txt`, then `python manage.py migrate` and `python manage.py runserver` to start locally.
- Backend: `python manage.py check` validates Django configuration; `python manage.py test` runs the test suite.
- Frontend: `npm ci` installs locked dependencies; `npm run dev` starts Quasar development mode.
- Frontend: `npm run build` builds the app; `npm run typecheck` checks TypeScript and Vue types; `npm run format` applies Prettier. `npm run lint` invokes ESLint, but its referenced `eslint.config.js` is currently absent.

Makefile deploy targets operate on a remote server; use them only for an intended deployment.

## Coding Style & Naming Conventions

Use four spaces and `snake_case` for Python modules, functions, and test methods. Follow existing Django app boundaries and create migrations for model changes. Frontend `.editorconfig` specifies two spaces, LF endings, and a final newline for JavaScript, TypeScript, and Vue files. Name Vue components and pages in `PascalCase` (for example, `SalonPage.vue`); keep route and data modules descriptive. Prettier and ESLint are listed in frontend scripts; keep formatting consistent with nearby files.

## Testing Guidelines

Backend tests use Django `TestCase` and DRF `APITestCase`, with methods named `test_*`. Add focused tests in the affected app's `tests.py`; mock external API calls. Run `python manage.py test` from `scissors-backend/`. Run the nonstandard review module explicitly with `python manage.py test reviews.reviews_tests`. No frontend test runner or coverage threshold is configured; run typecheck and a build for frontend changes.

## Commit & Pull Request Guidelines

There are no commits on the current branch to establish a message convention. Use short, imperative subjects such as `Add salon review filtering`. In pull requests, describe the behavior change, list checks run, link related issues, and include screenshots for visible UI changes. Keep `.env` values, API tokens, and generated assets out of new commits.
