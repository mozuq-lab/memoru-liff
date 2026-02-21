# TASK-0042: APIルート統一（3レイヤー整合性修正）- タスクノート

**作成日**: 2026-02-21
**関連タスク**: TASK-0042
**要件名**: code-review-fixes-v2
**ノートバージョン**: v1.0

---

## 1. 技術スタック

### 1.1 バックエンド

| 技術 | バージョン | 役割 |
|------|----------|------|
| **Python** | 3.12 | Lambda関数実装言語 |
| **AWS SAM** | - | Infrastructure as Code (IaC)、API定義 |
| **AWS Lambda Powertools** | 最新 | ロギング、トレース、エラー処理 |
| **Pydantic** | v2 | リクエスト/レスポンスの型検証 |
| **moto** | - | DynamoDB/AWSサービスのローカルモック |
| **pytest** | - | ユニットテスト・統合テストフレームワーク |

**重要な決定**:
- SAM テンプレートは「単一ソース・オブ・トゥルース (SSOT)」として機能
- API パスの定義は SAM → handler.py → frontend/api.ts の順に統一

### 1.2 フロントエンド

| 技術 | バージョン | 役割 |
|------|----------|------|
| **React** | 18+ | UI フレームワーク |
| **TypeScript** | 5+ | 型安全な開発 |
| **Vite** | 5+ | ビルドツール・開発サーバー |
| **oidc-client-ts** | - | OIDC 認証クライアント |
| **Vitest** | - | ユニットテストフレームワーク |

**重要な決定**:
- フロントエンドの API パスは backend/template.yaml で定義されたパスと完全一致すること
- API クライアント (`api.ts`) は全エンドポイントの "単一公開API"

### 1.3 インフラストラクチャ

| コンポーネント | 機能 |
|-------------|------|
| **API Gateway HTTP API** | REST API のエンドポイント定義 |
| **JWT Authorizer** | Keycloak OIDC トークン検証 |
| **DynamoDB** | ユーザー・カード・レビューのデータ永続化 |
| **CloudWatch Logs** | Lambda 関数ログ（環境別保持期間設定） |

---

## 2. 開発ルール・コーディング規約

### 2.1 API パス定義の優先順序

1. **設計文書** (`docs/design/code-review-fixes-v2/api-endpoints.md`) が最上位の定義
2. **SAM テンプレート** (`backend/template.yaml`) が実装の "SSOT"
3. **Lambda ハンドラー** (`backend/src/api/handler.py`) がパス実装
4. **フロントエンド API クライアント** (`frontend/src/services/api.ts`) が呼び出し

**ルール**: 3レイヤーのパスが完全一致していない場合は必ず修正する

### 2.2 HTTP メソッドとパスの命名規約

| HTTP メソッド | 用途 | パスパターン | 例 |
|-------------|------|-------------|-----|
| **GET** | リソース取得（一覧/単体） | `/resource` / `/resource/{id}` | `/users/me`, `/cards/{cardId}` |
| **POST** | リソース作成・アクション | `/resource` / `/resource/action` | `/cards`, `/reviews/{cardId}`, `/users/link-line` |
| **PUT** | リソース更新（全体置換） | `/resource/{id}` | `/cards/{cardId}`, `/users/me/settings` |
| **DELETE** | リソース削除 | `/resource/{id}` | `/cards/{cardId}` |

**ルール**:
- リソース名は英字小文字（ハイフン区切り）
- パスパラメータは `{camelCase}` 形式（SAM では `{paramName}` でハンドラーでは `param_name` に変換）
- ネストされたリソースは最大2階層まで

### 2.3 イベント定義の SAM テンプレート形式

**標準形式** (`backend/template.yaml`):

```yaml
EventName:
  Type: HttpApi
  Properties:
    ApiId: !Ref HttpApi
    Path: /resource/{id}/action
    Method: post
```

**重要なポイント**:
- 全 HttpApi イベントは `ApiId: !Ref HttpApi` で統一 API にバインド
- Method は小文字（`get`, `post`, `put`, `delete`）
- Path は先頭スラッシュで開始、パスパラメータは `{paramName}` 形式

### 2.4 Lambda ハンドラーのルート定義

**標準形式** (`backend/src/api/handler.py`):

```python
@app.get("/resource/{id}")
@tracer.capture_method
def get_resource(id: str):
    """Get resource by ID."""
    # Lambda Powertools APIGatewayHttpResolver が自動で id パラメータを注入
    ...
```

**重要なポイント**:
- パスパラメータはハンドラー関数の引数として受け取る
- SAM テンプレートのパスとデコレータのパスが完全一致すること
- 全エンドポイントに `@tracer.capture_method` で distributed tracing を有効化

### 2.5 フロントエンド API クライアント設計

**標準形式** (`frontend/src/services/api.ts`):

```typescript
async linkLine(data: LinkLineRequest): Promise<User> {
  return this.request<User>('/users/link-line', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}
```

**重要なポイント**:
- 全メソッドは `private request<T>()` を経由して呼び出す
- パスはバックエンドの API パスと完全一致
- リクエスト/レスポンス型は TypeScript インターフェイス

### 2.6 テスト規約

#### 2.6.1 バックエンド テスト

**ファイル構成**:
```
backend/tests/
├── unit/               # ユニットテスト（moto で AWS サービスモック）
│   └── test_*.py
└── integration/        # 統合テスト（実装待ち）
    └── test_*.py
```

**テスト命名規約**:
- テストメソッド: `test_<メソッド>_<条件>_<期待結果>`
- テストクラス: `Test<ClassName>`
- 例: `test_link_line_invalid_token_returns_401`

**重要なポイント**:
- Pytest fixtures で moto DynamoDB モックを共有
- 全テストで 80% 以上のコード カバレッジを目指す
- 非同期処理のテストは `@pytest.mark.asyncio` で標記

#### 2.6.2 フロントエンド テスト

**ファイル構成**:
```
frontend/src/
├── services/__tests__/
│   └── api.test.ts     # API クライアント テスト
```

**テスト命名規約** (Vitest):
- テストケース ID: `TC-XXX-YY` (例: `TC-027-01`)
- テスト説明: 日本語で詳細な目的・期待結果を記載
- モック設定をテスト前処理で実装

**重要なポイント**:
- global.fetch をモック化
- beforeEach で環境変数を stub、afterEach で restore
- 204 No Content の扱い: JSON パース をスキップして undefined を返す

---

## 3. 現在のコード状態・不一致箇所

### 3.1 3レイヤーのパス不一致

#### 3.1.1 設定更新エンドポイント

**現在の状態**:

| レイヤー | パス | 状態 |
|---------|------|------|
| SAM (template.yaml L259) | `/users/me` (PUT) | ❌ **不一致** |
| Handler (handler.py L151) | `/users/me/settings` (PUT) | ✓ 正 |
| Frontend (api.ts L142) | `/users/me` (PUT) | ❌ **不一致** |

**問題**: API Gateway が `/users/me` に PUT リクエストを送信すると ハンドラーの `/users/me/settings` マッピングに到達しない

**修正内容**:
```yaml
# SAM template.yaml - UpdateUser イベントを修正
UpdateUser:
  Type: HttpApi
  Properties:
    ApiId: !Ref HttpApi
    Path: /users/me/settings  # before: /users/me
    Method: PUT
```

#### 3.1.2 レビュー送信エンドポイント

**現在の状態**:

| レイヤー | パス | 状態 |
|---------|------|------|
| SAM (template.yaml L309) | `/reviews` (POST) | ❌ **不一致** |
| Handler (handler.py L493) | `/reviews/{card_id}` (POST) | ✓ 正 |
| Frontend (api.ts L130) | `/reviews/{cardId}` (POST) | ✓ 正 |

**問題**: SAM テンプレートにパスパラメータがないため、リクエストが正しくマッピングされない

**修正内容**:
```yaml
# SAM template.yaml - SubmitReview イベントを修正
SubmitReview:
  Type: HttpApi
  Properties:
    ApiId: !Ref HttpApi
    Path: /reviews/{cardId}  # before: /reviews
    Method: POST
```

#### 3.1.3 LINE 連携エンドポイント

**現在の状態**:

| レイヤー | パス | 状態 |
|---------|------|------|
| SAM (template.yaml) | ❌ **欠落** | 定義なし |
| Handler (handler.py L104) | `/users/link-line` (POST) | ✓ 実装済み |
| Frontend (api.ts L149) | `/users/me/link-line` (POST) | ❌ **不一致** |

**問題**:
1. SAM テンプレートに LINE 連携イベント定義がない → API Gateway でルーティングできない
2. フロントエンドが `/users/me/link-line` を使用 → ハンドラーの `/users/link-line` と不一致

**修正内容**:
```yaml
# SAM template.yaml に追加
LinkLineEvent:
  Type: HttpApi
  Properties:
    ApiId: !Ref HttpApi
    Path: /users/link-line
    Method: POST
```

```typescript
// frontend/src/services/api.ts を修正
async linkLine(data: LinkLineRequest): Promise<User> {
  return this.request<User>('/users/link-line', {  // before: '/users/me/link-line'
    method: 'POST',
    body: JSON.stringify(data),
  });
}
```

### 3.2 既存の正一致エンドポイント

以下のエンドポイントは既に 3レイヤーで一致しているため、修正不要:

```
✓ GET    /users/me
✓ POST   /users/me/unlink-line
✓ GET    /cards
✓ POST   /cards
✓ GET    /cards/{cardId}
✓ PUT    /cards/{cardId}
✓ DELETE /cards/{cardId}
✓ GET    /cards/due
✓ GET    /reviews/stats
✓ POST   /cards/generate
```

---

## 4. 設計文書・要件定義の参照

### 4.1 関連設計文書

| 文書 | パス | 関連度 |
|------|------|--------|
| **API仕様書** | `/docs/design/code-review-fixes-v2/api-endpoints.md` | 🔴 **必須** |
| **アーキテクチャ** | `/docs/design/code-review-fixes-v2/architecture.md` | 緑: 全体構成理解 |
| **データフロー** | `/docs/design/code-review-fixes-v2/dataflow.md` | 参考: 統合テスト設計 |
| **既存 API 仕様** | `/docs/design/memoru-liff/api-endpoints.md` | 参考: 変更なしエンドポイント |

### 4.2 要件定義への対応

本タスクは以下の要件を実装:

| 要件ID | 要件内容 | タスク内対応 |
|--------|---------|------------|
| **REQ-V2-001** | API パス統一 | SAM/handler/frontend の同期 |
| **REQ-V2-002** | レビュー送信パス修正 | `/reviews/{cardId}` に統一 |
| **REQ-V2-004** | 3レイヤー整合性テスト | test_template_routes.py 実装 |

---

## 5. 既存実装パターン・コード例

### 5.1 SAM テンプレート事例

**既存の正しいイベント定義** (`backend/template.yaml` L249-254):

```yaml
GetUser:
  Type: HttpApi
  Properties:
    ApiId: !Ref HttpApi
    Path: /users/me
    Method: GET
```

**特徴**:
- `Type: HttpApi` で HTTP API イベント指定
- `ApiId: !Ref HttpApi` で統一 API にバインド
- Method は小文字
- Path は `/` で開始、パスパラメータは `{paramName}` 形式

### 5.2 Lambda ハンドラーパターン

**既存の実装** (`backend/src/api/handler.py` L89-101):

```python
@app.get("/users/me")
@tracer.capture_method
def get_current_user():
    """Get current user information."""
    user_id = get_user_id_from_context()
    logger.info(f"Getting user info for user_id: {user_id}")

    try:
        user = user_service.get_or_create_user(user_id)
        return user.to_response().model_dump(mode="json")
    except Exception as e:
        logger.error(f"Error getting user: {e}")
        raise
```

**特徴**:
- `@app.get()` デコレータでルート定義
- `@tracer.capture_method` で distributed tracing
- `get_user_id_from_context()` で認証情報抽出
- 例外の適切なハンドリング

### 5.3 フロントエンド API クライアントパターン

**既存の実装** (`frontend/src/services/api.ts` L137-145):

```typescript
async getCurrentUser(): Promise<User> {
  return this.request<User>('/users/me');
}

async updateUser(data: UpdateUserRequest): Promise<User> {
  return this.request<User>('/users/me', {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}
```

**特徴**:
- ジェネリック型 `<T>` で戻り値の型安全性確保
- `private request<T>()` で統一 HTTP 処理
- Content-Type は自動設定
- Authorization ヘッダーは自動付加（`setAccessToken()`後）

### 5.4 テスト実装パターン

#### 5.4.1 バックエンドテスト例

**既存テスト** (`backend/tests/unit/test_user_service.py` L50-72):

```python
class TestUserServiceGetUser:
    """Tests for UserService.get_user method."""

    def test_get_user_success(self, user_service, dynamodb_table):
        """Test getting an existing user."""
        # Setup: create a user in the table
        table = dynamodb_table.Table("memoru-users-test")
        table.put_item(
            Item={
                "user_id": "test-user-id",
                "display_name": "Test User",
                "settings": {"notification_time": "09:00", "timezone": "Asia/Tokyo"},
                "created_at": "2024-01-01T00:00:00",
            }
        )

        # Execute
        user = user_service.get_user("test-user-id")

        # Assert
        assert user.user_id == "test-user-id"
        assert user.display_name == "Test User"
```

**特徴**:
- AAA パターン（Arrange, Act, Assert）
- Pytest fixtures で moto DynamoDB 共有
- 期待値の明確な assert

#### 5.4.2 フロントエンドテスト例

**既存テスト** (`frontend/src/services/__tests__/api.test.ts` L32-62):

```typescript
describe('ApiClient', () => {
  let mockFetch: ReturnType<typeof vi.fn>;

  beforeEach(async () => {
    vi.clearAllMocks();
    vi.resetModules();
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.com');
    mockFetch = vi.fn();
    global.fetch = mockFetch;
  });

  it('TC-027-01: 204 No Content レスポンスで undefined が返される', async () => {
    mockFetch.mockResolvedValue(new Response(null, { status: 204 }));
    const { apiClient } = await import('@/services/api');
    const result = await apiClient['request']<void>('/cards/card-123', {
      method: 'DELETE',
    });
    expect(result).toBeUndefined();
  });
});
```

**特徴**:
- Vitest の `vi.fn()` でモック設定
- テストケース ID (`TC-027-01`) で識別性向上
- beforeEach/afterEach で環境初期化・復元

---

## 6. 実装上の制約・考慮事項

### 6.1 制約事項

| 制約 | 内容 | 理由 |
|------|------|------|
| **SAM SSOT** | SAM テンプレートが API パスの定義元 | インフラストラクチャと実装の同期 |
| **後方互換性** | 既存テストは修正後も通ること | レグレッション防止 |
| **パス完全一致** | 3レイヤーのパスが byte-by-byte 同じ | API Gateway マッピング失敗防止 |
| **テストカバレッジ** | 80% 以上 | CLAUDE.md 指定要件 |

### 6.2 環境依存

| 環境 | 設定 | 影響 |
|------|------|------|
| **開発環境 (dev)** | ローカル API デバッグ可能 | SAM ローカル実行テスト必須 |
| **本番環境 (prod)** | CORS 設定に `https://liff.line.me` のみ | テスト環境と異なる可能性 |

### 6.3 依存タスク

**前提タスク**: なし（独立実装可能）

**後続タスク**:
- TASK-0044: LINE連携本人性検証（リクエスト/レスポンス型の変更）
- TASK-0045: レスポンスDTO統一（User 型統一）

---

## 7. 修正チェックリスト

このタスクの完了条件:

### 7.1 SAM テンプレート修正

- [ ] `/users/me` (PUT) → `/users/me/settings` (PUT) に修正
- [ ] `/reviews` (POST) → `/reviews/{cardId}` (POST) に修正
- [ ] `/users/link-line` (POST) イベント定義を新規追加
- [ ] SAM ビルド確認: `cd backend && make build`

### 7.2 フロントエンド API クライアント修正

- [ ] `linkLine()` メソッドのパス: `/users/me/link-line` → `/users/link-line`
- [ ] `updateUser()` メソッドのパス確認（既に `/users/me` で正しい）
- [ ] `submitReview()` メソッドのパス確認（既に `/reviews/{cardId}` で正しい）

### 7.3 テスト実装

- [ ] `backend/tests/test_template_routes.py` 作成（SAM パスバリデーション）
- [ ] `frontend/src/services/__tests__/api.test.ts` テスト追加（linkLine パス確認）
- [ ] 既存テスト実行: `cd backend && make test`
- [ ] フロントエンドテスト実行: `cd frontend && npm test`

### 7.4 品質指標

- [ ] テストカバレッジ 80% 以上
- [ ] 既存テスト全てパス
- [ ] Linter エラー なし
- [ ] 型チェック (TypeScript) エラー なし

---

## 8. 参考リソース

### 8.1 AWS SAM ドキュメント

- [AWS SAM CLI Reference](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/)
- [HttpApi Event - SAM](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-resource-httpapi.html)

### 8.2 Lambda Powertools (Python)

- [Powertools - GitHub](https://github.com/aws-powertools/powertools-lambda-python)
- [APIGatewayHttpResolver - docs](https://docs.powertools.aws.dev/latest/core/event_handler/api_gateway/)

### 8.3 フロントエンド テストツール

- [Vitest - Official Docs](https://vitest.dev/)
- [Testing Library - fetch mocking](https://testing-library.com/)

### 8.4 プロジェクト内ドキュメント

- [CLAUDE.md - 開発ガイドライン](/Volumes/external/dev/memoru-liff/CLAUDE.md)
- [API仕様 - api-endpoints.md](/Volumes/external/dev/memoru-liff/docs/design/code-review-fixes-v2/api-endpoints.md)
- [要件定義 - requirements.md](/Volumes/external/dev/memoru-liff/docs/spec/code-review-fixes-v2/requirements.md)

---

## 9. タスク実装のステップ

### ステップ 1: テスト設計 (`/tsumiki:tdd-testcases`)

このフェーズで以下のテストケースを設計:

**テストケース 1: SAM テンプレートパス検証**
- ファイル: `backend/tests/test_template_routes.py`
- 内容: template.yaml をパース、3つのエンドポイント定義を確認

**テストケース 2: フロントエンド API パス確認**
- ファイル: `frontend/src/services/__tests__/api.test.ts`
- 内容: linkLine() メソッドが `/users/link-line` へリクエスト送信を確認

**テストケース 3: 既存テスト回帰**
- 実行: `cd backend && make test`
- 確認: 全テスト通過

### ステップ 2: テスト実装 (`/tsumiki:tdd-red`)

テストを実装（最初は失敗して OK）

### ステップ 3: 実装修正 (`/tsumiki:tdd-green`)

テストを通すための最小限の実装:
1. SAM template.yaml 修正
2. frontend/src/services/api.ts 修正

### ステップ 4: リファクタリング (`/tsumiki:tdd-refactor`)

コード品質向上:
- コメント追加
- エラーメッセージ精緻化
- 不要なコード削除

### ステップ 5: 確認 (`/tsumiki:tdd-verify-complete`)

完了条件チェック:
- テストカバレッジ 80% 以上
- 全テスト通過
- 3レイヤーパス一致確認

---

## 10. よくある質問 (FAQ)

**Q: SAM テンプレートのパスを修正したら、デプロイしないといけない？**

A: 開発環境ではローカル SAM で動作確認を推奨（`make local-api`）。本番デプロイはユーザーが手動実行。

**Q: フロントエンドのパス修正で既存コンポーネントが影響を受ける？**

A: `api.ts` は全エンドポイントの公開 API のため、影響は限定的。型チェック (`npm run type-check`) で確認。

**Q: テスト YAML をパース する場合、どのライブラリを使う？**

A: Python の `yaml` ライブラリ（pytest で `pip install pyyaml`）

**Q: 204 No Content レスポンスの処理は？**

A: frontend/src/services/api.ts の `request()` メソッドで既に実装済み（JSON パース をスキップ）

---

## 11. 変更履歴

| バージョン | 日付 | 変更内容 |
|-----------|------|---------|
| v1.0 | 2026-02-21 | 初版作成 |

