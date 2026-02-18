# Vociferous — Project Tasks
# Usage: make <target>

.DEFAULT_GOAL := help
.PHONY: help install install-desktop uninstall-desktop install-shortcut-linux uninstall-shortcut-linux install-shortcut-mac uninstall-shortcut-mac install-shortcut-windows uninstall-shortcut-windows run test format lint build clean docker docker-gpu provision fix-gpu

DESKTOP_DEST := $(HOME)/.local/share/applications/vociferous.desktop

VENV     := .venv
PYTHON   := $(VENV)/bin/python
PIP      := $(VENV)/bin/pip
RUFF     := $(VENV)/bin/ruff
PYTEST   := $(VENV)/bin/pytest
NPM      := npm

# ── Help ─────────────────────────────────────────────────────────────────────

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# ── Setup ────────────────────────────────────────────────────────────────────

install: ## Install all dependencies (system check + venv + frontend)
	@bash scripts/install.sh

provision: ## Download ASR and SLM models
	$(PYTHON) scripts/provision_models.py

install-desktop: ## Install the .desktop launcher for the current location
	@sed 's|{{INSTALL_DIR}}|$(CURDIR)|g' vociferous.desktop.template > vociferous.desktop
	@mkdir -p $(dir $(DESKTOP_DEST))
	@cp vociferous.desktop $(DESKTOP_DEST)
	@update-desktop-database $(dir $(DESKTOP_DEST)) 2>/dev/null || true
	@echo "Installed desktop entry to $(DESKTOP_DEST)"

uninstall-desktop: ## Remove the installed .desktop launcher
	@rm -f $(DESKTOP_DEST) vociferous.desktop
	@update-desktop-database $(dir $(DESKTOP_DEST)) 2>/dev/null || true
	@echo "Removed desktop entry"

install-shortcut-linux: ## Linux alias for install-desktop
	@$(MAKE) install-desktop

uninstall-shortcut-linux: ## Linux alias for uninstall-desktop
	@$(MAKE) uninstall-desktop

install-shortcut-mac: ## Install macOS launcher shortcut (.command + Desktop link)
	@bash scripts/install_mac_shortcut.sh

uninstall-shortcut-mac: ## Remove macOS launcher shortcut
	@bash scripts/uninstall_mac_shortcut.sh

install-shortcut-windows: ## Install Windows Desktop + Start Menu shortcuts
	@powershell -ExecutionPolicy Bypass -File scripts/install_windows_shortcut.ps1

uninstall-shortcut-windows: ## Remove Windows Desktop + Start Menu shortcuts
	@powershell -ExecutionPolicy Bypass -File scripts/uninstall_windows_shortcut.ps1

fix-gpu: ## Fix NVIDIA UVM module for GPU acceleration
	@bash scripts/fix_gpu.sh

# ── Development ──────────────────────────────────────────────────────────────

run: ## Run the application
	./vociferous

test: ## Run the test suite
	$(PYTEST)

lint: ## Run linters (Ruff + frontend type check)
	$(RUFF) check src/ tests/ scripts/
	cd frontend && $(NPM) run check

format: ## Auto-format all code (Python + frontend)
	$(RUFF) format src/ tests/ scripts/
	cd frontend && $(NPM) run format

build: ## Build the frontend
	cd frontend && $(NPM) install --silent && npx vite build

# ── Docker ───────────────────────────────────────────────────────────────────

docker: ## Build and run in Docker (CPU)
	docker compose up --build

docker-gpu: ## Build and run in Docker (NVIDIA GPU)
	docker compose --profile gpu up --build

# ── Cleanup ──────────────────────────────────────────────────────────────────

clean: ## Remove build artifacts and caches
	rm -rf frontend/dist frontend/node_modules/.vite
	find . -path ./.venv -prune -o -path ./old-vociferous -prune -o -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage vociferous.desktop
