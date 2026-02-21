# TASK-0044 Red フェーズ記録

**タスクID**: TASK-0044
**要件名**: code-review-fixes-v2
**機能名**: LINE ID token verification + httpx unification
**フェーズ**: Red (失敗テスト作成)
**作成日**: 2026-02-21

---

## 作成したテストケース一覧

| # | テストケース | ファイル | 信頼性 | 失敗理由 |
|---|-------------|---------|--------|---------|
| TC-01 | verify_id_token 成功 | `backend/tests/unit/test_line_service_verify.py` | 🔵 | `verify_id_token` メソッドが未実装 |
| TC-02 | 無効なトークン → UnauthorizedError | `backend/tests/unit/test_line_service_verify.py` | 🔵 | `verify_id_token` メソッドが未実装 |
| TC-03 | 期限切れトークン → UnauthorizedError | `backend/tests/unit/test_line_service_verify.py` | 🟡 | `verify_id_token` メソッドが未実装 |
| TC-04 | sub クレーム欠落 → UnauthorizedError | `backend/tests/unit/test_line_service_verify.py` | 🔵 | `verify_id_token` メソッドが未実装 |
| TC-05 | LINE_CHANNEL_ID 未設定 → LineApiError | `backend/tests/unit/test_line_service_verify.py` | 🔵 | `verify_id_token` メソッドが未実装 |
| TC-06 | ネットワーク障害 → LineApiError | `backend/tests/unit/test_line_service_verify.py` | 🟡 | `verify_id_token` メソッドが未実装 |
| TC-07 | id_token 未送信 → 400 | `backend/tests/unit/test_handler_link_line.py` | 🔵 | `handler.py` に `line_service` インスタンスが未設定 |
| TC-08 | id_token 空文字 → 400 | `backend/tests/unit/test_handler_link_line.py` | 🔵 | `handler.py` に `line_service` インスタンスが未設定 |
| TC-09 | 有効な id_token → 連携成功 | `backend/tests/unit/test_handler_link_line.py` | 🔵 | `handler.py` に `line_service` インスタンスが未設定 |
| TC-10 | 検証失敗 → 401 | `backend/tests/unit/test_handler_link_line.py` | 🔵 | `handler.py` に `line_service` インスタンスが未設定 |
| TC-11 | requests が import されていない | `backend/tests/unit/test_line_service_verify.py` | 🔵 | `line_service.py` が `requests` を使用中 |
| TC-12 | reply_message が httpx を使用 | `backend/tests/unit/test_line_service_verify.py` | 🔵 | `line_service.py` が `requests.post` を使用中 |
| TC-13 | push_message が httpx を使用 | `backend/tests/unit/test_line_service_verify.py` | 🔵 | `line_service.py` が `requests.post` を使用中 |
| TC-14 | id_token フィールドで API 呼び出し | `frontend/src/pages/__tests__/LinkLinePage.idtoken.test.tsx` | 🔵 | `LinkLinePage.tsx` が `line_user_id` を使用中 |
| TC-15 | null IDToken → エラー表示 | `frontend/src/pages/__tests__/LinkLinePage.idtoken.test.tsx` | 🟡 | `LinkLinePage.tsx` に `getLiffIdToken` 呼び出しなし |
| TC-16 | line_user_id ではなく id_token を使用 | `frontend/src/pages/__tests__/LinkLinePage.idtoken.test.tsx` | 🔵 | `LinkLinePage.tsx` が `line_user_id` を使用中 |
| TC-17 | LineChannelId パラメータ存在確認 | `backend/tests/test_template_params.py` | 🔵 | `template.yaml` に `LineChannelId` パラメータなし |
| TC-18 | LINE_CHANNEL_ID 環境変数存在確認 | `backend/tests/test_template_params.py` | 🔵 | `template.yaml` に `LINE_CHANNEL_ID` 環境変数なし |

---

## テスト実行結果

### バックエンドテスト（15 件）

```
FAILED tests/unit/test_line_service_verify.py::TestVerifyIdToken::test_verify_id_token_success
FAILED tests/unit/test_line_service_verify.py::TestVerifyIdToken::test_verify_id_token_failure_invalid_token
FAILED tests/unit/test_line_service_verify.py::TestVerifyIdToken::test_verify_id_token_failure_expired_token
FAILED tests/unit/test_line_service_verify.py::TestVerifyIdToken::test_verify_id_token_failure_missing_sub_claim
FAILED tests/unit/test_line_service_verify.py::TestVerifyIdToken::test_verify_id_token_failure_channel_id_not_configured
FAILED tests/unit/test_line_service_verify.py::TestVerifyIdToken::test_verify_id_token_failure_network_error
FAILED tests/unit/test_line_service_verify.py::TestHttpxMigration::test_line_service_uses_httpx_not_requests
FAILED tests/unit/test_line_service_verify.py::TestHttpxMigration::test_reply_message_uses_httpx
FAILED tests/unit/test_line_service_verify.py::TestHttpxMigration::test_push_message_uses_httpx
FAILED tests/unit/test_handler_link_line.py::TestLinkLineHandler::test_link_line_missing_id_token
FAILED tests/unit/test_handler_link_line.py::TestLinkLineHandler::test_link_line_empty_id_token
FAILED tests/unit/test_handler_link_line.py::TestLinkLineHandler::test_link_line_success_with_id_token
FAILED tests/unit/test_handler_link_line.py::TestLinkLineHandler::test_link_line_unauthorized_on_verification_failure
FAILED tests/test_template_params.py::TestSAMTemplateLineChannelId::test_line_channel_id_parameter_exists
FAILED tests/test_template_params.py::TestSAMTemplateLineChannelId::test_line_channel_id_env_var_in_globals_or_api_function
============================== 15 failed in 0.62s ==============================
```

### フロントエンドテスト（TC-14〜16）

`frontend/src/pages/__tests__/LinkLinePage.idtoken.test.tsx` を作成済み。
テストが失敗する理由:
- `liff` サービスに `getLiffIdToken` 関数が存在しない
- `LinkLinePage.tsx` が `line_user_id` を使用しており `id_token` を使用していない

---

## 失敗の主な理由

### 1. `verify_id_token` メソッド未実装 (TC-01〜TC-06)

`backend/src/services/line_service.py` に `verify_id_token` メソッドが存在しない。

### 2. `httpx` 未使用 (TC-11〜TC-13)

`backend/src/services/line_service.py` が `import requests` を使用しており、`httpx` を使用していない。

```python
# 現在のコード（L12）:
import requests
# → httpx に変更が必要
import httpx
```

### 3. `handler.py` に `line_service` インスタンスが未設定 (TC-07〜TC-10)

`backend/src/api/handler.py` に `line_service` のインスタンスが存在しない。

```python
# 現在のコード（L51-55）:
user_service = UserService()
card_service = CardService()
review_service = ReviewService()
bedrock_service = BedrockService()
# line_service が存在しない
```

### 4. `handler.py` の `link_line_account` が `id_token` を処理しない (TC-07〜TC-10)

現在のコードが `LinkLineRequest(line_user_id=...)` を使用しており、`id_token` の検証フローがない。

### 5. SAM テンプレートに `LineChannelId` が未定義 (TC-17〜TC-18)

`backend/template.yaml` の Parameters セクションに `LineChannelId` が存在しない。
`Globals.Function.Environment.Variables` に `LINE_CHANNEL_ID` が存在しない。

### 6. フロントエンドが `id_token` を送信しない (TC-14〜TC-16)

`frontend/src/pages/LinkLinePage.tsx` が `liff.getProfile()` を使用して `line_user_id` を直接送信している。

---

## Green フェーズで実装すべき内容

### バックエンド

1. **`line_service.py`**: `verify_id_token(id_token: str) -> str` メソッドを追加
   - `self.channel_id = os.environ.get('LINE_CHANNEL_ID')` を `__init__` に追加
   - `import requests` を `import httpx` に置換
   - `requests.post` を `httpx.post` に置換
   - `requests.RequestException` を `httpx.RequestError` に置換

2. **`handler.py`**: `link_line_account` 関数を ID トークン検証フローに変更
   - `from ..services.line_service import LineService, LineApiError` を追加
   - `line_service = LineService()` をモジュールレベルで追加
   - `id_token` の取得とバリデーション（400 エラー）
   - `line_service.verify_id_token(id_token)` 呼び出し
   - `UnauthorizedError` を 401 にマッピング

3. **`models/user.py`**: `LinkLineRequest` を `id_token: str` フィールドに変更

4. **`template.yaml`**:
   - `LineChannelId` パラメータを追加
   - `LINE_CHANNEL_ID: !Ref LineChannelId` を Globals に追加

### フロントエンド

5. **`frontend/src/services/liff.ts`** (または同等ファイル): `getLiffIdToken()` 関数を追加
6. **`frontend/src/pages/LinkLinePage.tsx`**: `handleLinkLine` を `id_token` 送信に変更
7. **`frontend/src/types/user.ts`**: `LinkLineRequest` を `id_token: string` に変更

---

## 信頼性レベルサマリー

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 15 | 83% |
| 🟡 黄信号 | 3 | 17% |
| 🔴 赤信号 | 0 | 0% |

---

**最終更新**: 2026-02-21
