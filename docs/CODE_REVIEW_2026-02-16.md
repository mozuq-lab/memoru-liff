# Memoru LIFF 全体コードレビュー結果（第2回）

**実施日**: 2026-02-16
**レビュアー**: Claude Opus 4.6 + OpenAI Codex (MCP経由)
**対象**: backend/, frontend/, infrastructure/ 全ソースコード
**方法**: 両レビュアーが独立にレビュー → 結果を突合・議論 → 統合

---

## 総合評価

全体的にアーキテクチャの設計は堅実で、型安全性（Pydantic v2, TypeScript strict mode）、AWSベストプラクティス（KMS暗号化、IAM最小権限、Powertools活用）への配慮が見られる。しかし、**API契約の不一致**が複数のレイヤーにわたって存在し、主要機能（設定保存・レビュー送信・LINE連携）が実環境で動作しない状態にある。前回レビュー（2026-02-15）から一部修正済みだが、Critical・Highレベルの問題が依然として残っている。

### 強み

- SM-2アルゴリズムの正確な実装と14+テストケースによるカバレッジ
- Pydantic v2による型安全なデータバリデーション（バックエンド）
- AWS Lambda Powertoolsの適切な使用（Logger, Tracer, Event Handler）
- DynamoDBテーブル設計とGSIのアクセスパターン適合性
- インフラの暗号化徹底（DynamoDB KMS, RDS暗号化, S3 AES256）
- 環境分離（dev/staging/prod）の条件分岐設計
- ProtectedRouteの `loginAttempted` フラグによる無限ループ防止
- CloudFrontの適切なキャッシュ戦略（index.html: no-cache, assets/: 長期キャッシュ）
- LINE Webhook署名検証のタイミングセーフ実装（hmac.compare_digest）

### 前回からの修正状況

| 前回ID | 問題 | 状況 |
|--------|------|------|
| C-03 | OIDC Callback未実装 | 修正済み |
| C-05 | 204 No Content JSON Parse Error | 修正済み |
| C-06 | LINE署名タイミング攻撃 | 修正済み |
| C-07 | 環境変数バリデーション未呼出 | 修正済み |
| C-01 | APIルート不一致 | **未修正** |
| C-02 | レスポンス契約不一致 | **未修正** |
| C-04 | DuePush Lambda権限不足 | 修正済み（UpdateItem追加） |

---

## Critical (P0: 先に直さないと主要機能が成立しない)

### CR-01: APIルーティング契約の破綻

**検出**: Claude Opus + Codex (合意)
**影響範囲**: backend, frontend, infrastructure, tests, docs
**影響**: 設定保存・レビュー送信・LINE連携がデプロイ後に動作しない

SAMテンプレートのイベント定義、Lambdaハンドラーのルート、フロントエンドAPIクライアントの3レイヤーでパスが不一致。

| 機能 | SAM template.yaml | handler.py | frontend api.ts | 状態 |
|------|-------------------|------------|-----------------|------|
| 設定更新 | `PUT /users/me` (L255-260) | `PUT /users/me/settings` (L151) | `PUT /users/me` (L142) | 3者不一致 |
| レビュー送信 | `POST /reviews` (L309) | `POST /reviews/<card_id>` (L493) | `POST /reviews/${cardId}` (L130) | SAMにパスパラメータなし |
| LINE連携 | **定義なし** | `POST /users/link-line` (L104) | `POST /users/me/link-line` (L149) | SAM未定義+パス不一致 |
| Due Cards | `GET /cards/due` (L303) | `GET /cards/due` (L469) | `GET /cards/due` (L120) | 一致 |

**改善案**:
1. OpenAPIスキーマを単一ソースとして定義
2. SAMイベント/ハンドラー/フロントAPIを同時修正して統一
3. CIで3レイヤーのパス一致を検証するテストを追加

---

### CR-02: `card_count` 前提トランザクションの整合性不備

**検出**: Codex → Claude Opus検証で確認
**影響範囲**: backend, data integrity
**影響**: カード作成が不正に失敗、上限判定の誤作動、削除後の件数不整合

```python
# card_service.py:106-127
client.transact_write_items(
    TransactItems=[
        {
            'Update': {
                'UpdateExpression': 'SET card_count = card_count + :inc',  # card_countが存在しない場合エラー
                'ConditionExpression': 'card_count < :limit',
            }
        },
        ...
    ]
)
```

問題点:
1. **ユーザー作成時に `card_count=0` が初期化されるか未確認** → 存在しない属性への加算でトランザクション失敗
2. **`TransactionCanceledException` を一律 `CardLimitExceededError` に変換** (L130-132) → 原因誤認
3. **`delete_card()` (L234-250) で `card_count` を減算していない** → 削除しても上限カウントが減らない
4. **handler.py L361 でユーザー存在保証なし** → カード作成前にユーザーレコードがない可能性

**改善案**:
1. `if_not_exists(card_count, :zero) + :inc` で安全に加算
2. `CancellationReasons` で正確にエラー分類
3. `delete_card()` でもトランザクションを使い `card_count - 1` を実行
4. カード作成前に `get_or_create_user()` を呼ぶ

---

## High (P1: リリース前に必須)

### H-01: LINE連携で本人性検証がない

**検出**: Codex → Claude Opus検証で確認
**影響範囲**: security, backend, frontend
**影響**: 悪意のあるユーザーが任意のLINE IDを自分のアカウントに紐付け可能

```typescript
// LinkLinePage.tsx:75-77
const updatedUser = await usersApi.linkLine({
  line_user_id: profile.userId,  // フロントから直接送信
});
```

サーバー側（handler.py L112-132）でLINEの本人性検証がない。LIFF SDKの `profile.userId` をそのまま信用している。

**改善案**: LIFF IDトークンをサーバーに送信し、LINEのIDトークン検証APIでサーバー側検証してから連携確定。

---

### H-02: レスポンス契約不一致 + LINE解除API未使用

**検出**: Codex → Claude Opus検証で確認
**影響範囲**: frontend, backend
**影響**: フロントエンドが期待する形式と異なるレスポンスで状態不整合

| エンドポイント | バックエンドの返却 | フロントの期待 |
|---------------|-------------------|---------------|
| `PUT /users/me/settings` | `{success, settings}` (handler.py:184) | `User` 型 (api.ts:141) |
| `POST /users/link-line` | `{success, message}` (handler.py:133) | `User` 型 (api.ts:148) |
| `POST /users/me/unlink-line` | `{success, data}` (handler.py:207) | **呼ばれない** |

さらに `LinkLinePage.tsx:94` の連携解除で `usersApi.updateUser()` を使っており、専用の `POST /users/me/unlink-line` エンドポイントを呼んでいない。

**改善案**:
1. レスポンスDTOをバックエンド/フロントで統一
2. `usersApi.unlinkLine()` を追加して `POST /users/me/unlink-line` を使用

---

### H-03: 通知時刻/タイムゾーン判定が未実装

**検出**: Codex → Claude Opus検証で確認
**影響範囲**: backend, product behavior
**影響**: ユーザー設定の通知時刻を無視して全時間帯で通知送信

```python
# notification_service.py:79-86
if user.last_notified_date == today_str:  # 日付チェックのみ
    result.skipped += 1
    continue
due_count = self.card_service.get_due_card_count(...)  # 時刻チェックなし
```

SAMテンプレート L399 のコメントには「notification time check is done in Lambda」と記載されているが、未実装。

**改善案**: `zoneinfo` でユーザーごとのローカル時刻を算出し、`notification_time` との一致時のみ送信。

---

### H-04: 環境変数名不一致（API URL）

**検出**: Codex → Claude Opus検証で確認
**影響範囲**: frontend, CI/CD
**影響**: CI/CDデプロイ後にAPIに接続できない

| 場所 | 変数名 |
|------|--------|
| `frontend/src/services/api.ts:14` | `VITE_API_BASE_URL` |
| `.github/workflows/deploy.yml:91` | `VITE_API_URL` |
| `.github/workflows/deploy.yml:169` | `VITE_API_URL` |

**改善案**: `VITE_API_BASE_URL` に統一し、`.env.example` と CI/CD を同期。

---

### H-05: `requests` ライブラリが依存に未宣言

**検出**: Codex → Claude Opus検証で確認
**影響範囲**: backend runtime
**影響**: Lambda実行時に `ImportError` のリスク

`backend/src/services/line_service.py:12` で `import requests` しているが、`backend/requirements.txt` には `requests` が含まれていない（`httpx` は宣言済み）。

**改善案**: `requests` を `requirements.txt` に追加するか、`httpx` に統一。統一推奨（`httpx` は async対応でLambdaとの親和性が高い）。

---

### H-06: OIDCクライアントIDの設定ドリフト

**検出**: Codex
**影響範囲**: auth, frontend, backend, infrastructure
**影響**: トークン検証の audience 不一致で認証失敗のリスク

| 場所 | クライアントID |
|------|--------------|
| `infrastructure/keycloak/realm-export.json` | `liff-client` |
| `backend/template.yaml:213` (JWT audience) | `liff-client` |
| `.github/workflows/deploy.yml:95` | `memoru-liff` |
| `frontend/e2e/fixtures/auth.fixture.ts:32` | `memoru-liff` |

**改善案**: 全レイヤーで `client_id` / `audience` を統一し、CIで整合チェック。

---

## Medium (P2: 早期改善推奨)

### M-01: Reviews テーブルの TTL が機能しない

**検出**: Claude Opus（独自発見） + Codex合意
**根拠**: `backend/template.yaml:159-161` でTTL有効化、`backend/src/services/review_service.py:242-253` で `expires_at` 未設定

DynamoDB TTLは `expires_at` 属性を見てレコードを自動削除するが、`put_item` 時にこの属性を設定していない。結果として、レビューデータが無限に蓄積しコスト増加。

**改善案**: `put_item` で `expires_at` を算出して設定（例: `reviewed_at + 90日` のUNIXタイムスタンプ）。

---

### M-02: レビュー記録失敗のサイレントキャッチ

**検出**: Claude Opus（独自発見）
**根拠**: `backend/src/services/review_service.py:255-258`

```python
except ClientError as e:
    # Log error but don't fail the review
    # Reviews table is for analytics, not critical
    pass  # ← ログすら残らない
```

コメントでは「Log error」と書いているが、実際には `pass` でログ出力なし。

**改善案**: `logger.warning()` で記録し、可観測性を維持。

---

### M-03: `limit` パラメータの直キャストで500エラー

**検出**: Codex → Claude Opus検証で確認
**根拠**: `backend/src/api/handler.py:316`, `backend/src/api/handler.py:478`

```python
limit = min(int(params.get("limit", 50)), 100)  # 不正値で ValueError → 500
```

**改善案**: `try/except` でバリデーションし、不正値は400レスポンスを返却。

---

### M-04: エラーレスポンス形式の不一致

**検出**: Codex → Claude Opus合意
**根拠**: `backend/src/api/handler.py:119` は `{"error": ...}` を返却、`frontend/src/services/api.ts:65` は `error.message` を期待

**改善案**: エラースキーマを `{message, code, details}` に統一し、フロントの解析ロジックを整合。

---

### M-05: 通知対象取得が全件 scan

**検出**: Codex
**根拠**: `backend/src/services/user_service.py` の `get_linked_users()` が `scan` ベース、5分ごと実行（template.yaml:398）

**改善案**: 通知時刻バケットGSI、または EventBridge + SQS によるイベント駆動へ変更。

---

### M-06: CSP に `unsafe-inline` が残存

**検出**: Codex
**根拠**: `infrastructure/liff-hosting/template.yaml:169`

```
script-src 'self' 'unsafe-inline' https://static.line-scdn.net;
style-src 'self' 'unsafe-inline';
```

LIFF SDKの制約で `script-src` には必要な場合があるが、`style-src` の `unsafe-inline` は Tailwind CSS のインラインスタイル対策で必要な可能性を確認した上で、nonce/hash方式への移行を検討。

**改善案**: LIFF SDK要件を確認し、可能な範囲でnonce/hash方式へ移行。

---

### M-07: 契約テスト・E2Eテストの不足

**検出**: Codex + Claude Opus合意
**根拠**: `frontend/src/services/__tests__/api.test.ts` は `fetch` モック中心、`frontend/e2e/auth.spec.ts:6` はスキップ

フロントのAPIテストは実サーバーの契約を検証しておらず、バックエンドとの不整合（CR-01, H-02）を検知できていない。

**改善案**: SAM local連携の契約テスト、主要フローのE2E実運用化。

---

### M-08: silent renew のコールバック経路不足

**検出**: Codex
**根拠**: `frontend/src/config/oidc.ts` で `silent_redirect_uri` 設定

OIDC silent renew用の `/silent-renew` ルートが `App.tsx` に未実装。トークン自動更新が失敗する可能性。

**改善案**: `/silent-renew` 用のHTML/ルートを実装。

---

## Low (P3: 継続改善)

### L-01: README の API 表が実装と不一致

**検出**: Codex
**根拠**: `README.md:227`, `README.md:234` vs 実装のパス

**改善案**: OpenAPIスキーマからの自動生成に移行。

---

### L-02: テストユーザーの平文パスワード記載

**検出**: Codex
**根拠**: `infrastructure/keycloak/test-users.json:20,47`, `infrastructure/keycloak/README.md:285`

**改善案**: 自動生成/別配布に移行し、コミット外へ。再利用禁止を明記。

---

## 修正優先順（推奨実行順序）

### Phase 1: Critical修正（P0）
1. **CR-01**: API契約統一（SAM template + handler + frontend api.ts を同時修正）
2. **CR-02**: card_count トランザクション修正（if_not_exists対応 + 削除時減算）

### Phase 2: High修正（P1）
3. **H-01**: LINE連携のサーバー側本人性検証
4. **H-02**: レスポンスDTO統一 + unlinkLine API使用
5. **H-03**: 通知時刻/タイムゾーン判定実装
6. **H-04**: 環境変数名統一
7. **H-05**: requests依存の解決（httpx統一推奨）
8. **H-06**: OIDCクライアントID統一

### Phase 3: Medium修正（P2）
9. **M-01**: Reviews TTL（expires_at設定）
10. **M-02**: レビュー記録失敗のログ出力
11. **M-03**: limit バリデーション
12. **M-04**: エラーレスポンス形式統一
13. **M-05**: 通知取得の scan 改善
14. **M-06**: CSP unsafe-inline 見直し
15. **M-07**: 契約テスト・E2E追加
16. **M-08**: silent renew ルート実装

### Phase 4: Low改善（P3）
17. **L-01**: README API表の自動生成化
18. **L-02**: テストユーザーパスワードの外部化

---

## スコアカード

| 観点 | スコア | 備考 |
|------|--------|------|
| アーキテクチャ | 8/10 | レイヤー分離は良好。API契約の単一ソース化が必要 |
| コード品質 | 7/10 | 型安全性は高い。エラー分類・入力検証に改善余地 |
| セキュリティ | 6/10 | 暗号化・PKCE・署名検証は良好。LINE認証検証・CSP・rate limitingが不足 |
| テスト | 7/10 | 単体テスト80%達成。契約テスト・E2Eが不足 |
| パフォーマンス | 6/10 | 現規模では問題なし。scan通知・TTL未活用がボトルネック |
| エラーハンドリング | 5/10 | カスタム例外は良好。レスポンス形式不統一・サイレントキャッチが問題 |
| フロントエンド | 6/10 | コンポーネント設計は良好。API契約・認証状態管理に課題 |
| バックエンド | 6/10 | サービス層パターンは良好。API契約・DDB整合性に課題 |
| インフラ | 7/10 | 暗号化・監視・環境分離は良好。CSP・通知スケーリングに課題 |
| ドキュメント | 7/10 | 設計書・タスク管理は充実。実装との乖離が問題 |
| **総合** | **6.5/10** | **Critical 2件を解消すれば7.5+へ改善見込み** |

---

## レビュー方法論

1. Claude Opus 4.6: プロジェクト全構造の探索 → 主要ファイルの精読 → 独自の問題検出
2. OpenAI Codex (MCP): 10観点での網羅的コードレビュー → 17項目の指摘
3. 統合: Claude Opusの検証結果とCodexの指摘を突合 → 追加で5件の独自発見（M-01, M-02等）を加えて最終統合
4. 議論: Codexに追加発見事項を共有し、最終的な重要度・優先順を合議で決定
