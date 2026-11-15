#!/usr/bin/env bash
set -Eeuo pipefail

ACTION="${1:-deploy}"
BRANCH="${2:-main}"
ROOT=/home/scissors
NODE_HOME="$ROOT/runtime/node-v22.23.5-linux-x64"
REPOSITORY="$ROOT/repository"
RELEASES="$ROOT/releases"
CURRENT="$ROOT/current"
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

python3 -m venv "$RELEASE/scissors-backend/.venv"
"$RELEASE/scissors-backend/.venv/bin/python" -m pip install --disable-pip-version-check -r "$RELEASE/scissors-backend/requirements.txt"

cd "$RELEASE/scissors-frontend"
export PATH="$NODE_HOME/bin:$PATH"
"$NODE_HOME/bin/npm" ci --include=dev
TILDA_ASSETS="$RELEASE/scissors-frontend/public/tilda_assets"
TILDA_BUILD_HOLD="$RELEASE/.tilda-assets-build-hold"
if [[ -d "$TILDA_ASSETS" ]]; then
    mv "$TILDA_ASSETS" "$TILDA_BUILD_HOLD"
fi
SITE_URL=https://studio.scissors.group \
API_ORIGIN=https://api.studio.scissors.group \
VITE_SITE_URL=https://studio.scissors.group \
VITE_API_BASE_URL=https://api.studio.scissors.group/api/v1 \
VITE_STATIC_URL=https://studio.static.scissors.group/ \
VITE_MEDIA_URL=https://studio.static.scissors.group/media/ \
"$NODE_HOME/bin/npm" run build -- -m ssr || BUILD_STATUS=$?
if [[ -d "$TILDA_BUILD_HOLD" ]]; then
    mv "$TILDA_BUILD_HOLD" "$TILDA_ASSETS"
fi
if [[ "${BUILD_STATUS:-0}" -ne 0 ]]; then
    exit "$BUILD_STATUS"
fi
if [[ ! -L "$RELEASE/scissors-frontend/dist/ssr/node_modules" ]]; then
    ln -s ../../src-ssr/node_modules "$RELEASE/scissors-frontend/dist/ssr/node_modules"
fi

rsync -a --no-owner --no-group --no-times --no-perms "$RELEASE/scissors-frontend/public/" "$ROOT/static/"
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

if ! systemctl is-active --quiet scissors-backend.service \
    || ! systemctl is-active --quiet scissors-frontend.service \
    || ! curl --fail --silent --show-error http://127.0.0.1:4000/ -o /dev/null; then
    rollback
    exit 1
fi

echo "Deployed $COMMIT"
