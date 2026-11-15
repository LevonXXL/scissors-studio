# ============================================================
# Scissors Studio Frontend
# Quasar SSR + PWA
# ============================================================

# --- Локальные настройки ---

NODE_VERSION = 22.22.0
LOCAL_DIST_DIR = dist/ssr


# --- Сервер ---

REMOTE_USER = scissors
REMOTE_ADMIN_USER = levon
REMOTE_HOST = chinese-russian.com
REMOTE_PATH = /home/scissors


# --- Systemd ---

SERVICE_NAME = scissors-frontend


# --- Rsync ---

DEPLOY_HELPER = ../ops/deploy/scissors-git-deploy.sh
SSH_DEPLOY = ssh -i ~/.ssh/scissors-crc -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes
SCP_DEPLOY = scp -i ~/.ssh/scissors-crc -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes


# ============================================================
# BUILD
# ============================================================

.PHONY: build
build:
	@echo "[BUILD] Переключаемся на Node $(NODE_VERSION)..."
	@bash -c 'source ~/.nvm/nvm.sh && nvm use $(NODE_VERSION) && quasar build -m ssr'
	@echo "[BUILD] Quasar SSR build завершён."


# ============================================================
# SYNC
# ============================================================

.PHONY: sync-dry-run
sync-dry-run:
	git ls-remote origin refs/heads/main


.PHONY: sync-prod
sync-prod:
	@$(SCP_DEPLOY) $(DEPLOY_HELPER) $(REMOTE_USER)@$(REMOTE_HOST):$(REMOTE_PATH)/scissors-git-deploy.sh
	@$(SSH_DEPLOY) $(REMOTE_USER)@$(REMOTE_HOST) "chmod 0750 $(REMOTE_PATH)/scissors-git-deploy.sh && bash $(REMOTE_PATH)/scissors-git-deploy.sh deploy main"


.PHONY: sync-public-static
sync-public-static:
	@echo "Файлы public/ копируются из Git-релиза при make deploy."


# ============================================================
# INSTALL PRODUCTION DEPENDENCIES
# ============================================================

.PHONY: install-prod
install-prod:
	@echo "Production-зависимости устанавливаются и собираются из Git-релиза при make deploy."


# ============================================================
# SYSTEMD
# ============================================================

.PHONY: restart
restart:
	@echo "[RESTART] Перезапуск $(SERVICE_NAME)..."
	$(SSH_DEPLOY) $(REMOTE_USER)@$(REMOTE_HOST) \
		"sudo -n /usr/bin/systemctl restart $(SERVICE_NAME).service"

.PHONY: snapshots rollback
snapshots:
	$(SSH_DEPLOY) $(REMOTE_USER)@$(REMOTE_HOST) "ls -1dt $(REMOTE_PATH)/releases/*"

rollback:
	$(SSH_DEPLOY) $(REMOTE_USER)@$(REMOTE_HOST) "bash $(REMOTE_PATH)/scissors-git-deploy.sh rollback"


.PHONY: status
status:
	@echo "[STATUS] $(SERVICE_NAME)"
	$(SSH_DEPLOY) $(REMOTE_USER)@$(REMOTE_HOST) \
		"systemctl status $(SERVICE_NAME) --no-pager"


.PHONY: logs
logs:
	@echo "[LOGS] $(SERVICE_NAME)"
	ssh $(REMOTE_ADMIN_USER)@$(REMOTE_HOST) \
		"sudo -n journalctl -u $(SERVICE_NAME) -n 100 --no-pager"


# ============================================================
# DEPLOY
# ============================================================

.PHONY: deploy
deploy: sync-prod
	@echo ""
	@echo "=========================================="
	@echo "✅ Scissors Studio frontend deployed"
	@echo "=========================================="

.PHONY: run-dev
run-dev:
	@echo "[RUN] Переключаемся на Node $(NODE_VERSION)"
	@bash -c 'source ~/.nvm/nvm.sh && nvm use $(NODE_VERSION) && quasar dev -m ssr'
