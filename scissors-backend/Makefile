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
# Деплой через rsync без Git
# ============================================================

# --- Переменные ---
LOCAL_DIR = .
REMOTE_USER = levon
REMOTE_HOST = chinese-russian.com
REMOTE_PATH = /opt/scissors-backend
SERVICE_NAME = scissors-backend
VENV_DIR = .venv

# Команда для запуска Django на сервере с активацией venv
# (DJANGO_SETTINGS_MODULE указан явно для надежности, но можно убрать, если он есть в .env)
REMOTE_DJANGO = cd $(REMOTE_PATH) && source $(VENV_DIR)/bin/activate && export DJANGO_SETTINGS_MODULE=scissors_studio.settings && python manage.py

# Rsync с игнорированием проверки хоста для автоматизации
RSYNC_CMD = rsync -av --delete -e "ssh -o StrictHostKeyChecking=no"

# Исключаемые файлы и папки (не копируем виртуальное окружение, медиа, секреты и кэш)
RSYNC_EXCLUDES = \
	--exclude='.idea' \
	--exclude='.vscode' \
	--exclude='.venv' \
	--exclude='venv' \
	--exclude='media/' \
	--exclude='.env' \
	--exclude='.env.local' \
	--exclude='.env.*' \
	--exclude='__pycache__' \
	--exclude='*.pyc' \
	--exclude='*.pyo' \
	--exclude='db.sqlite3' \
	--exclude='*.log' \
	--exclude='.DS_Store' \
	--exclude='staticfiles/'

# ============================================================
# Цели
# ============================================================

.PHONY: sync-dry-run
sync-dry-run:
	@echo "[SYNC-DRY-RUN] Проверка синхронизации $(LOCAL_DIR)/ -> $(REMOTE_USER)@$(REMOTE_HOST):$(REMOTE_PATH)/"
	$(RSYNC_CMD) $(RSYNC_EXCLUDES) --dry-run $(LOCAL_DIR)/ $(REMOTE_USER)@$(REMOTE_HOST):$(REMOTE_PATH)/

.PHONY: sync-prod
sync-prod:
	@echo "[SYNC-PROD] Синхронизация $(LOCAL_DIR)/ -> $(REMOTE_USER)@$(REMOTE_HOST):$(REMOTE_PATH)/"
	$(RSYNC_CMD) $(RSYNC_EXCLUDES) $(LOCAL_DIR)/ $(REMOTE_USER)@$(REMOTE_HOST):$(REMOTE_PATH)/
	@echo "[SYNC-PROD] Синхронизация завершена."

.PHONY: install-reqs
install-reqs:
	@echo "[INSTALL] Установка зависимостей (requirements.txt) на $(REMOTE_HOST)"
	ssh $(REMOTE_USER)@$(REMOTE_HOST) "cd $(REMOTE_PATH) && source $(VENV_DIR)/bin/activate && pip install -r requirements.txt --upgrade"
	@echo "[INSTALL] Зависимости обновлены."

.PHONY: check
check:
	@echo "[CHECK] Проверка настроек Django на $(REMOTE_HOST)"
	ssh $(REMOTE_USER)@$(REMOTE_HOST) "$(REMOTE_DJANGO) check"
	@echo "[CHECK] Проверка пройдена."

.PHONY: migrate
migrate:
	@echo "[MIGRATE] Применение миграций на $(REMOTE_HOST)"
	ssh $(REMOTE_USER)@$(REMOTE_HOST) "$(REMOTE_DJANGO) migrate --noinput"
	@echo "[MIGRATE] Миграции применены."

.PHONY: collectstatic
collectstatic:
	@echo "[COLLECTSTATIC] Сбор статических файлов на $(REMOTE_HOST)"
	ssh $(REMOTE_USER)@$(REMOTE_HOST) "$(REMOTE_DJANGO) collectstatic --noinput"
	@echo "[COLLECTSTATIC] Статика собрана."

.PHONY: restart
restart:
	@echo "[RESTART] Перезапуск сервиса $(SERVICE_NAME) на $(REMOTE_HOST)"
	ssh $(REMOTE_USER)@$(REMOTE_HOST) "sudo systemctl restart $(SERVICE_NAME)"
	@echo "[RESTART] Сервис перезапущен."

.PHONY: status
status:
	@echo "[STATUS] Статус сервиса $(SERVICE_NAME) на $(REMOTE_HOST)"
	ssh $(REMOTE_USER)@$(REMOTE_HOST) "sudo systemctl status $(SERVICE_NAME) --no-pager"

.PHONY: logs
logs:
	@echo "[LOGS] Последние 100 строк лога сервиса $(SERVICE_NAME)"
	ssh $(REMOTE_USER)@$(REMOTE_HOST) "sudo journalctl -u $(SERVICE_NAME) -n 100 --no-pager"

.PHONY: logs-f
logs-f:
	@echo "[LOGS-F] Live-логи сервиса $(SERVICE_NAME) (Ctrl+C для выхода)"
	ssh $(REMOTE_USER)@$(REMOTE_HOST) "sudo journalctl -u $(SERVICE_NAME) -f"

# ============================================================
# Деплой
# ============================================================

.PHONY: deploy
deploy: sync-prod install-reqs check migrate collectstatic restart
	@echo ""
	@echo "=========================================="
	@echo "✅ Деплой бэкенда Scissors Studio завершён!"
	@echo "=========================================="

# Быстрый деплой без миграций и статики (только код + зависимости + рестарт)
.PHONY: deploy-fast
deploy-fast: sync-prod install-reqs restart
	@echo "[DEPLOY-FAST] Быстрый деплой завершён."

# Откат: перезапуск сервиса (если нужно быстро вернуть рабочую версию после неудачного деплоя)
.PHONY: rollback
rollback:
	@echo "[ROLLBACK] Откат: перезапуск сервиса $(SERVICE_NAME)"
	ssh $(REMOTE_USER)@$(REMOTE_HOST) "sudo systemctl restart $(SERVICE_NAME)"
	@echo "[ROLLBACK] Сервис перезапущен."

.PHONY: help
help:
	@echo "🚀 Scissors Backend — команды деплоя"
	@echo ""
	@echo "Деплой:"
	@echo "  deploy         - Полный деплой: sync → install → check → migrate → collectstatic → restart"
	@echo "  deploy-fast    - Быстрый деплой: sync → install → restart (без миграций и статики)"
	@echo "  rollback       - Перезапуск сервиса (для быстрого отката состояния)"
	@echo ""
	@echo "Синхронизация:"
	@echo "  sync-dry-run   - Тестовая синхронизация (без реальных изменений)"
	@echo "  sync-prod      - Реальная синхронизация файлов через rsync"
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
