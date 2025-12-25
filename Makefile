SHELL  = /bin/bash
RPI    = rpi
PICO   = pico

.PHONY: help
help:  ## Show this help menu
	@echo "Usage: make [TARGET ...]"
	@echo ""
	@grep --no-filename -E '^[a-zA-Z_%-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "%-25s %s\n", $$1, $$2}'

.PHONY: deps
deps:  ## Install Python requirements (server + hardware)
	uv sync --extra hardware

.PHONY: mpdeps
mpdeps:  ## Install Micropython tooling requirements
	uv sync --extra micropython

.PHONY: devdeps
devdeps:  ## Install development dependencies (includes pytest)
	uv sync --extra dev

.PHONY: test
test:  ## Run pytest test suite
	uv run python -m pytest tests/ -v

.PHONY: isort
isort:  ## Sort Python imports
	uv run isort $(RPI) tests

.PHONY: serve
serve:  ## Start the server (for development)
	uv run uvicorn $(RPI).server.entrypoint:create_app --factory --host 0.0.0.0 --reload

.PHONY: server
server:  ## Start the server with uvicorn (binded for Nginx)
	uv run uvicorn $(RPI).server.entrypoint:create_app --factory --uds /tmp/uvicorn.sock --workers 3

.PHONY: polling
polling:  ## Start the DHT polling service
	uv run python -m $(RPI).dht

.PHONY: pico
pico:  ## Start the Pico serial reader
	uv run python -m $(RPI).pico

.PHONY: mpedit
mpedit:  ## Edit remote Pico file (make mpedit file=main.py)
	EDITOR=vim uv run mpremote edit $(file)

.PHONY: mprestart
mprestart:  ## Restart main.py script on the Pico
	uv run mpremote soft-reset
	uv run mpremote exec --no-follow 'import main'

.PHONY: up
up:  ## Start Docker services (RPi production)
	docker compose up -d --build

.PHONY: dev
dev:  ## Start Docker services (local development, no hardware)
	docker compose -f docker-compose.dev.yml up -d --build

.PHONY: dev-rebuild
dev-rebuild:  ## Rebuild dev Docker (clears static volume for fresh FE)
	docker compose -f docker-compose.dev.yml down
	docker volume rm -f rpi-gardener-dev-static
	docker compose -f docker-compose.dev.yml build --no-cache
	docker compose -f docker-compose.dev.yml up -d

.PHONY: dev-down
dev-down:  ## Stop dev Docker services
	docker compose -f docker-compose.dev.yml down

.PHONY: dev-logs
dev-logs:  ## View dev Docker logs
	docker compose -f docker-compose.dev.yml logs -f

.PHONY: dev-seed
dev-seed:  ## Seed dev database with dummy data (clears existing)
	docker compose -f docker-compose.dev.yml exec app python scripts/seed_data.py -clear

.PHONY: down
down:  ## Stop Docker services
	docker compose down

.PHONY: logs
logs:  ## View Docker logs (follow mode)
	docker compose logs -f

.PHONY: logs-app
logs-app:  ## View app container logs
	docker compose logs -f app

.PHONY: restart
restart:  ## Restart Docker services
	docker compose restart

.PHONY: clean
clean:  ## Stop services and remove volumes
	docker compose down -v
