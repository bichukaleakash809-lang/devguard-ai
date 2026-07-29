# DevGuard AI — common tasks.
#
# Every target here is something a reviewer might actually want to run, and
# every one of them works without a Groq API key, without a collector, and
# without SigNoz. Targets that need something unavailable say so rather than
# failing obscurely.

PYTHON ?= python
PORT   ?= 8000

.DEFAULT_GOAL := help

.PHONY: help
help:  ## Show this help
	@echo ""
	@echo "DevGuard AI — make targets"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'
	@echo ""

.PHONY: doctor
doctor:  ## Preflight: what is installed, what is missing, what to do about it
	@$(PYTHON) scripts/doctor.py

.PHONY: install
install:  ## Install backend and frontend dependencies
	$(PYTHON) -m pip install -r requirements.txt
	cd frontend && npm install

.PHONY: test
test:  ## Run the test suite (no API key or network required)
	$(PYTHON) -m pytest

.PHONY: verify-otel
verify-otel:  ## Prove OTLP export + trace context + log correlation are real
	$(PYTHON) scripts/verify_otel.py

.PHONY: verify
verify: test verify-otel lint build  ## Everything CI runs, locally
	@echo ""
	@echo "verify: all checks passed."

.PHONY: lint
lint:  ## Lint the frontend
	cd frontend && npm run lint

.PHONY: build
build:  ## Type-check and build the frontend
	cd frontend && npm run build

.PHONY: backend
backend:  ## Run the backend (works with no API key; /scan needs one)
	$(PYTHON) -m uvicorn backend.main:app --reload --port $(PORT)

.PHONY: frontend
frontend:  ## Run the frontend dev server
	cd frontend && npm run dev

.PHONY: clean
clean:  ## Remove build artifacts and caches
	rm -rf frontend/.next frontend/tsconfig.tsbuildinfo
	find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
	find . -name '*.pyc' -delete 2>/dev/null || true
	rm -rf .pytest_cache
