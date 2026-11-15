.DEFAULT_GOAL := help
.PHONY: migrate-local runserver sync sync-one test superuser check-local seed

manage = python manage.py

migrate-local:
	$(manage) migrate

runserver:
	$(manage) runserver

sync:
	$(manage) sync_yclients

sync-one:
	$(manage) sync_yclients --salon-id $(id)

test:
	$(manage) test -v2

superuser:
	$(manage) createsuperuser

check-local:
	$(manage) check

seed:
	$(manage) seed_demo_data

# ============================================================
# Scissors Studio Backend (Django)
# Production deployment from the GitHub main branch
# ============================================================

# --- Переменные ---
LOCAL_DIR = .
REMOTE_USER = scissors
REMOTE_ADMIN_USER = levon
REMOTE_HOST = chinese-russian.com
REMOTE_PATH = /home/scissors
SERVICE_NAME = scissors-backend
DEPLOY_HELPER = ../ops/deploy/scissors-git-deploy.sh
SSH_DEPLOY = ssh -i ~/.ssh/scissors-crc -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes
SCP_DEPLOY = scp -i ~/.ssh/scissors-crc -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes

# ============================================================
# Цели
# ============================================================

.PHONY: sync-dry-run
sync-dry-run:
	git ls-remote origin refs/heads/main

.PHONY: sync-prod
# Deployment uses the shared Git helper; persistent Tilda assets live only in /home/scissors/static/tilda_assets.
sync-prod:
	@$(SCP_DEPLOY) $(DEPLOY_HELPER) $(REMOTE_USER)@$(REMOTE_HOST):$(REMOTE_PATH)/scissors-git-deploy.sh
	@$(SSH_DEPLOY) $(REMOTE_USER)@$(REMOTE_HOST) "chmod 0750 $(REMOTE_PATH)/scissors-git-deploy.sh && bash $(REMOTE_PATH)/scissors-git-deploy.sh deploy main"

.PHONY: install-reqs
install-reqs:
	@echo "Зависимости устанавливаются из Git-релиза при make deploy."

.PHONY: check
check:
	$(SSH_DEPLOY) $(REMOTE_USER)@$(REMOTE_HOST) "systemctl is-active $(SERVICE_NAME).service"

.PHONY: migrate
migrate:
	@echo "Миграции выполняются служебным пользователем при перезапуске backend."

.PHONY: collectstatic
collectstatic:
	@echo "collectstatic выполняется служебным пользователем при перезапуске backend."

.PHONY: restart
restart:
	@echo "[RESTART] Перезапуск сервиса $(SERVICE_NAME) на $(REMOTE_HOST)"
	$(SSH_DEPLOY) $(REMOTE_USER)@$(REMOTE_HOST) "sudo -n /usr/bin/systemctl restart $(SERVICE_NAME).service"
	@echo "[RESTART] Сервис перезапущен."

.PHONY: status
status:
	@echo "[STATUS] Статус сервиса $(SERVICE_NAME) на $(REMOTE_HOST)"
	$(SSH_DEPLOY) $(REMOTE_USER)@$(REMOTE_HOST) "systemctl status $(SERVICE_NAME).service --no-pager"

.PHONY: logs
logs:
	@echo "[LOGS] Последние 100 строк лога сервиса $(SERVICE_NAME)"
	ssh $(REMOTE_ADMIN_USER)@$(REMOTE_HOST) "sudo -n journalctl -u $(SERVICE_NAME).service -n 100 --no-pager"

.PHONY: logs-f
logs-f:
	@echo "[LOGS-F] Live-логи сервиса $(SERVICE_NAME) (Ctrl+C для выхода)"
	ssh $(REMOTE_ADMIN_USER)@$(REMOTE_HOST) "sudo -n journalctl -u $(SERVICE_NAME).service -f"

# ============================================================
# Деплой
# ============================================================

.PHONY: deploy
deploy: sync-prod
	@echo ""
	@echo "=========================================="
	@echo "✅ Деплой бэкенда Scissors Studio завершён!"
	@echo "=========================================="

# Быстрый Git-деплой: обновление релиза и перезапуск приложения.
.PHONY: deploy-fast
deploy-fast: sync-prod
	@echo "[DEPLOY-FAST] Быстрый деплой завершён."

# Откат выполняется возвратом current symlink к предыдущему Git-релизу.
.PHONY: rollback
rollback:
	$(SSH_DEPLOY) $(REMOTE_USER)@$(REMOTE_HOST) "bash $(REMOTE_PATH)/scissors-git-deploy.sh rollback"

.PHONY: snapshots
snapshots:
	$(SSH_DEPLOY) $(REMOTE_USER)@$(REMOTE_HOST) "ls -1dt $(REMOTE_PATH)/releases/*"

.PHONY: help
help:
	@echo "🚀 Scissors Backend — команды деплоя"
	@echo ""
	@echo "Деплой:"
	@echo "  deploy         - Git-деплой main с подготовкой релиза, сборкой и проверкой сервисов"
	@echo "  deploy-fast    - Быстрый Git-деплой main"
	@echo "  rollback       - Переключение на предыдущий Git-релиз"
	@echo ""
	@echo "Синхронизация:"
	@echo "  sync-dry-run   - Тестовая синхронизация (без реальных изменений)"
	@echo "  sync-prod      - Получение Git-релиза на сервере"
	@echo ""
	@echo "Django на сервере:"
	@echo "  install-reqs   - Обновление pip пакетов из requirements.txt"
	@echo "  check          - Проверка настроек Django (manage.py check)"
	@echo "  migrate        - Применение миграций"
	@echo "  collectstatic  - Сбор статических файлов"
	@echo ""
	@echo "Django локально:"
	@echo "  check-local    - Проверка настроек Django"
	@echo "  migrate-local  - Применение локальных миграций"
	@echo ""
	@echo "Сервис (systemd):"
	@echo "  restart        - Перезапустить systemd-сервис"
	@echo "  status         - Статус сервиса"
	@echo "  logs           - Последние 100 строк лога"
	@echo "  logs-f         - Live-логи (follow)"
	@echo ""
	@echo "  help           - Показать это сообщение"
