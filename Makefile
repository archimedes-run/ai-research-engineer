SHELL := /bin/bash
REPO_ROOT := $(shell pwd)

.PHONY: dev up stop install test lint clean help format lint-frontend build-frontend

dev: ## Start local dev stack (gateway :8001, frontend :3000, nginx :8080)
	@./scripts/serve.sh --dev

up: ## Build and start Docker stack
	@./scripts/deploy.sh

stop: ## Stop all local services
	@./scripts/serve.sh --stop

install: ## Install all dependencies
	@uv sync
	@cd frontend && npm install

test: ## Run test suite
	@uv run pytest

lint: ## Run linter
	@uv run ruff check src/

clean: ## Remove runtime data and output artifacts
	@rm -rf .data/runs agentic_output/ frontend/.next

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

format: ## Format backend with ruff
	@uv run ruff format src/ tests/

lint-frontend: ## Lint the frontend
	@cd frontend && npm run lint

build-frontend: ## Production build of the frontend (Vercel parity)
	@cd frontend && npm run build

.DEFAULT_GOAL := help
