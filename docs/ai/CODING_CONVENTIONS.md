# Соглашения по коду

Основание: корневой `AGENTS.md`, `.editorconfig` frontend и существующие файлы. При расхождении документа с актуальным кодом сверяйтесь с кодом затронутого модуля.

## Backend

- Работать внутри доменного приложения (`pages`, `salons`, `masters`, `services`, `booking`, `sync`, `reviews`, `client_auth`, `communications`, `search`). Настройки и общую маршрутизацию держать в `scissors_studio/`; общие утилиты — в `core_utils/`.
- Python: четыре пробела, `snake_case` для модулей, функций и методов тестов; классы моделей, сериализаторов и представлений именуются в `PascalCase`. Сохранять стиль соседнего файла.
- При изменении моделей создавать миграцию. Публичный контракт держать согласованным между моделями, сериализаторами, URL и frontend-типами/клиентом.
- Тесты размещать в затронутом приложении (`tests.py` или существующих `test_*.py`); именовать методы `test_*`. Вызовы внешних API подменять в тестах. Отдельно запускать `reviews.reviews_tests`, если затронуты отзывы.
- Для операций импорта и синхронизации учитывать уже существующие management-команды и сохранение полей, редактируемых вручную; это видно в `sync/` и оговорено в backend README.

## Frontend

- Vue-страницы и компоненты — `PascalCase.vue` в `src/pages/` и `src/components/`. Маршруты — `src/router/routes.ts`; API-вызовы и типы — `src/api/`; состояние загрузки — Pinia-сторы в `src/stores/`; локальный контент — `src/data/`.
- Для JavaScript, TypeScript и Vue `.editorconfig` задаёт два пробела, LF и финальный перевод строки. В существующих файлах есть отклонения; менять форматирование соседнего кода только по необходимости задачи.
- Для данных backend использовать существующий Axios-клиент и типы; в компонентах учитывать SSR. Загрузка перед SSR уже реализуется через Quasar `preFetch`/`onServerPrefetch`; клиентские API вроде `window` использовать с проверкой окружения.
- Для публичных/media URL использовать `src/config/urls.ts` и `src/utils/assetUrl.ts`; для записи через YCLIENTS — `src/utils/yclientsBooking.ts`. Не встраивать новые адреса среды напрямую в компоненты.
- Видимый HTML из CMS отображается через `v-html`; сохранять существующие правила обработки такого содержимого и не добавлять произвольный HTML из непроверенных источников.

## Команды проверки

Из `scissors-backend/`: `python manage.py check`, `python manage.py test`; для отдельного модуля отзывов — `python manage.py test reviews.reviews_tests`. Локальный `Makefile` также предоставляет `make check-local`, `make test`, `make migrate-local`.

Из `scissors-frontend/`: `npm ci`, `npm run dev`, `npm run typecheck`, `npm run build`, `npm run test:messenger-links`. Тест `tests/thumbnailUrl.test.mjs` существует, но отдельный npm-скрипт не объявлен. `npm run lint` сейчас неработоспособен без `eslint.config.js`. `npm run format` пишет во множество файлов; запускать его целиком только при намеренном форматировании. Для явной SSR-сборки README указывает `quasar build -m ssr`, для PWA — `quasar build -m pwa`.

Корневой и оба локальных Makefile содержат команды удалённого развёртывания; их запуск требует отдельной задачи на deployment.
