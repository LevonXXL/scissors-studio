.PHONY: archive deploy-backend deploy-frontend

# Архив исходников без секретов, артефактов сборки и пользовательских файлов.
archive:
	tar czf ../scissors-project.tar.gz \
		--exclude='.git' --exclude='.env' --exclude='.env.*' \
		--exclude='.venv' --exclude='node_modules' --exclude='dist' \
		--exclude='scissors-frontend/tilda_assets' --exclude='scissors-frontend/public/tilda_assets' \
		--exclude='media' --exclude='staticfiles' --exclude='*.pem' --exclude='*.key' \
		scissors-backend scissors-frontend ops Makefile

deploy-backend:
	$(MAKE) -C scissors-backend deploy

deploy-frontend:
	$(MAKE) -C scissors-frontend deploy
