.PHONY: setup build up down migrate superuser logs shell frontend

# 第一次從零跑起整個專案
setup: .env build
	docker compose up db cache -d
	@echo "Waiting for db..." && sleep 3
	docker compose run --rm saleor python manage.py migrate
	docker compose run --rm saleor python manage.py createsuperuser --noinput || true
	docker compose up -d saleor saleor-worker api dashboard mailpit
	@echo ""
	@echo "All services running:"
	@echo "  Saleor API  http://localhost:8000/graphql/"
	@echo "  Tachiya     http://localhost:8001/"
	@echo "  Dashboard   http://localhost:9000/"
	@echo "  Mailpit     http://localhost:8025/"
	@echo ""
	@echo "For storefront: make frontend"

# 自動從 .env.example 建立 .env 並產生 SECRET_KEY
.env:
	cp .env.example .env
	@SECRET=$$(python3 -c "import secrets; print(secrets.token_urlsafe(50))"); \
	sed -i '' "s|change-this-to-a-random-secret-key|$$SECRET|" .env
	@echo ".env created with random SECRET_KEY"

build:
	docker compose build api dashboard

up:
	docker compose up -d saleor saleor-worker api db cache dashboard mailpit

down:
	docker compose down

migrate:
	docker compose run --rm saleor python manage.py migrate

superuser:
	docker compose run --rm saleor python manage.py createsuperuser --noinput

logs:
	docker compose logs -f

shell:
	docker compose run --rm saleor python manage.py shell

frontend:
	docker compose --profile frontend up --build frontend
