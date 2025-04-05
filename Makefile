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
		--workers 3 --threads 100

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
