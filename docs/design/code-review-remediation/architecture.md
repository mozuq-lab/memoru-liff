# code-review-remediation アーキテクチャ設計

**作成日**: 2026-02-15
**関連要件定義**: [requirements.md](../../spec/code-review-remediation/requirements.md)
**ヒアリング記録**: [design-interview.md](design-interview.md)
**既存アーキテクチャ**: [architecture.md](../memoru-liff/architecture.md)

**【信頼性レベル凡例】**:

- 🔵 **青信号**: コードレビュー結果・既存設計文書・ユーザヒアリングを参考にした確実な設計
- 🟡 **黄信号**: コードレビュー結果・既存設計文書・ユーザヒアリングから妥当な推測による設計
- 🔴 **赤信号**: コードレビュー結果・既存設計文書・ユーザヒアリングにない推測による設計

---

## 設計概要 🔵

**信頼性**: 🔵 *コードレビュー結果 CODE_REVIEW_2026-02-15.md より*

既存の memoru-liff アーキテクチャ（サーバーレス + LIFF + Keycloak）は変更せず、**コードレベルの修正とインフラ設定の調整** により 19 件の Critical/High 問題を解消する。新規コンポーネントの追加は不要で、既存コンポーネント内の修正のみで対応する。

### 変更方針

- アーキテクチャパターン（サーバーレス）は **変更なし**
- コンポーネント構成は **変更なし**（新規 Lambda/テーブル追加なし）
- API エンドポイント 1 件追加（LINE 連携解除）
- インフラテンプレート 3 ファイル修正

---

## Phase 1: Critical 修正の設計

### 1.1 API ルート統一 (C-01) 🔵

**信頼性**: 🔵 *C-01: handler.py, template.yaml, api.ts の実装から確認*

**関連要件**: REQ-CR-001, REQ-CR-002

**問題**: handler.py の `@app.get("/cards/due")` と template.yaml の `Path: /reviews/due` が不一致

**設計決定**: 設計文書 `api-endpoints.md` の定義を正とする

```
正規パス: GET /cards/due  ← api-endpoints.md の定義

修正対象:
1. backend/template.yaml:293-298
   Path: /reviews/due → Path: /cards/due

2. frontend/src/services/api.ts
   パス定義を /cards/due に統一

3. backend/src/api/handler.py
   @app.get("/cards/due") → 変更なし（正）
```

**影響範囲**:

- SAM テンプレートの API Gateway リソース定義
- Frontend API クライアントのパス定数
- 既存テストのパス参照

---

### 1.2 API レスポンス契約統一 (C-02) 🔵

**信頼性**: 🔵 *C-02: Backend モデルと Frontend 型定義の比較から確認*

**関連要件**: REQ-CR-003

**設計決定**: Backend の Pydantic モデルを正として Frontend の TypeScript 型を合わせる（手動統一）

```
修正方針:
1. Backend Pydantic モデルのフィールド名・型を確認
2. Frontend TypeScript 型定義を Backend に合わせて修正
3. api.ts のレスポンス変換ロジックがあれば修正

対象ファイル:
- backend/src/models/card.py → 変更なし（正）
- backend/src/models/user.py → 変更なし（正）
- frontend/src/types/card.ts → Backend に合わせて修正
- frontend/src/types/user.ts → Backend に合わせて修正
```

---

### 1.3 OIDC コールバック実装 (C-03) 🔵

**信頼性**: 🔵 *C-03: CallbackPage.tsx と auth.ts の実装から確認*

**関連要件**: REQ-CR-005

**設計**:

```typescript
// frontend/src/pages/CallbackPage.tsx
// 修正: useEffect 内で authService.handleCallback() を呼び出す

useEffect(() => {
  const processCallback = async () => {
    try {
      await authService.handleCallback();
      navigate('/');  // ホームにリダイレクト
    } catch (error) {
      setError('認証に失敗しました');
    }
  };
  processCallback();
}, []);
```

**影響範囲**:

- `CallbackPage.tsx` のみ修正
- 既存の `authService.handleCallback()` メソッドは実装済み

---

### 1.4 DuePush Lambda IAM 権限修正 (C-04) 🔵

**信頼性**: 🔵 *C-04: template.yaml の IAM ポリシーから確認*

**関連要件**: REQ-CR-012

**設計**:

```yaml
# backend/template.yaml - DuePushJob Lambda の Policies に追加
- DynamoDBCrudPolicy:
    TableName: !Ref UsersTable
# または明示的に:
- Statement:
    - Effect: Allow
      Action:
        - dynamodb:UpdateItem
      Resource: !GetAtt UsersTable.Arn
```

---

### 1.5 204 レスポンス処理修正 (C-05) 🔵

**信頼性**: 🔵 *C-05: api.ts の実装から確認*

**関連要件**: REQ-CR-004, REQ-CR-101

**設計**:

```typescript
// frontend/src/services/api.ts - request() メソッド内
private async request<T>(url: string, options: RequestInit): Promise<T> {
  const response = await fetch(url, options);

  if (!response.ok) {
    // エラーハンドリング
  }

  // 204 No Content の場合は JSON パースをスキップ
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}
```

---

### 1.6 LINE 署名タイミング攻撃対策 (C-06) 🔵

**信頼性**: 🔵 *C-06: line_service.py の実装から確認*

**関連要件**: REQ-CR-009

**設計**:

```python
# backend/src/services/line_service.py
def verify_signature(self, body: str, signature: str | None) -> bool:
    """タイミングセーフな署名検証"""
    if signature is None:
        signature = ""

    hash_value = hmac.new(
        self.channel_secret.encode('utf-8'),
        body.encode('utf-8'),
        hashlib.sha256
    ).digest()

    expected = base64.b64encode(hash_value).decode('utf-8')

    # 常に compare_digest を通す（タイミング攻撃対策）
    return hmac.compare_digest(expected, signature)
```

**変更点**: `if not signature: return False` の早期リターンを削除

---

### 1.7 環境変数バリデーション有効化 (C-07) 🔵

**信頼性**: 🔵 *C-07: oidc.ts と main.tsx の実装から確認*

**関連要件**: REQ-CR-006

**設計**:

```typescript
// frontend/src/main.tsx
import { validateOidcConfig } from './config/oidc';

// アプリ起動前にバリデーション
validateOidcConfig();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

---

## Phase 2: High 修正の設計

### 2.1 datetime 統一 (H-01) 🔵

**信頼性**: 🔵 *H-01: 複数ファイルの実装から確認*

**関連要件**: REQ-CR-013

**設計**:

```python
# 全箇所で以下に統一:
from datetime import datetime, timezone

# Before (非推奨):
datetime.utcnow()

# After:
datetime.now(timezone.utc)
```

**修正対象** (4 箇所):

1. `backend/src/services/card_service.py:84`
2. `backend/src/services/srs.py:77`
3. `backend/src/services/review_service.py:290`
4. `backend/src/models/card.py:84`

---

### 2.2 CSP 強化 (H-02) 🔵

**信頼性**: 🔵 *H-02: liff-hosting/template.yaml の実装から確認、ヒアリングで方針確定*

**関連要件**: REQ-CR-010

**設計決定**: `unsafe-eval` のみ除去、`unsafe-inline` は LIFF SDK 互換性のため維持

```yaml
# infrastructure/liff-hosting/template.yaml
# Before:
ContentSecurityPolicy: "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' ..."

# After:
ContentSecurityPolicy: "default-src 'self'; script-src 'self' 'unsafe-inline' ..."
```

**リスク**: Vite の動的 import が `unsafe-eval` に依存している場合、ビルド設定の調整が必要

---

### 2.3 Keycloak HTTPS 強制 (H-03) 🔵

**信頼性**: 🔵 *H-03: keycloak/template.yaml の実装から確認*

**関連要件**: REQ-CR-011, REQ-CR-105

**設計**:

```yaml
# infrastructure/keycloak/template.yaml
# 環境パラメータで切り替え

Parameters:
  Environment:
    Type: String
    AllowedValues: [dev, prod]

# ECS Task Definition の環境変数
- Name: KC_HTTP_ENABLED
  Value: !If [IsProd, 'false', 'true']
- Name: KC_HOSTNAME_STRICT_HTTPS
  Value: !If [IsProd, 'true', 'false']

Conditions:
  IsProd: !Equals [!Ref Environment, 'prod']
```

---

### 2.4 LINE 連携解除 API (H-04) 🔵

**信頼性**: 🔵 *H-04: Frontend UI と Backend の実装差から確認*

**関連要件**: REQ-CR-018

**設計**: 詳細は [api-endpoints.md](api-endpoints.md) を参照

```python
# backend/src/api/handler.py に追加
@app.post("/users/me/unlink-line")
def unlink_line():
    user_id = get_user_id_from_jwt()
    user_service.unlink_line(user_id)
    return {"success": True}

# backend/src/services/user_service.py に追加
def unlink_line(self, user_id: str) -> None:
    self.users_table.update_item(
        Key={'user_id': user_id},
        UpdateExpression='REMOVE line_user_id',
        ConditionExpression='attribute_exists(line_user_id)'
    )
```

**SAM テンプレート追加**:

```yaml
UnlinkLineEvent:
  Type: Api
  Properties:
    Path: /users/me/unlink-line
    Method: post
    RestApiId: !Ref MemoruApi
```

---

### 2.5 通知 cron 修正 (H-05) 🔵

**信頼性**: 🔵 *H-05: template.yaml の実装から確認*

**関連要件**: REQ-CR-014

**設計**: cron 式とコメントを一致させる

```yaml
# backend/template.yaml
# コメントと cron を一致させる
# 5分間隔で実行（通知対象の時間帯チェックは Lambda 内で実施）
Schedule: rate(5 minutes)
```

---

### 2.6 Race Condition 対策 (H-06) 🔵

**信頼性**: 🔵 *H-06: card_service.py の実装から確認、ヒアリングで方式確定*

**関連要件**: REQ-CR-015

**設計決定**: ConditionExpression 方式

```python
# backend/src/services/card_service.py
# カード作成時の TransactWriteItems に ConditionExpression を追加
transact_items = [
    {
        'Update': {
            'TableName': 'memoru-users',
            'Key': {'user_id': {'S': user_id}},
            'UpdateExpression': 'SET card_count = card_count + :inc',
            'ConditionExpression': 'card_count < :limit',
            'ExpressionAttributeValues': {
                ':inc': {'N': '1'},
                ':limit': {'N': '2000'}
            }
        }
    },
    # ... cards, reviews の Put
]
```

**エラーハンドリング**: `TransactionCanceledException` をキャッチし、`CARD_LIMIT_EXCEEDED` エラーを返す

---

### 2.7 Bedrock リトライジッター (H-07) 🔵

**信頼性**: 🔵 *H-07: bedrock.py の実装から確認*

**関連要件**: REQ-CR-016

**設計**:

```python
# backend/src/services/bedrock.py
import random

def _retry_with_jitter(self, attempt: int) -> float:
    """Full Jitter Exponential Backoff"""
    max_delay = min(2 ** attempt, 30)  # 最大30秒
    return random.uniform(0, max_delay)
```

---

### 2.8 Token リフレッシュ (H-08) 🟡

**信頼性**: 🟡 *H-08: api.ts に機能なし、ヒアリングで interceptor 方式に確定*

**関連要件**: REQ-CR-007, REQ-CR-102, REQ-CR-103

**設計決定**: API クライアント interceptor パターン

```typescript
// frontend/src/services/api.ts
class ApiClient {
  private isRefreshing = false;
  private refreshPromise: Promise<void> | null = null;

  private async request<T>(url: string, options: RequestInit): Promise<T> {
    const response = await this.fetchWithAuth(url, options);

    if (response.status === 401) {
      // 並行リクエストのリフレッシュを1回に制限
      if (!this.isRefreshing) {
        this.isRefreshing = true;
        this.refreshPromise = this.refreshToken();
      }

      try {
        await this.refreshPromise;
        // リトライ
        return this.request<T>(url, options);
      } catch {
        // リフレッシュ失敗 → ログイン画面
        authService.login();
        throw new AuthError('Session expired');
      } finally {
        this.isRefreshing = false;
        this.refreshPromise = null;
      }
    }

    if (response.status === 204) return undefined as T;
    return response.json();
  }

  private async refreshToken(): Promise<void> {
    await authService.silentRenew();
  }
}
```

**設計ポイント**:

- `isRefreshing` フラグで並行リフレッシュを防止 (EDGE-CR-003)
- リフレッシュ失敗時はログイン画面にリダイレクト (REQ-CR-103)
- 既存の `authService` の `silentRenew()` メソッドを活用

---

### 2.9 ProtectedRoute 修正 (H-09) 🔵

**信頼性**: 🔵 *H-09: ProtectedRoute.tsx の実装から確認*

**関連要件**: REQ-CR-008, REQ-CR-104

**設計**:

```typescript
// frontend/src/components/common/ProtectedRoute.tsx
const ProtectedRoute: React.FC<Props> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();
  const [loginAttempted, setLoginAttempted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoading && !isAuthenticated && !loginAttempted) {
      setLoginAttempted(true);
      authService.login().catch((err) => {
        setError('ログインに失敗しました');
      });
    }
  }, [isLoading, isAuthenticated, loginAttempted]);

  if (error) return <ErrorPage message={error} />;
  if (isLoading) return <Loading />;
  if (!isAuthenticated) return <Loading />;
  return <>{children}</>;
};
```

**変更点**: render 中の `login()` 呼び出しを `useEffect` + `loginAttempted` フラグに変更

---

### 2.10 Context API メモ化 (H-10) 🔵

**信頼性**: 🔵 *H-10: CardsContext.tsx, AuthContext.tsx の実装から確認*

**関連要件**: REQ-CR-017

**設計**:

```typescript
// frontend/src/contexts/CardsContext.tsx
const CardsProvider: React.FC<Props> = ({ children }) => {
  const [cards, setCards] = useState<Card[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchCards = useCallback(async () => {
    setLoading(true);
    // ... fetch logic
    setLoading(false);
  }, []);

  const value = useMemo(
    () => ({ cards, loading, fetchCards }),
    [cards, loading, fetchCards]
  );

  return (
    <CardsContext.Provider value={value}>
      {children}
    </CardsContext.Provider>
  );
};
```

同様のパターンを `AuthContext.tsx` にも適用。

---

### 2.11 インフラコスト最適化 (H-11, H-12) 🟡

**信頼性**: 🟡 *H-11, H-12: Claude Infra が検出、設定値は推定*

**関連要件**: REQ-CR-413, REQ-CR-414

#### NAT Gateway 削除（開発環境）

```yaml
# infrastructure/keycloak/template.yaml
# Condition で環境に応じて NAT Gateway を作成/スキップ
Conditions:
  CreateNatGateway: !Equals [!Ref Environment, 'prod']

NatGateway:
  Type: AWS::EC2::NatGateway
  Condition: CreateNatGateway
  # ...

# 開発環境: ECS タスクを Public Subnet に配置
ECSService:
  Properties:
    NetworkConfiguration:
      AwsvpcConfiguration:
        Subnets: !If
          - CreateNatGateway
          - !Ref PrivateSubnets
          - !Ref PublicSubnets
        AssignPublicIp: !If
          - CreateNatGateway
          - DISABLED
          - ENABLED
```

#### CloudWatch Logs 保存期間

```yaml
# backend/template.yaml - 各 Lambda の LogGroup に追加
ApiLogGroup:
  Type: AWS::Logs::LogGroup
  Properties:
    RetentionInDays: !If [IsProd, 90, 14]
```

---

## コンポーネント別修正サマリー

### Backend 修正一覧 🔵

| ファイル | 修正内容 | 対応項目 |
|---------|---------|---------|
| `src/api/handler.py` | LINE unlink エンドポイント追加 | H-04 |
| `src/services/line_service.py` | 署名検証タイミング攻撃対策 | C-06 |
| `src/services/card_service.py` | datetime 統一、ConditionExpression | H-01, H-06 |
| `src/services/srs.py` | datetime 統一 | H-01 |
| `src/services/review_service.py` | datetime 統一 | H-01 |
| `src/services/user_service.py` | unlink_line メソッド追加 | H-04 |
| `src/services/bedrock.py` | リトライジッター追加 | H-07 |
| `src/models/card.py` | datetime 統一 | H-01 |
| `template.yaml` | パス修正、IAM 追加、cron 修正、LogGroup | C-01, C-04, H-05, H-12 |

### Frontend 修正一覧 🔵

| ファイル | 修正内容 | 対応項目 |
|---------|---------|---------|
| `src/pages/CallbackPage.tsx` | handleCallback 呼び出し | C-03 |
| `src/services/api.ts` | 204 処理、token リフレッシュ | C-05, H-08 |
| `src/types/card.ts` | Backend と型統一 | C-02 |
| `src/types/user.ts` | Backend と型統一 | C-02 |
| `src/config/oidc.ts` | 変更なし | - |
| `src/main.tsx` | validateOidcConfig 呼び出し | C-07 |
| `src/components/common/ProtectedRoute.tsx` | loginAttempted フラグ | H-09 |
| `src/contexts/CardsContext.tsx` | useMemo/useCallback | H-10 |
| `src/contexts/AuthContext.tsx` | useMemo/useCallback | H-10 |

### Infrastructure 修正一覧 🔵

| ファイル | 修正内容 | 対応項目 |
|---------|---------|---------|
| `infrastructure/liff-hosting/template.yaml` | CSP から unsafe-eval 除去 | H-02 |
| `infrastructure/keycloak/template.yaml` | HTTPS 強制、NAT Gateway 条件化 | H-03, H-11 |

---

## 非機能要件の実現方法

### セキュリティ強化 🔵

**信頼性**: 🔵 *コードレビュー結果より*

| 項目 | 実現方法 | 対応項目 |
|------|---------|---------|
| タイミング攻撃対策 | `hmac.compare_digest` 徹底 | C-06 |
| XSS 耐性 | CSP から `unsafe-eval` 除去 | H-02 |
| 資格情報保護 | 本番 Keycloak HTTPS 強制 | H-03 |

### パフォーマンス改善 🔵

**信頼性**: 🔵 *コードレビュー結果より*

| 項目 | 実現方法 | 対応項目 |
|------|---------|---------|
| 再レンダリング削減 | Context API メモ化 | H-10 |
| API 安定性 | Bedrock リトライジッター | H-07 |

### データ整合性 🔵

**信頼性**: 🔵 *コードレビュー結果より*

| 項目 | 実現方法 | 対応項目 |
|------|---------|---------|
| 日時一貫性 | `datetime.now(timezone.utc)` 統一 | H-01 |
| カード数制限 | DynamoDB ConditionExpression | H-06 |
| 重複通知防止 | IAM 権限修正 | C-04 |

### コスト最適化 🟡

**信頼性**: 🟡 *コスト削減額は推定*

| 項目 | 実現方法 | 年間削減額 |
|------|---------|----------|
| NAT Gateway | 開発環境で条件付き削除 | $360-480 |
| CloudWatch Logs | 保存期間設定 | $50-200 |

---

## 関連文書

- **データフロー**: [dataflow.md](dataflow.md)
- **API 仕様**: [api-endpoints.md](api-endpoints.md)
- **要件定義**: [requirements.md](../../spec/code-review-remediation/requirements.md)
- **既存アーキテクチャ**: [architecture.md](../memoru-liff/architecture.md)
- **既存 API 仕様**: [api-endpoints.md](../memoru-liff/api-endpoints.md)
- **既存 DB スキーマ**: [database-schema.md](../memoru-liff/database-schema.md)

---

## 信頼性レベルサマリー

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 21件 | 88% |
| 🟡 黄信号 | 3件 | 12% |
| 🔴 赤信号 | 0件 | 0% |

**品質評価**: ✅ 高品質（青信号が88%、赤信号なし）
