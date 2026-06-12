# Memoru LIFF Backend Makefile
SHELL := /bin/bash
AWS_REGION ?= ap-northeast-1

.PHONY: help install build validate deploy-dev deploy-prod local-db local-keycloak local-ollama local-ollama-pull local-ollama-stop local-ollama-logs local-all local-all-stop local-api test clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	pip install -r requirements.txt -r requirements-dev.txt

build: ## Build SAM application (uses Docker container for Python 3.12)
	sam build --use-container

validate: ## Validate SAM template
	sam validate --lint

# ------------------------------------------------------------
# 実環境固有の値は samconfig.toml にコミットせず、デプロイ時に環境変数から
# --parameter-overrides を組み立てて注入する（public リポジトリ方針）。
#
# 必須（未設定なら fail-fast）:
#   OIDC_ISSUER    OIDC Issuer URL (Cognito/Keycloak)
#   OIDC_AUDIENCE  OIDC Audience (Cognito の場合は UserPool Client ID)
# 任意（未設定なら template.yaml の既定値を使用。空文字は渡さない）:
#   LINE_CHANNEL_ID, USE_STRANDS, TUTOR_SESSION_BACKEND,
#   AGENTCORE_MEMORY_ID, BEDROCK_MODEL_ID
#
# 使い方:
#   export OIDC_ISSUER=... OIDC_AUDIENCE=... && make deploy-dev
# 詳細は docs/deployment-guide-prod.md を参照。
# ------------------------------------------------------------
define build_param_overrides
	if [ -z "$$OIDC_ISSUER" ] || [ -z "$$OIDC_AUDIENCE" ]; then \
		echo "ERROR: 必須の環境変数が未設定です。" >&2; \
		[ -z "$$OIDC_ISSUER" ] && echo "  - OIDC_ISSUER (例: https://cognito-idp.ap-northeast-1.amazonaws.com/<UserPoolId>)" >&2; \
		[ -z "$$OIDC_AUDIENCE" ] && echo "  - OIDC_AUDIENCE (例: <UserPool Client ID>)" >&2; \
		echo "詳細: docs/deployment-guide-prod.md" >&2; \
		exit 1; \
	fi; \
	if [ -z "$$LINE_CHANNEL_ID" ]; then \
		echo "WARNING: LINE_CHANNEL_ID が未設定です。template.yaml の既定値(空)を使用します（LINE ID トークン検証は無効）。" >&2; \
	fi; \
	OVERRIDES="Environment=$(1) OidcIssuer=$$OIDC_ISSUER OidcAudience=$$OIDC_AUDIENCE"; \
	[ -n "$$LINE_CHANNEL_ID" ]       && OVERRIDES="$$OVERRIDES LineChannelId=$$LINE_CHANNEL_ID"; \
	[ -n "$$USE_STRANDS" ]           && OVERRIDES="$$OVERRIDES UseStrands=$$USE_STRANDS"; \
	[ -n "$$TUTOR_SESSION_BACKEND" ] && OVERRIDES="$$OVERRIDES TutorSessionBackend=$$TUTOR_SESSION_BACKEND"; \
	[ -n "$$AGENTCORE_MEMORY_ID" ]   && OVERRIDES="$$OVERRIDES AgentCoreMemoryId=$$AGENTCORE_MEMORY_ID"; \
	[ -n "$$BEDROCK_MODEL_ID" ]      && OVERRIDES="$$OVERRIDES BedrockModelId=$$BEDROCK_MODEL_ID"
endef

deploy-dev: build ## Deploy to development environment (requires OIDC_ISSUER, OIDC_AUDIENCE)
	@$(call build_param_overrides,dev); \
	sam deploy --config-env dev --parameter-overrides "$$OVERRIDES"

deploy-staging: build ## Deploy to staging environment (requires OIDC_ISSUER, OIDC_AUDIENCE)
	@$(call build_param_overrides,staging); \
	sam deploy --config-env staging --parameter-overrides "$$OVERRIDES"

deploy-prod: build ## Deploy to production environment (requires OIDC_ISSUER, OIDC_AUDIENCE)
	@$(call build_param_overrides,prod); \
	sam deploy --config-env prod --parameter-overrides "$$OVERRIDES"

local-db: ## Start local DynamoDB
	docker compose up -d dynamodb-local dynamodb-admin setup-tables
	@echo "DynamoDB Local: http://localhost:8000"
	@echo "DynamoDB Admin: http://localhost:8001"

local-keycloak: ## Start local Keycloak
	docker compose up -d keycloak
	@echo "Keycloak: http://localhost:8180"
	@echo "Admin Console: http://localhost:8180/admin (admin/admin)"
	@echo "Test User: test-user / test-password-123"

local-ollama: ## Start local Ollama (Docker)
	docker compose up -d ollama
	@echo "Waiting for Ollama service to be ready..."
	@echo "Ollama: http://localhost:11434"

local-ollama-pull: ## Pull Ollama model
	docker compose exec ollama ollama pull $${OLLAMA_MODEL:-llama3.2}
	@echo "Model downloaded successfully"

local-ollama-stop: ## Stop local Ollama
	docker compose stop ollama

local-ollama-logs: ## Show Ollama logs
	docker compose logs -f ollama

local-all: local-db local-keycloak local-ollama ## Start all local services
	@echo ""
	@echo "All local services started"
	@echo "  DynamoDB Local: http://localhost:8000"
	@echo "  DynamoDB Admin: http://localhost:8001"
	@echo "  Keycloak:       http://localhost:8180"
	@echo "  Ollama:         http://localhost:11434"
	@echo ""
	@echo "Next: run 'make local-api' in a separate terminal to start the API server"

local-all-stop: ## Stop all local services
	@echo "Stopping SAM local containers on memoru-network..."
	@docker ps --filter "network=memoru-network" --format '{{.ID}}' | xargs -r docker stop 2>/dev/null || true
	docker compose down

local-db-stop: ## Stop local DynamoDB
	docker compose down

local-api: build ## Start local API
	sam local start-api --port 8080 --docker-network memoru-network --env-vars env.json

local-invoke: build ## Invoke function locally
	sam local invoke ApiFunction --docker-network memoru-network --env-vars env.json

test: ## Run tests
	pytest tests/ -v --cov=src --cov-report=term-missing

test-unit: ## Run unit tests only
	pytest tests/unit/ -v

test-integration: ## Run integration tests
	pytest tests/integration/ -v

lint: ## Run linter
	ruff check src/ tests/
	python -m mypy src/

format: ## Format code
	ruff format src/ tests/

clean: ## Clean build artifacts
	rm -rf .aws-sam/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

logs-api: ## Tail API function logs
	sam logs -n ApiFunction --stack-name memoru-backend-dev --tail

logs-webhook: ## Tail webhook function logs
	sam logs -n LineWebhookFunction --stack-name memoru-backend-dev --tail

# DynamoDB operations
list-tables: ## List DynamoDB tables (local)
	aws dynamodb list-tables --endpoint-url http://localhost:8000

scan-users: ## Scan users table (local)
	aws dynamodb scan --table-name memoru-users-dev --endpoint-url http://localhost:8000

scan-cards: ## Scan cards table (local)
	aws dynamodb scan --table-name memoru-cards-dev --endpoint-url http://localhost:8000
