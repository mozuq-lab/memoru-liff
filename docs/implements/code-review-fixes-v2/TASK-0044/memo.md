# TDD開発メモ: LINE ID token verification + httpx unification

## 概要

- 機能名: LINE ID トークン検証 + httpx 統一
- 開発開始: 2026-02-21
- 現在のフェーズ: 完了（Refactorフェーズ完了）

## 関連ファイル

- 元タスクファイル: `docs/tasks/code-review-fixes-v2/TASK-0044.md`
- 要件定義: `docs/implements/code-review-fixes-v2/TASK-0044/requirements.md`
- テストケース定義: `docs/implements/code-review-fixes-v2/TASK-0044/testcases.md`
- 実装ファイル（変更対象）:
  - `backend/src/services/line_service.py`
  - `backend/src/api/handler.py`
  - `backend/src/models/user.py`
  - `backend/template.yaml`
  - `frontend/src/pages/LinkLinePage.tsx`
  - `frontend/src/services/liff.ts`（getLiffIdToken 追加）
  - `frontend/src/types/user.ts`
- テストファイル:
  - `backend/tests/unit/test_line_service_verify.py`
  - `backend/tests/unit/test_handler_link_line.py`
  - `backend/tests/test_template_params.py`
  - `frontend/src/pages/__tests__/LinkLinePage.idtoken.test.tsx`

## Redフェーズ（失敗するテスト作成）

### 作成日時

2026-02-21

### テストケース概要

| TC | 対象 | テストクラス | 信頼性 |
|----|------|-------------|--------|
| TC-01 | verify_id_token 成功 | `TestVerifyIdToken` | 🔵 |
| TC-02 | 無効トークン → UnauthorizedError | `TestVerifyIdToken` | 🔵 |
| TC-03 | 期限切れトークン → UnauthorizedError | `TestVerifyIdToken` | 🟡 |
| TC-04 | sub クレーム欠落 → UnauthorizedError | `TestVerifyIdToken` | 🔵 |
| TC-05 | LINE_CHANNEL_ID 未設定 → LineApiError | `TestVerifyIdToken` | 🔵 |
| TC-06 | ネットワーク障害 → LineApiError | `TestVerifyIdToken` | 🟡 |
| TC-07 | id_token 未送信 → 400 | `TestLinkLineHandler` | 🔵 |
| TC-08 | id_token 空文字 → 400 | `TestLinkLineHandler` | 🔵 |
| TC-09 | 有効な id_token → 連携成功 | `TestLinkLineHandler` | 🔵 |
| TC-10 | 検証失敗 → 401 | `TestLinkLineHandler` | 🔵 |
| TC-11 | requests import なし | `TestHttpxMigration` | 🔵 |
| TC-12 | reply_message が httpx 使用 | `TestHttpxMigration` | 🔵 |
| TC-13 | push_message が httpx 使用 | `TestHttpxMigration` | 🔵 |
| TC-14 | id_token フィールドで API 呼び出し | vitest | 🔵 |
| TC-15 | null IDToken → エラー表示 | vitest | 🟡 |
| TC-16 | line_user_id ではなく id_token 使用 | vitest | 🔵 |
| TC-17 | LineChannelId パラメータ存在確認 | `TestSAMTemplateLineChannelId` | 🔵 |
| TC-18 | LINE_CHANNEL_ID 環境変数存在確認 | `TestSAMTemplateLineChannelId` | 🔵 |

### テスト実行結果（Red フェーズ確認）

```
バックエンド: 15 failed in 0.62s（全て失敗 ✓）
フロントエンド: TC-14〜16 が失敗（getLiffIdToken 未実装、id_token 未使用 ✓）
```

### 期待される失敗

1. **TC-01〜06**: `AttributeError: 'LineService' object has no attribute 'verify_id_token'`
2. **TC-11**: `AssertionError: line_service.py should import httpx`
3. **TC-12〜13**: `AttributeError: module 'src.services.line_service' has no attribute 'httpx'`
4. **TC-07〜10**: `AttributeError: module 'src.api.handler' does not have the attribute 'line_service'`
5. **TC-17**: `AssertionError: template.yaml should have LineChannelId parameter`
6. **TC-18**: `AssertionError: LINE_CHANNEL_ID should be defined in environment variables`
7. **TC-14〜16**: `getLiffIdToken` 関数が存在しない、`linkLine` が `line_user_id` で呼ばれる

### 次のフェーズへの要求事項

Green フェーズで実装すべき内容:

#### バックエンド

1. **`line_service.py`**:
   - `import requests` → `import httpx` に変更（L12）
   - `__init__` に `self.channel_id = os.environ.get('LINE_CHANNEL_ID')` を追加
   - `verify_id_token(id_token: str) -> str` メソッドを実装:
     - `channel_id` 未設定チェック → `LineApiError("LINE_CHANNEL_ID not configured")`
     - `httpx.post("https://api.line.me/oauth2/v2.1/verify", data=..., timeout=10)` 呼び出し
     - 非 200 → `UnauthorizedError("LINE ID token verification failed")`
     - `sub` クレーム欠落 → `UnauthorizedError("Invalid ID token format")`
     - `httpx.RequestError` → `LineApiError("Failed to verify ID token: ...")`
   - `reply_message`: `requests.post` → `httpx.post`、`requests.RequestException` → `httpx.RequestError`
   - `push_message`: 同上

2. **`handler.py`**:
   - `from ..services.line_service import LineService, LineApiError` を追加
   - `line_service = LineService()` をモジュールレベルで追加
   - `link_line_account` 関数を変更:
     - `id_token = body.get('id_token')` で取得
     - `if not id_token: raise BadRequestError("id_token is required")`
     - `line_user_id = line_service.verify_id_token(id_token)`
     - `UnauthorizedError` を 401 でハンドリング

3. **`models/user.py`**:
   - `LinkLineRequest.line_user_id` → `id_token: str = Field(..., min_length=1, ...)`

4. **`template.yaml`**:
   - `Parameters` に `LineChannelId: {Type: String, Default: ''}` を追加
   - `Globals.Function.Environment.Variables` に `LINE_CHANNEL_ID: !Ref LineChannelId` を追加

#### フロントエンド

5. **`frontend/src/services/liff.ts`**: `getLiffIdToken()` 関数を追加
6. **`frontend/src/pages/LinkLinePage.tsx`**:
   - `import { getLiffIdToken }` を追加
   - `handleLinkLine`: `getLiffProfile()` → `getLiffIdToken()` に変更
   - `linkLine({ id_token: idToken })` で送信
7. **`frontend/src/types/user.ts`**: `LinkLineRequest.line_user_id` → `id_token: string`

## Refactorフェーズ（品質改善）

### 実施日時

2026-02-21

### 改善内容

| ファイル | 改善内容 | 信頼性 |
|---------|---------|--------|
| `backend/src/services/line_service.py` | ロガー追加、`verify_id_token` にロギング強化 | 🔵 |
| `backend/src/api/handler.py` | `except LineNotLinkedError as e:` の未使用変数 `e` を削除 | 🔵 |
| `frontend/src/pages/LinkLinePage.tsx` | ヘッダコメントにセキュリティ意図とTASK-0044参照を追加 | 🔵 |

### テスト実行結果

- バックエンド: 226 passed ✅
- フロントエンド: 251 passed ✅

### 品質評価

✅ 高品質 - 全テスト継続成功、セキュリティ問題なし、パフォーマンス問題なし
