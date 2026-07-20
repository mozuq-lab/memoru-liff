# Memoru LIFF Backend Makefile
SHELL := /bin/bash
AWS_REGION ?= ap-northeast-1

.PHONY: help install build validate deploy-dev deploy-prod local-db local-keycloak local-ollama local-ollama-pull local-ollama-stop local-ollama-logs local-ollama-native-check local-ollama-native-pull local-all local-all-native-ollama local-all-stop local-api test clean allowlist-add allowlist-list allowlist-approve allowlist-remove verify-presignup

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
#   LIFF_ORIGIN    LIFF フロントの Origin (例: https://liff.<your-domain>)。
#                  CORS AllowOrigins に注入する。prod は必須（未設定なら fail-fast。
#                  template.yaml の Rules でも二重にガード）。dev/staging は任意
#                  （未設定なら localhost 系のみ許可）。
#   COGNITO_USER_POOL_ARN  PreSignUp トリガーの Invoke Permission (SourceArn) に必要な
#                  Cognito UserPool ARN。prod は必須（未設定なら fail-fast。
#                  template.yaml の Rules でも二重にガード）。dev/staging は任意
#                  （未設定なら Invoke Permission は作成されない＝トリガー未配線）。
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
	if [ "$(1)" = "prod" ] && [ -z "$$LIFF_ORIGIN" ]; then \
		echo "ERROR: LIFF_ORIGIN が未設定です（prod では必須）。" >&2; \
		echo "  CORS AllowOrigins に本番 LIFF フロントの Origin を注入するために必要です。" >&2; \
		echo "  例: export LIFF_ORIGIN=https://liff.<your-domain>" >&2; \
		echo "詳細: docs/deployment-guide-prod.md" >&2; \
		exit 1; \
	fi; \
	if [ "$(1)" = "prod" ] && [ -z "$$COGNITO_USER_POOL_ARN" ]; then \
		echo "ERROR: COGNITO_USER_POOL_ARN が未設定です（prod では必須）。" >&2; \
		echo "  PreSignUp トリガーの Invoke Permission (SourceArn) に必要です。" >&2; \
		echo "  例: export COGNITO_USER_POOL_ARN=arn:aws:cognito-idp:ap-northeast-1:123456789012:userpool/ap-northeast-1_xxxxxxxxx" >&2; \
		echo "詳細: docs/deployment-guide-prod.md" >&2; \
		exit 1; \
	fi; \
	if [ -z "$$LINE_CHANNEL_ID" ]; then \
		echo "WARNING: LINE_CHANNEL_ID が未設定です。template.yaml の既定値(空)を使用します（LINE ID トークン検証は無効）。" >&2; \
	fi; \
	OVERRIDES="Environment=$(1) OidcIssuer=$$OIDC_ISSUER OidcAudience=$$OIDC_AUDIENCE"; \
	[ -n "$$LIFF_ORIGIN" ]           && OVERRIDES="$$OVERRIDES LiffOrigin=$$LIFF_ORIGIN"; \
	[ -n "$$COGNITO_USER_POOL_ARN" ] && OVERRIDES="$$OVERRIDES CognitoUserPoolArn=$$COGNITO_USER_POOL_ARN"; \
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

deploy-prod: build ## Deploy to production environment (requires OIDC_ISSUER, OIDC_AUDIENCE, LIFF_ORIGIN, COGNITO_USER_POOL_ARN)
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

# ------------------------------------------------------------
# ネイティブ (ホスト) Ollama を使う場合の代替ターゲット。
# env.json の OLLAMA_HOST は既に host.docker.internal:11434 を指しているため、
# アプリ側の設定変更は不要。ホストの 11434 番ポートを Docker 版 (ollama サービス)
# とネイティブ版(Ollama.app / `ollama serve`) のどちらが握るかを切り替えるだけでよい。
# 併用不可（ポート競合）のため、ネイティブに切り替える前に `make local-ollama-stop`
# で Docker 版を停止すること。
# ------------------------------------------------------------
local-ollama-native-check: ## Check host-native Ollama is reachable on :11434
	@if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then \
		echo "Native Ollama is reachable: http://localhost:11434"; \
	else \
		echo "Native Ollama is NOT reachable on http://localhost:11434" >&2; \
		echo "  - Docker 版を使っていないか確認: make local-ollama-stop" >&2; \
		echo "  - Ollama.app を起動するか、ターミナルで 'ollama serve' を実行してください" >&2; \
		exit 1; \
	fi

local-ollama-native-pull: ## Pull Ollama model via host-installed ollama CLI (native mode)
	ollama pull $${OLLAMA_MODEL:-llama3.2}
	@echo "Model downloaded successfully (native)"

local-all: local-db local-keycloak local-ollama ## Start all local services
	@echo ""
	@echo "All local services started"
	@echo "  DynamoDB Local: http://localhost:8000"
	@echo "  DynamoDB Admin: http://localhost:8001"
	@echo "  Keycloak:       http://localhost:8180"
	@echo "  Ollama:         http://localhost:11434"
	@echo ""
	@echo "Next: run 'make local-api' in a separate terminal to start the API server"

local-all-native-ollama: local-db local-keycloak local-ollama-native-check ## Start all local services, using host-native Ollama instead of Docker
	@echo ""
	@echo "All local services started (using host-native Ollama)"
	@echo "  DynamoDB Local:  http://localhost:8000"
	@echo "  DynamoDB Admin:  http://localhost:8001"
	@echo "  Keycloak:        http://localhost:8180"
	@echo "  Ollama (native): http://localhost:11434"
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

# ------------------------------------------------------------
# サインアップ許可リスト運用 CLI (make allowlist-* / make verify-presignup)
# design: docs/design/signup-allowlist/architecture.md 「4. 運用 CLI」節を参照。
#
# 対象は実 AWS（--endpoint-url は指定しない）。認証はスイッチロール済みプロファイル
# 前提（例: AWS_PROFILE=xxx make allowlist-list ENV=prod）。リージョンは既存の
# AWS_REGION 変数に従う。テーブル名は memoru-signup-allowlist-$(ENV)。
#
# identifier 正規化: ID が "idp#" で始まればそのまま使用し、それ以外は小文字化して
# "email#" を前置する（LINE の identifier は必ず allowlist-list の出力からコピー
# すること。手入力しない）。email 側は前後の空白混入も除去する（services 側の
# _normalize_email の trim+小文字化と対称）。レシピ内で $(ID) / $(ALLOWLIST_NORMALIZED_ID)
# を展開する箇所は必ずダブルクォートで囲むこと（idp#... の "#" を含む値のため。シェルは
# ダブルクォート内の # をコメント開始と解釈しない。動作確認済み）。
# なお、レシピ外の素の変数代入行で # を直接書くと Make 自身のコメント開始として
# 解釈されてしまうため、下記 ALLOWLIST_NORMALIZED_ID の定義では \# エスケープを
# 使っている（レシピ内側で $(ID) を直接展開する分にはエスケープ不要。両方とも
# `make -n` のドライランで正しく展開されることを確認済み）。
#
# NOTE / ID の JSON 埋め込み: ID や NOTE にシングルクォートが含まれる値（例:
# NOTE="friend's account"）を、そのままシングルクォートで囲んだ --item / --key /
# --expression-attribute-values の JSON リテラルに埋め込むとシェル構文エラーになる。
# そのため python3 の json.dumps で JSON リテラル化した上で、シェル変数に代入してから
# ダブルクォート展開 ("$$VAR") で aws コマンドへ渡す（この形式ならシェル変数の中身に
# 任意の文字が含まれていても再解釈されず安全に1引数として渡る。verify-presignup で
# 既に使っている `VAR=$$(...)` パターンと同じ流儀）。
#
# 使い方:
#   make allowlist-add     ENV=prod ID=friend@example.com NOTE="大学の友人"
#   make allowlist-list    ENV=prod
#   make allowlist-approve ENV=prod ID='idp#line_u1234...' NOTE="..."
#   make allowlist-remove  ENV=prod ID=friend@example.com
#   make verify-presignup  ENV=prod COGNITO_USER_POOL_ARN=arn:aws:cognito-idp:...
# ------------------------------------------------------------
ALLOWLIST_COMMA := ,
ALLOWLIST_NOW_UTC := $(shell date -u +%Y-%m-%dT%H:%M:%SZ)
ALLOWLIST_NORMALIZED_ID = $(if $(filter idp\#%,$(ID)),$(ID),email\#$(shell printf '%s' "$(ID)" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]'))

allowlist-add: ## Add an approved entry to the signup allowlist (ENV, ID required; NOTE optional)
	@if [ -z "$(ENV)" ]; then \
		echo "ERROR: ENV が未設定です（例: ENV=prod）。" >&2; \
		exit 1; \
	fi
	@if [ -z "$(ID)" ]; then \
		echo "ERROR: ID が未設定です（例: ID=friend@example.com または ID='idp#line_u1234...'）。" >&2; \
		exit 1; \
	fi
	@ITEM_JSON=$$(ALLOWLIST_ID="$(ALLOWLIST_NORMALIZED_ID)" ALLOWLIST_NOTE="$(NOTE)" ALLOWLIST_NOW="$(ALLOWLIST_NOW_UTC)" python3 -c "import json, os; print(json.dumps({'identifier': {'S': os.environ['ALLOWLIST_ID']}, 'status': {'S': 'approved'}, 'note': {'S': os.environ['ALLOWLIST_NOTE']}, 'created_at': {'S': os.environ['ALLOWLIST_NOW']}, 'updated_at': {'S': os.environ['ALLOWLIST_NOW']}}))"); \
	aws dynamodb put-item \
		--region "$(AWS_REGION)" \
		--table-name "memoru-signup-allowlist-$(ENV)" \
		--item "$$ITEM_JSON" \
		--condition-expression "attribute_not_exists(identifier)" \
	|| { echo "ERROR: 既に登録済みです（pending からの承認は allowlist-approve を使用してください）。" >&2; exit 1; }

allowlist-list: ## List all entries in the signup allowlist (ENV required)
	@if [ -z "$(ENV)" ]; then \
		echo "ERROR: ENV が未設定です（例: ENV=prod）。" >&2; \
		exit 1; \
	fi
	aws dynamodb scan \
		--region "$(AWS_REGION)" \
		--table-name "memoru-signup-allowlist-$(ENV)" \
		--query 'Items[*].{identifier:identifier.S,status:status.S,note:note.S,display_name:display_name.S,created_at:created_at.S}' \
		--output table

allowlist-approve: ## Approve a pending signup allowlist entry, ttl を解除 (ENV, ID required; NOTE optional)
	@if [ -z "$(ENV)" ]; then \
		echo "ERROR: ENV が未設定です（例: ENV=prod）。" >&2; \
		exit 1; \
	fi
	@if [ -z "$(ID)" ]; then \
		echo "ERROR: ID が未設定です（例: ID='idp#line_u1234...'。allowlist-list の出力からコピーする）。" >&2; \
		exit 1; \
	fi
	@KEY_JSON=$$(ALLOWLIST_ID="$(ALLOWLIST_NORMALIZED_ID)" python3 -c "import json, os; print(json.dumps({'identifier': {'S': os.environ['ALLOWLIST_ID']}}))"); \
	VALUES_JSON=$$(ALLOWLIST_NOW="$(ALLOWLIST_NOW_UTC)" ALLOWLIST_NOTE="$(NOTE)" python3 -c "import json, os; values = {':approved': {'S': 'approved'}, ':pending': {'S': 'pending'}, ':now': {'S': os.environ['ALLOWLIST_NOW']}}; $(if $(NOTE),values[':note'] = {'S': os.environ['ALLOWLIST_NOTE']};) print(json.dumps(values))"); \
	aws dynamodb update-item \
		--region "$(AWS_REGION)" \
		--table-name "memoru-signup-allowlist-$(ENV)" \
		--key "$$KEY_JSON" \
		--update-expression 'SET #s = :approved, updated_at = :now$(if $(NOTE),$(ALLOWLIST_COMMA) note = :note,) REMOVE #t' \
		--expression-attribute-names '{"#s": "status", "#t": "ttl"}' \
		--expression-attribute-values "$$VALUES_JSON" \
		--condition-expression "attribute_exists(identifier) AND #s = :pending" \
	|| { echo "ERROR: 該当する pending がありません（ID の誤り、または既に approved 済みの可能性があります。allowlist-list で確認してください）。" >&2; exit 1; }

allowlist-remove: ## Remove an entry from the signup allowlist (ENV, ID required; 既存アカウントは削除されない)
	@if [ -z "$(ENV)" ]; then \
		echo "ERROR: ENV が未設定です（例: ENV=prod）。" >&2; \
		exit 1; \
	fi
	@if [ -z "$(ID)" ]; then \
		echo "ERROR: ID が未設定です（例: ID=friend@example.com または ID='idp#line_u1234...'）。" >&2; \
		exit 1; \
	fi
	@KEY_JSON=$$(ALLOWLIST_ID="$(ALLOWLIST_NORMALIZED_ID)" python3 -c "import json, os; print(json.dumps({'identifier': {'S': os.environ['ALLOWLIST_ID']}}))"); \
	aws dynamodb delete-item \
		--region "$(AWS_REGION)" \
		--table-name "memoru-signup-allowlist-$(ENV)" \
		--key "$$KEY_JSON"

verify-presignup: ## Verify Cognito PreSignUp trigger wiring / detect drift (ENV, COGNITO_USER_POOL_ARN required)
	@if [ -z "$(ENV)" ]; then \
		echo "ERROR: ENV が未設定です（例: ENV=prod）。" >&2; \
		exit 1; \
	fi
	@if [ -z "$(COGNITO_USER_POOL_ARN)" ]; then \
		echo "ERROR: COGNITO_USER_POOL_ARN が未設定です。" >&2; \
		echo "  例: export COGNITO_USER_POOL_ARN=arn:aws:cognito-idp:ap-northeast-1:123456789012:userpool/ap-northeast-1_xxxxxxxxx" >&2; \
		exit 1; \
	fi
	@CONFIGURED=$$(aws cognito-idp describe-user-pool \
			--region "$(AWS_REGION)" \
			--user-pool-id "$(lastword $(subst /, ,$(COGNITO_USER_POOL_ARN)))" \
			--query 'UserPool.LambdaConfig.PreSignUp' --output text); \
	EXPECTED=$$(aws lambda get-function-configuration \
			--region "$(AWS_REGION)" \
			--function-name "memoru-presignup-$(ENV)" \
			--query 'FunctionArn' --output text); \
	if [ -n "$$CONFIGURED" ] && [ "$$CONFIGURED" != "None" ] && [ "$$CONFIGURED" = "$$EXPECTED" ]; then \
		echo "OK: PreSignUp トリガー配線済み ($$CONFIGURED)"; \
	else \
		echo "ERROR: PreSignUp トリガーが未配線、またはドリフトしています（フェイルオープンの可能性）。" >&2; \
		echo "  UserPool.LambdaConfig.PreSignUp = $$CONFIGURED" >&2; \
		echo "  memoru-presignup-$(ENV) の FunctionArn = $$EXPECTED" >&2; \
		exit 1; \
	fi
