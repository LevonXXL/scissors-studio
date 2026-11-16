#!/usr/bin/env bash
set -Eeuo pipefail

ACTION="${1:-deploy}"
BRANCH="${2:-main}"
ROOT=/home/scissors
NODE_HOME="$ROOT/runtime/node-v22.23.5-linux-x64"
REPOSITORY="$ROOT/repository"
RELEASES="$ROOT/releases"
CURRENT="$ROOT/current"
IMPORT_PHOTOS="$ROOT/imports/service-photos"
PUBLIC_IMPORT_PHOTOS="$ROOT/static/tilda_assets"
FRONTEND_BUILD_ENV="$ROOT/frontend-build.env"
REPO_URL=git@github.com:LevonXXL/scissors-studio.git
GIT_SSH_COMMAND="ssh -i /etc/scissors/github_deploy_key -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes"
export GIT_SSH_COMMAND

if [[ "$ACTION" == rollback ]]; then
    CURRENT_RELEASE="$(readlink -f "$CURRENT")"
    PREVIOUS=""
    while IFS= read -r candidate; do
        if [[ "$candidate" != "$CURRENT_RELEASE" ]]; then
            PREVIOUS="$candidate"
            break
        fi
    done < <(find "$RELEASES" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' | sort -rn | cut -d' ' -f2-)
    [[ -n "$PREVIOUS" ]] || { echo "No previous release available" >&2; exit 1; }
    ln -s "$PREVIOUS" "$ROOT/current.rollback"
    mv -Tf "$ROOT/current.rollback" "$CURRENT"
    sudo -n /usr/bin/systemctl restart scissors-backend.service
    sudo -n /usr/bin/systemctl restart scissors-frontend.service
    exit 0
fi

if [[ ! -d "$REPOSITORY/.git" ]]; then
    git clone --no-checkout --single-branch --branch "$BRANCH" "$REPO_URL" "$REPOSITORY"
else
    git -C "$REPOSITORY" fetch --prune origin "$BRANCH"
fi

COMMIT="$(git -C "$REPOSITORY" rev-parse "origin/$BRANCH")"
REQUIRED_PATHS=(
    scissors-backend/masters/bot.py
    scissors-backend/pages/migrations/0005_page_link_title.py
    scissors-backend/salons/migrations/0010_salon_google_maps_url.py
    scissors-backend/core_utils/upload_handlers.py
    scissors-backend/services/xlsx_security.py
    scissors-backend/analytics/management/commands/aggregate_angie_logs.py
    scissors-frontend/src/components/Breadcrumbs.vue
)
for path in "${REQUIRED_PATHS[@]}"; do
    if ! git -C "$REPOSITORY" cat-file -e "$COMMIT:$path" 2>/dev/null; then
        echo "Refusing deploy: origin/$BRANCH is missing current production source $path" >&2
        exit 1
    fi
done

RELEASE="$RELEASES/$COMMIT"
PREVIOUS=""
if [[ -L "$CURRENT" ]]; then
    PREVIOUS="$(readlink -f "$CURRENT")"
fi

mkdir -p "$RELEASES"
if [[ ! -e "$RELEASE/.git" ]]; then
    git -C "$REPOSITORY" worktree add --detach "$RELEASE" "$COMMIT"
fi

if [[ ! -d "$IMPORT_PHOTOS" ]]; then
    echo "Refusing deploy: private service photo archive is missing: $IMPORT_PHOTOS" >&2
    exit 1
fi
if [[ ! -r "$FRONTEND_BUILD_ENV" ]]; then
    echo "Refusing deploy: frontend build config is missing or unreadable: $FRONTEND_BUILD_ENV" >&2
    exit 1
fi
VITE_YANDEX_MAPS_API_KEY="$(awk -F= '$1 == "VITE_YANDEX_MAPS_API_KEY" { sub(/^[^=]*=/, ""); print; exit }' "$FRONTEND_BUILD_ENV")"
if [[ -z "$VITE_YANDEX_MAPS_API_KEY" ]]; then
    echo "Refusing deploy: VITE_YANDEX_MAPS_API_KEY is missing from frontend build config" >&2
    exit 1
fi
export VITE_YANDEX_MAPS_API_KEY
if [[ -e "$PUBLIC_IMPORT_PHOTOS" ]]; then
    echo "Refusing deploy: service photo archive must not be in public static: $PUBLIC_IMPORT_PHOTOS" >&2
    exit 1
fi
while IFS= read -r -d '' duplicate; do
    if ! diff -qr --exclude=.DS_Store "$IMPORT_PHOTOS" "$duplicate" >/dev/null; then
        echo "Refusing deploy: release photo archive differs from private import source: $duplicate" >&2
        exit 1
    fi
    rm -rf "$duplicate"
done < <(find "$RELEASES" -type d -name tilda_assets -prune -print0)

python3 -m venv "$RELEASE/scissors-backend/.venv"
"$RELEASE/scissors-backend/.venv/bin/python" -m pip install --disable-pip-version-check -r "$RELEASE/scissors-backend/requirements.txt"

cd "$RELEASE/scissors-frontend"
export PATH="$NODE_HOME/bin:$PATH"
"$NODE_HOME/bin/npm" ci --include=dev
RELEASE_TILDA_ASSETS="$RELEASE/scissors-frontend/public/tilda_assets"
[[ ! -d "$RELEASE_TILDA_ASSETS" ]] || {
    echo "Refusing deploy: source photo archive unexpectedly appeared under frontend public/" >&2
    exit 1
}
SITE_URL=https://studio.scissors.group \
API_ORIGIN=https://api.studio.scissors.group \
VITE_SITE_URL=https://studio.scissors.group \
VITE_API_BASE_URL=https://api.studio.scissors.group/api/v1 \
VITE_STATIC_URL=https://studio.static.scissors.group/static/ \
VITE_MEDIA_URL=https://studio.static.scissors.group/media/ \
"$NODE_HOME/bin/npm" run build -- -m ssr || BUILD_STATUS=$?
if [[ "${BUILD_STATUS:-0}" -ne 0 ]]; then
    exit "$BUILD_STATUS"
fi
if ! grep -RFlq -- "$VITE_YANDEX_MAPS_API_KEY" "$RELEASE/scissors-frontend/dist/ssr/client"; then
    echo "Refusing deploy: Yandex Maps API key did not reach the compiled frontend bundle" >&2
    exit 1
fi
"$NODE_HOME/bin/npm" prune --omit=dev
rm -rf "$RELEASE/scissors-frontend/src-pwa/node_modules"
if [[ ! -L "$RELEASE/scissors-frontend/dist/ssr/node_modules" ]]; then
    ln -s ../../src-ssr/node_modules "$RELEASE/scissors-frontend/dist/ssr/node_modules"
fi
if [[ ! -x "$RELEASE/scissors-backend/.venv/bin/gunicorn" || ! -f "$RELEASE/scissors-frontend/dist/ssr/index.js" ]]; then
    echo "Refusing deploy: backend server or frontend SSR entrypoint is missing" >&2
    exit 1
fi

rsync -a --no-owner --no-group --no-times --no-perms --exclude=/tilda_assets/ \
    "$RELEASE/scissors-frontend/public/" "$ROOT/static/"
chgrp -R scissors-runtime "$RELEASE"
find "$RELEASE" -type d -exec chmod 0750 {} +
find "$RELEASE" -type f -perm /111 -exec chmod 0750 {} +
find "$RELEASE" -type f ! -perm /111 -exec chmod 0640 {} +
chmod -R go-w "$RELEASE/scissors-backend/.venv"
chgrp -R scissors-runtime "$RELEASE/scissors-backend/.venv"
find "$RELEASE/scissors-backend/.venv" -type d -exec chmod 0750 {} +
find "$RELEASE/scissors-backend/.venv" -type f -perm /111 -exec chmod 0750 {} +
find "$RELEASE/scissors-backend/.venv" -type f ! -perm /111 -exec chmod 0640 {} +

ln -s "$RELEASE" "$ROOT/current.next"
mv -Tf "$ROOT/current.next" "$CURRENT"

rollback() {
    if [[ -n "$PREVIOUS" && -d "$PREVIOUS" ]]; then
        ln -s "$PREVIOUS" "$ROOT/current.rollback"
        mv -Tf "$ROOT/current.rollback" "$CURRENT"
        sudo -n /usr/bin/systemctl restart scissors-backend.service || true
        sudo -n /usr/bin/systemctl restart scissors-frontend.service || true
    fi
}

if ! sudo -n /usr/bin/systemctl restart scissors-backend.service \
    || ! sudo -n /usr/bin/systemctl restart scissors-frontend.service; then
    rollback
    exit 1
fi

HEALTHY=0
for attempt in {1..30}; do
    if systemctl is-active --quiet scissors-backend.service \
        && systemctl is-active --quiet scissors-frontend.service \
        && curl --fail --silent http://127.0.0.1:4000/ -o /dev/null; then
        HEALTHY=1
        break
    fi
    sleep 1
done

if [[ "$HEALTHY" -ne 1 ]]; then
    rollback
    exit 1
fi

"$NODE_HOME/bin/npm" cache clean --force >/dev/null 2>&1 || true
"$RELEASE/scissors-backend/.venv/bin/python" -m pip cache purge >/dev/null 2>&1 || true

echo "Deployed $COMMIT"
