# Project Structure

## Organization Philosophy

モノレポ構成で `backend/` と `frontend/` を分離。バックエンドはレイヤードアーキテクチャ（handler → service → model）、フロントエンドは機能別ディレクトリ構成（pages, components, contexts, hooks, services, types）。インフラは `infrastructure/` に IaC として分離。

## Directory Patterns

### Backend: Layered Architecture
**Location**: `backend/src/`
**Purpose**: API ハンドラー → サービス → モデルの3層構造
**Patterns**:
- `api/handler.py`: Lambda Powertools の `APIGatewayHttpResolver` でルーティング。サブルーター（`api/handlers/` 内の `Router`）を `include_router()` で登録
- `services/`: ビジネスロジック層。各ドメインごとにサービスクラス（`UserService`, `CardService`, `ReviewService` など）
- `models/`: Pydantic モデル。リクエスト/レスポンスの型定義とバリデーション
- `services/prompts/`: AI プロンプトテンプレート。生成・採点・アドバイスごとに分離
- `webhook/`: LINE Webhook ハンドラー（`line_handler.py`）
- `jobs/`: スケジュール実行 Lambda（`due_push_handler.py`）

### Frontend: Feature-Directory Organization
**Location**: `frontend/src/`
**Purpose**: React SPA のソースコード
**Patterns**:
- `pages/`: ルーティング対応のページコンポーネント（1ページ1ファイル）
- `components/`: UI コンポーネント。共通部品は `components/common/`、機能別部品は `components/{feature}/`（例: `components/stats/`）に分離
- `contexts/`: React Context によるグローバル状態管理（`AuthContext`, `CardsContext`, `DecksContext`, `TutorContext`）
- `hooks/`: カスタムフック（`useAuth` など）
- `services/`: API 通信・認証・LIFF SDK のサービス層
- `types/`: TypeScript 型定義（`card.ts`, `user.ts`, `deck.ts`, `stats.ts`, `tutor.ts`）
- `config/`: 設定（OIDC 設定など）

### Infrastructure: IaC (AWS CDK)
**Location**: `infrastructure/cdk/`
**Purpose**: AWS CDK (TypeScript) によるインフラ定義
**Patterns**:
- `bin/app.ts`: CDK App エントリポイント。全スタック（dev/prod）を定義
- `lib/cognito-stack.ts`: Cognito UserPool スタック（OIDC + PKCE）
- `lib/keycloak-stack.ts`: Keycloak ECS/Fargate スタック（VPC + RDS + ALB）
- `lib/liff-hosting-stack.ts`: LIFF Hosting スタック（S3 + CloudFront + OAC）
- `infrastructure/keycloak/`: ローカル開発用 Keycloak 設定（realm-local.json, test-users.json）

### Backend IaC
**Location**: `backend/template.yaml`
**Purpose**: SAM テンプレートで Lambda, API Gateway, DynamoDB を定義

## Naming Conventions

- **Frontend ファイル**: PascalCase（`CardForm.tsx`, `ReviewPage.tsx`）
- **Frontend テスト**: `__tests__/OriginalName.test.tsx` （同階層に `__tests__/` ディレクトリ）
- **Backend ファイル**: snake_case（`card_service.py`, `line_handler.py`）
- **Backend テスト**: `tests/unit/test_*.py` or `tests/integration/test_*.py`
- **コンポーネント**: Named export（`export function CardForm` or `export const CardForm`）
- **サービスクラス**: PascalCase クラス名（`CardService`, `ReviewService`）

## Import Organization

### Frontend
```typescript
// 1. External libraries
import { BrowserRouter as Router } from 'react-router-dom';

// 2. Internal modules (path alias)
import { AuthProvider } from '@/contexts';
import { Layout } from '@/components/common';
import { HomePage } from '@/pages';
```

**Path Aliases**:
- `@/`: `frontend/src/` にマップ

**Barrel Exports**: 各ディレクトリに `index.ts` を配置し、re-export パターンを使用
- `@/pages` → `pages/index.ts`
- `@/contexts` → `contexts/index.ts`
- `@/components/common` → `components/common/index.ts`
- `@/types` → `types/index.ts`（`export type *` で型のみ re-export）

### Backend
```python
# 1. Standard library
import json
import os

# 2. Third-party
from aws_lambda_powertools import Logger, Tracer
from pydantic import ValidationError

# 3. Internal modules (relative from src/)
from models.card import CreateCardRequest
from services.card_service import CardService
```

**Import Style**: フラットなモジュール参照（`from models.card import ...`）。パッケージルートは `backend/src/`

## Code Organization Principles

- **サービスパターン**: ビジネスロジックはサービスクラスに集約。ハンドラーはリクエスト解析・レスポンス構築のみ
- **エラーハンドリング**: ドメイン固有の例外クラス（`CardNotFoundError`, `AIServiceError` 等）をサービス層で定義・送出し、ハンドラー層で HTTP レスポンスにマッピング
- **ファクトリーパターン**: AI サービスは `create_ai_service()` ファクトリーで環境変数に基づき実装を切り替え
- **Pydantic バリデーション**: 全リクエスト/レスポンスを Pydantic モデルで型安全に定義
- **Context パターン**: フロントエンドのグローバル状態は React Context で管理。`AuthProvider` → `CardsProvider` の順でネスト
- **仕様駆動開発**: `.kiro/specs/` に要件・設計・タスクを管理し、実装と仕様の整合性を維持

---
_Document patterns, not file trees. New files following patterns shouldn't require updates_
