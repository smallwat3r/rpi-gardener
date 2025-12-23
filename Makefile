SHELL  = /bin/bash
RPI    = rpi
PICO   = pico

.PHONY: help
help:  ## Show this help menu
	@echo "Usage: make [TARGET ...]"
	@echo ""
	@grep --no-filename -E '^[a-zA-Z_%-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "%-25s %s\n", $$1, $$2}'

VENV           = .venv
VENV_PYTHON    = $(VENV)/bin/python
SYSTEM_PYTHON  = $(shell which python3.12)
PYTHON         = $(wildcard $(VENV_PYTHON))
MPREMOTE       = $(VENV)/bin/mpremote

$(VENV_PYTHON):
	rm -rf $(VENV)
	$(SYSTEM_PYTHON) -m venv $(VENV)

.PHONY: venv
venv: $(VENV_PYTHON)  ## Create a Python virtual environment

.PHONY: deps
deps:  ## Install Python requirements in virtual environment
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install --no-cache-dir -r requirements.txt

.PHONY: mpdeps
mpdeps:  ## Install Micropython requirements in virtual environment
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install --no-cache-dir -r requirements-mp.txt

.PHONY: flask
flask:  ## Start the Flask server (for development)
	RELOAD=1 $(PYTHON) -m flask --app $(RPI).server:app run --host 0.0.0.0 --debug

.PHONY: server
server:  ## Start the Flask server with Gunicorn (binded for Nginx)
	$(PYTHON) -m gunicorn $(RPI).server:app --bind=unix:/tmp/gunicorn.sock \
		--workers 3 --threads 2

.PHONY: polling
polling:  ## Start the polling service
	$(PYTHON) -m $(RPI).dht.polling

.PHONY: mpedit
mpedit:  ## Edit remote Pico file (make mpedit file=main.py)
	EDITOR=vim $(MPREMOTE) edit $(file)

.PHONY: mprestart
mprestart:  ## Restart main.py script on the Pico
	$(MPREMOTE) soft-reset
	$(MPREMOTE) exec --no-follow 'import main'

.PHONY: up
up:  ## Start Docker services (RPi production)
	docker compose up -d --build

.PHONY: dev
dev:  ## Start Docker services (local development, no hardware)
	docker compose -f docker-compose.dev.yml up -d --build

.PHONY: dev-rebuild
dev-rebuild:  ## Rebuild dev Docker without cache (use after FE changes)
	docker compose -f docker-compose.dev.yml build --no-cache
	docker compose -f docker-compose.dev.yml up -d

.PHONY: dev-down
dev-down:  ## Stop dev Docker services
	docker compose -f docker-compose.dev.yml down

.PHONY: dev-logs
dev-logs:  ## View dev Docker logs
	docker compose -f docker-compose.dev.yml logs -f

.PHONY: dev-seed
dev-seed:  ## Seed dev database with dummy data
	docker compose -f docker-compose.dev.yml exec app python scripts/seed_data.py

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
