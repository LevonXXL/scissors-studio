.PHONY: archive deploy

archive:
	cd ~/scissors/scissors-studio && tar czf ../scissors-project.tar.gz \
	  --exclude='__pycache__' \
	  --exclude='*.pyc' \
	  --exclude='.venv' \
	  --exclude='node_modules' \
	  --exclude='.quasar' \
	  --exclude='dist' \
	  --exclude='.nuxt' \
	  --exclude='.output' \
	  --exclude='src-pwa' \
	  --exclude='tilda_assets' \
	  --exclude='public' \
	  --exclude='.idea' \
	  --exclude='.DS_Store' \
	  --exclude='__MACOSX' \
	  --exclude='*.egg-info' \
	  --exclude='.git' \
	  --exclude='*.sqlite3' \
	  --exclude='salons_dump.json' \
	  --exclude='scissors-backend/media' \
	  scissors-backend/ scissors-frontend/ .env Makefile 2>/dev/null
	@echo "Archive created: ../scissors-project.tar.gz"
	@ls -lah ../scissors-project.tar.gz

# Deploy Django backend to scissors-studio.ru
deploy:
	@test -n "$(MSG)" || (echo 'Usage: make deploy MSG="описание изменений"'; exit 1)
	git add --all &&
	git commit -m "$(MSG)" &&
	git push origin main &&
	ssh -t levon@chines