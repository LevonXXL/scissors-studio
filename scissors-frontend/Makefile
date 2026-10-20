# ============================================================
# Scissors Studio Frontend
# Quasar SSR + PWA
# ============================================================

# --- Локальные настройки ---

NODE_VERSION = 22.22.0
LOCAL_DIST_DIR = dist/ssr


# --- Сервер ---

REMOTE_USER = levon
REMOTE_HOST = chinese-russian.com
REMOTE_PATH = /opt/scissors-frontend


# --- Systemd ---

SERVICE_NAME = scissors-frontend


# --- Rsync ---

RSYNC_CMD = rsync -av --delete -e ssh


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
	@echo "[SYNC-DRY-RUN] Проверка синхронизации:"
	@echo "  $(LOCAL_DIST_DIR)/"
	@echo "  -> $(REMOTE_USER)@$(REMOTE_HOST):$(REMOTE_PATH)/"
	$(RSYNC_CMD) --dry-run \
		$(LOCAL_DIST_DIR)/ \
		$(REMOTE_USER)@$(REMOTE_HOST):$(REMOTE_PATH)/


.PHONY: sync-prod
sync-prod:
	@echo "[SYNC-PROD] Синхронизация:"
	@echo "  $(LOCAL_DIST_DIR)/"
	@echo "  -> $(REMOTE_USER)@$(REMOTE_HOST):$(REMOTE_PATH)/"
	$(RSYNC_CMD) \
		$(LOCAL_DIST_DIR)/ \
		$(REMOTE_USER)@$(REMOTE_HOST):$(REMOTE_PATH)/
	@echo "[SYNC-PROD] Синхронизация завершена."


# ============================================================
# INSTALL PRODUCTION DEPENDENCIES
# ============================================================

.PHONY: install-prod
install-prod:
	@echo "[INSTALL] Установка production dependencies..."
	ssh $(REMOTE_USER)@$(REMOTE_HOST) \
		"cd $(REMOTE_PATH) && npm install --omit=dev"
	@echo "[INSTALL] Dependencies установлены."


# ============================================================
# SYSTEMD
# ============================================================

.PHONY: restart
restart:
	@echo "[RESTART] Перезапуск $(SERVICE_NAME)..."
	ssh $(REMOTE_USER)@$(REMOTE_HOST) \
		"sudo systemctl restart $(SERVICE_NAME)"
	@echo "[RESTART] Сервис перезапущен."


.PHONY: status
status:
	@echo "[STATUS] $(SERVICE_NAME)"
	ssh $(REMOTE_USER)@$(REMOTE_HOST) \
		"systemctl status $(SERVICE_NAME) --no-pager"


.PHONY: logs
logs:
	@echo "[LOGS] $(SERVICE_NAME)"
	ssh $(REMOTE_USER)@$(REMOTE_HOST) \
		"journalctl -u $(SERVICE_NAME) -n 100 -f"


# ============================================================
# DEPLOY
# ============================================================

.PHONY: deploy
deploy: build sync-prod install-prod restart
	@echo ""
	@echo "=========================================="
	@echo "✅ Scissors Studio frontend deployed"
	@echo "=========================================="

.PHONY: run-dev
run-dev:
	@echo "[RUN] Переключаемся на Node $(NODE_VERSION)"
	@bash -c 'source ~/.nvm/nvm.sh && nvm use $(NODE_VERSION) && quasar dev -m ssr'