# TASK-0044 実装ノート: LINE ID トークン検証 + httpx 統一

**作成日**: 2026-02-21
**タスクタイプ**: TDD (Test-Driven Development)
**推定工数**: 8時間
**実装状態**: 準備完了

---

## 1. タスク概要

TASK-0044 は、LINE 連携時のセキュリティ強化と HTTP クライアントライブラリの統一を目的とする。

### 1.1 主な変更内容

| 項目 | 現状 | 変更後 |
|------|------|--------|
| **フロントエンド** | `liff.getProfile()` で line_user_id を直接送信 | `liff.getIDToken()` で ID トークンを送信 |
| **バックエンド検証** | line_user_id の検証なし | LINE API で ID トークンを検証 |
| **HTTP クライアント** | requests ライブラリ | httpx ライブラリ |
| **LINE_CHANNEL_ID** | ハードコード/環境変数未設定 | SAM テンプレートの環境変数として定義 |
| **セキュリティ** | フロントエンド信頼依存 | サーバー側検証による強化 |

### 1.2 信頼性レベル

- **全体評価**: 🔵 高品質 (88% 青信号)
  - 🔵 実装詳細: 6/6 (100%)
  - 🔵 単体テスト: 5/6 (83%)
  - 🔵 統合テスト: 1/1 (100%)
  - 🟡 UI/UX要件: 3/4 (75%) - エラーメッセージ文言は推測

---

## 2. 依存関係と前提条件

### 2.1 前提タスク

- **TASK-0042**: APIルート統一（完了）
  - SAM テンプレートに LINE 連携イベント定義済み
  - `/users/link-line` エンドポイント実装済み

### 2.2 後続タスク

- **TASK-0045**: レスポンスDTO統一 + unlinkLine API 使用

### 2.3 外部依存関係

- **LINE Developers Console**: Channel ID と Access Token の取得
- **AWS Secrets Manager**: LINE 認証情報の保管
- **LIFF SDK**: `getIDToken()` API 対応確認

---

## 3. 実装詳細分析

### 3.1 フロントエンド変更（LinkLinePage.tsx）

#### 現状コード (L75-77)

```typescript
const updatedUser = await usersApi.linkLine({
  line_user_id: profile.userId,
});
```

#### 変更後のコード

```typescript
// IDトークンを取得
const idToken = liff.getIDToken();
if (!idToken) {
  throw new Error('IDトークンを取得できませんでした');
}

// サーバーに送信
const updatedUser = await usersApi.linkLine({
  id_token: idToken,
});
```

#### 実装ポイント

- `liff.getIDToken()` は `liff.getProfile()` より先に呼び出す必要あり
- ID トークン取得失敗時の例外ハンドリング必須
- 既存の `handleLinkLine` 関数内で実装
- ローディング状態の保持（既存処理を維持）

---

### 3.2 API クライアント型変更（api.ts）

#### 現状

```typescript
async linkLine(data: LinkLineRequest): Promise<User> {
  return this.request<User>('/users/link-line', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}
```

#### 変更後

```typescript
async linkLine(data: { id_token: string }): Promise<User> {
  return this.request<User>('/users/link-line', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}
```

#### 型定義の検討

現在の `LinkLineRequest` モデル:

```typescript
export interface LinkLineRequest {
  line_user_id: string;  // 変更対象
}
```

2つの選択肢:

1. **新型定義**: `LinkLineIdTokenRequest` を追加
2. **型置換**: `LinkLineRequest` を修正（推奨）

リクエスト構造の根本的な変更なため、型定義の置換が適切。

---

### 3.3 バックエンド handler.py 変更

#### 現状 (L104-149)

```python
@app.post("/users/link-line")
@tracer.capture_method
def link_line_account():
    """Link LINE account to current user."""
    user_id = get_user_id_from_context()
    logger.info(f"Linking LINE account for user_id: {user_id}")

    try:
        body = app.current_event.json_body
        request = LinkLineRequest(**body)  # line_user_id の検証
    except ValidationError as e:
        logger.warning(f"Validation error: {e}")
        return Response(...)

    try:
        user_service.get_or_create_user(user_id)
        user_service.link_line(user_id, request.line_user_id)  # 直接連携
        return LinkLineResponse(success=True, message="...").model_dump()
```

#### 変更後

```python
@app.post("/users/link-line")
@tracer.capture_method
def link_line_account():
    """Link LINE account to current user."""
    user_id = get_user_id_from_context()
    logger.info(f"Linking LINE account for user_id: {user_id}")

    try:
        body = app.current_event.json_body
        id_token = body.get('id_token')

        if not id_token:
            raise BadRequestError("id_token is required")
    except Exception as e:
        logger.warning(f"Validation error: {e}")
        return Response(...)

    try:
        # LINE ID トークンを検証して line_user_id を取得
        line_user_id = line_service.verify_id_token(id_token)

        user_service.get_or_create_user(user_id)
        user_service.link_line(user_id, line_user_id)  # 検証後に連携
        return LinkLineResponse(success=True, message="...").model_dump()
    except UnauthorizedError:
        return Response(
            status_code=401,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "LINE ID token verification failed"}),
        )
```

#### 実装ポイント

- ID トークン未送信時は `BadRequestError` (400) 返却
- 検証失敗時は `UnauthorizedError` (401) 返却
- `line_service.verify_id_token()` の例外ハンドリング必須

---

### 3.4 LINE サービス: verify_id_token 実装

#### 現状 (line_service.py)

```python
import requests  # L12

class LineService:
    def reply_message(self, reply_token: str, messages: List[Dict[str, Any]]) -> bool:
        ...
        response = requests.post(url, headers=headers, json=payload, timeout=10)  # L223
        response.raise_for_status()
        return True
```

#### 変更後

```python
import httpx  # requests を置換

class LineService:
    def __init__(self, ...):
        ...
        self.channel_id = os.environ.get('LINE_CHANNEL_ID')

    def verify_id_token(self, id_token: str) -> str:
        """LIFF IDトークンをLINE APIで検証し、line_user_idを返す

        Args:
            id_token: LIFF が返した ID トークン

        Returns:
            検証済みの line_user_id ('sub' クレーム値)

        Raises:
            UnauthorizedError: ID トークン検証失敗時
        """
        if not self.channel_id:
            raise LineApiError("LINE_CHANNEL_ID not configured")

        try:
            response = httpx.post(
                'https://api.line.me/oauth2/v2.1/verify',
                data={
                    'id_token': id_token,
                    'client_id': self.channel_id,
                },
                timeout=10,
            )

            if response.status_code != 200:
                logger.warning(f"ID token verification failed: {response.status_code}")
                raise UnauthorizedError("LINE ID token verification failed")

            data = response.json()
            line_user_id = data.get('sub')

            if not line_user_id:
                logger.warning("ID token response missing 'sub' claim")
                raise UnauthorizedError("Invalid ID token format")

            return line_user_id
        except httpx.RequestException as e:
            logger.error(f"ID token verification request failed: {e}")
            raise LineApiError(f"Failed to verify ID token: {e}") from e

    def reply_message(self, ...):
        # requests → httpx に変更
        response = httpx.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        return True
```

#### LINE API 仕様

- **エンドポイント**: `https://api.line.me/oauth2/v2.1/verify`
- **リクエスト形式**: `application/x-www-form-urlencoded`
- **パラメータ**:
  - `id_token`: LIFF から取得したトークン
  - `client_id`: LINE Channel ID
- **レスポンス**: JSON
  ```json
  {
    "iss": "https://access.line.me",
    "sub": "U1234567890abcdef1234567890abcdef",
    "aud": "1234567890",
    "exp": 1234567890,
    "iat": 1234567890,
    "nonce": "nonce-value"
  }
  ```
- **エラーレスポンス**: 400 または 401 ステータス
  ```json
  {
    "error": "invalid_request",
    "error_description": "..."
  }
  ```

#### ID トークン有効期限

- 典型値: 発行後 数分～数十分
- テスト時: 有効期限切れのトークンでの 400 エラーをシミュレート必須

---

### 3.5 requirements.txt 更新

#### 現状

```
boto3>=1.34.0
pydantic>=2.5.0
python-jose[cryptography]>=3.3.0
httpx>=0.26.0  # 既に存在
aws-lambda-powertools>=2.32.0
```

#### 確認事項

- httpx はすでに requirements.txt に記載されている（L4: `httpx>=0.26.0`）
- requests ライブラリは記載されていない（import されているが宣言されていない不具合）

#### 変更作業

1. httpx のバージョン確認: 最新は `>=0.27.0` への更新を検討
2. requests を明示的に削除しないが、imports から除去

---

### 3.6 SAM テンプレート: 環境変数追加

#### 現状 (template.yaml)

```yaml
Globals:
  Function:
    Environment:
      Variables:
        ENVIRONMENT: !Ref Environment
        USERS_TABLE: !Ref UsersTable
        CARDS_TABLE: !Ref CardsTable
        REVIEWS_TABLE: !Ref ReviewsTable
        LOG_LEVEL: !If [IsProd, INFO, DEBUG]
```

#### 変更後

```yaml
Parameters:
  LineChannelId:
    Type: String
    Default: ''
    Description: LINE Login Channel ID for ID token verification
    NoEcho: false  # 非機密情報

Globals:
  Function:
    Environment:
      Variables:
        ENVIRONMENT: !Ref Environment
        USERS_TABLE: !Ref UsersTable
        CARDS_TABLE: !Ref CardsTable
        REVIEWS_TABLE: !Ref ReviewsTable
        LOG_LEVEL: !If [IsProd, INFO, DEBUG]
        LINE_CHANNEL_ID: !Ref LineChannelId
```

#### 実装ポイント

- LINE Channel ID は **公開情報** のため `NoEcho: false`
- Access Token と Secret はすでに Secrets Manager で管理
- ApiFunction と LineWebhookFunction の両方に環境変数を設定
- デプロイ時にパラメータとして指定: `aws cloudformation deploy --parameter-overrides LineChannelId=1234567890`

---

## 4. テスト戦略

### 4.1 単体テスト: バックエンド

#### テストケース1: ID トークン検証成功

```python
def test_verify_id_token_success():
    """Valid LIFF ID token is verified and line_user_id is extracted."""
    # Arrange
    service = LineService(channel_id="test-channel-id")
    mock_response = {
        "sub": "U1234567890abcdef1234567890abcdef",
        "iss": "https://access.line.me",
    }

    # Act & Assert
    with patch('httpx.post') as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_response

        result = service.verify_id_token("valid-id-token")

        assert result == "U1234567890abcdef1234567890abcdef"
        mock_post.assert_called_once_with(
            'https://api.line.me/oauth2/v2.1/verify',
            data={'id_token': 'valid-id-token', 'client_id': 'test-channel-id'},
            timeout=10,
        )
```

#### テストケース2: ID トークン検証失敗（無効なトークン）

```python
def test_verify_id_token_failure_invalid_token():
    """Invalid ID token returns 400 and raises UnauthorizedError."""
    # Arrange
    service = LineService(channel_id="test-channel-id")

    # Act & Assert
    with patch('httpx.post') as mock_post:
        mock_post.return_value.status_code = 400

        with pytest.raises(UnauthorizedError):
            service.verify_id_token("invalid-id-token")
```

#### テストケース3: ID トークン検証失敗（有効期限切れ）

```python
def test_verify_id_token_failure_expired():
    """Expired ID token returns 401 and raises UnauthorizedError."""
    # Arrange
    service = LineService(channel_id="test-channel-id")

    # Act & Assert
    with patch('httpx.post') as mock_post:
        mock_post.return_value.status_code = 401

        with pytest.raises(UnauthorizedError):
            service.verify_id_token("expired-id-token")
```

#### テストケース4: handler での ID トークン未送信

```python
def test_link_line_missing_id_token():
    """Missing id_token in request body returns 400 error."""
    # Arrange
    event = {
        "requestContext": {"authorizer": {"jwt": {"claims": {"sub": "user-123"}}}},
        "body": json.dumps({}),  # id_token 未送信
    }

    # Act
    response = handler(event, context)

    # Assert
    assert response['statusCode'] == 400
    assert 'id_token is required' in response['body']
```

#### テストケース5: httpx 使用の確認

```python
def test_line_service_uses_httpx():
    """LineService uses httpx instead of requests."""
    # Arrange: line_service.py の import を検査
    import src.services.line_service as ls_module

    # Assert
    assert hasattr(ls_module, 'httpx'), "httpx should be imported"
    assert not hasattr(ls_module, 'requests'), "requests should not be imported"
```

---

### 4.2 単体テスト: フロントエンド

#### テストケース6: ID トークン送信

```typescript
it('LINE連携ボタン押下時にIDトークンが送信される', async () => {
  // Arrange
  const mockIdToken = 'test-id-token-xyz';
  mockGetLiffIdToken.mockResolvedValue(mockIdToken);
  mockLinkLine.mockResolvedValue(mockLinkedUser);

  // Act
  const user = userEvent.setup();
  renderLinkLinePage();
  await user.click(screen.getByTestId('link-button'));

  // Assert
  await waitFor(() => {
    expect(mockLinkLine).toHaveBeenCalledWith({
      id_token: mockIdToken,
    });
  });
});
```

#### テストケース7: ID トークン取得失敗

```typescript
it('IDトークン取得失敗時にエラーが表示される', async () => {
  // Arrange
  mockGetLiffIdToken.mockResolvedValue(null);

  // Act
  const user = userEvent.setup();
  renderLinkLinePage();
  await user.click(screen.getByTestId('link-button'));

  // Assert
  await waitFor(() => {
    expect(screen.getByTestId('error-message')).toHaveTextContent(
      'LINEの認証情報を取得できませんでした'
    );
  });
});
```

---

### 4.3 統合テスト

#### シナリオ: LINE 連携 E2E フロー

1. **フロントエンド**: `liff.getIDToken()` で ID トークン取得
2. **フロントエンド**: `POST /users/link-line` に ID トークンを送信
3. **バックエンド**: LINE API を呼び出して ID トークンを検証
4. **バックエンド**: 検証結果から line_user_id を抽出
5. **バックエンド**: user_service.link_line() で DB に保存
6. **バックエンド**: User 型でレスポンス返却
7. **フロントエンド**: ユーザー情報を更新表示

**期待結果**: ID トークン検証を経由して正しく LINE 連携が完了し、User 型でレスポンスが返却される

---

## 5. 実装手順（TDD プロセス）

### Phase 1: テスト実装（Red）

1. `/tsumiki:tdd-red` を実行
2. テストファイルを作成:
   - `backend/tests/unit/test_line_service_verify.py`: verify_id_token メソッドのテスト
   - `backend/tests/api/test_link_line_idtoken.py`: ハンドラのテスト
   - `frontend/src/pages/__tests__/LinkLinePage.idtoken.test.tsx`: ID トークン送信のテスト
3. すべてのテストが失敗することを確認

### Phase 2: 最小実装（Green）

1. `/tsumiki:tdd-green` を実行
2. verify_id_token メソッドを実装
3. handler.py で ID トークン処理を実装
4. LinkLinePage.tsx でフロントエンド処理を実装
5. すべてのテストが成功することを確認

### Phase 3: リファクタリング（Refactor）

1. `/tsumiki:tdd-refactor` を実行
2. httpx への移行を完了（requests 全置換）
3. 環境変数の設定確認
4. 型定義の整理
5. エラーハンドリングの統一
6. テストカバレッジ 80% 以上を確認

---

## 6. チェックリスト

### 6.1 実装確認項目

- [ ] フロントエンドが `liff.getIDToken()` を使用している
- [ ] フロントエンドが ID トークンをリクエストボディで送信している
- [ ] `LinkLineRequest` モデルが `id_token: str` フィールドを持つ
- [ ] handler.py で `id_token` をバリデーションしている
- [ ] `line_service.verify_id_token()` メソッドが実装されている
- [ ] verify_id_token で LINE API を呼び出している
- [ ] 検証成功時に `sub` クレームから line_user_id を抽出している
- [ ] 検証失敗時に `UnauthorizedError` を発生させている
- [ ] line_service.py で `httpx` を import している
- [ ] line_service.py で `requests` を import していない
- [ ] reply_message と push_message が httpx を使用している
- [ ] requirements.txt に httpx が記載されている
- [ ] SAM テンプレートに `LineChannelId` パラメータが定義されている
- [ ] SAM テンプレートの環境変数に `LINE_CHANNEL_ID` が設定されている

### 6.2 テスト確認項目

- [ ] verify_id_token の成功テストが実装されている
- [ ] verify_id_token の失敗テスト（複数ケース）が実装されている
- [ ] handler での ID トークン未送信テストが実装されている
- [ ] httpx 使用確認テストが実装されている
- [ ] フロントエンド ID トークン送信テストが実装されている
- [ ] フロントエンド ID トークン取得失敗テストが実装されている
- [ ] テストカバレッジ 80% 以上を達成している

### 6.3 ドキュメント確認項目

- [ ] TASK-0044.md の完了条件をすべて満たしている
- [ ] overview.md を更新している
- [ ] コミットメッセージを適切に記載している
- [ ] 実装ノート（本ドキュメント）を記録している

---

## 7. 既知の制約と注意事項

### 7.1 LINE API 仕様上の制約

- **ID トークン有効期限**: 数分～数十分程度（短い）
  - テスト: Mock を使用して有効期限切れのシナリオをシミュレート
  - 本番: ネットワークレイテンシーを考慮したタイムアウト設定

- **Nonce 値の検証**: 本実装では省略
  - 推奨: LIFF で nonce を保存し、検証時に比較する
  - 後続タスク: TASK-0045 で検討

### 7.2 HTTP クライアント移行上の注意点

- **httpx vs requests**: ほぼ同じ API だが、例外が異なる
  - requests: `RequestException`
  - httpx: `httpx.RequestException`

- **タイムアウト**: 両方とも `timeout` パラメータをサポート
  - 推奨: 10秒（既存の requests コード参照）

### 7.3 セキュリティ上の注意点

- **ID トークン保存**: フロントエンド側で保持しない
  - 取得直後に送信、レスポンス受け取り後は破棄

- **Channel ID**: 公開情報だが、環境変数として安全に管理

- **Access Token/Secret**: すでに Secrets Manager で管理中

---

## 8. 参考資料

### 8.1 LINE API ドキュメント

- **ID Token Verification**: https://developers.line.biz/ja/docs/line-login/integrate-line-login/#verify-id-token
- **LIFF SDK Reference**: https://developers.line.biz/ja/docs/liff/reference/

### 8.2 プロジェクト内リソース

- **タスク定義**: `/Volumes/external/dev/memoru-liff/docs/tasks/code-review-fixes-v2/TASK-0044.md`
- **要件定義**: `/Volumes/external/dev/memoru-liff/docs/spec/code-review-fixes-v2/requirements.md`
- **API 設計**: `/Volumes/external/dev/memoru-liff/docs/design/code-review-fixes-v2/api-endpoints.md`
- **アーキテクチャ**: `/Volumes/external/dev/memoru-liff/docs/design/code-review-fixes-v2/architecture.md`

### 8.3 既存実装参照

- **LINE Service**: `/Volumes/external/dev/memoru-liff/backend/src/services/line_service.py`
- **Handler**: `/Volumes/external/dev/memoru-liff/backend/src/api/handler.py`
- **Link Line Page**: `/Volumes/external/dev/memoru-liff/frontend/src/pages/LinkLinePage.tsx`
- **API Client**: `/Volumes/external/dev/memoru-liff/frontend/src/services/api.ts`
- **テスト例**: `/Volumes/external/dev/memoru-liff/backend/tests/unit/test_line_service.py`

---

## 9. 実装後の検証チェック

### 9.1 ローカルテスト

```bash
# バックエンドテスト実行
cd /Volumes/external/dev/memoru-liff/backend
make test

# カバレッジ確認
pytest --cov=src tests/

# フロントエンドテスト実行
cd /Volumes/external/dev/memoru-liff/frontend
npm run test

# 型チェック
npm run type-check
```

### 9.2 統合テスト環境

1. ローカル SAM 環境で API 動作確認
2. Mock LINE API でテスト
3. Keycloak 認証を通すテスト流を確認
4. フロントエンド LIFF SDK との統合テスト

---

## 10. まとめ

TASK-0044 は LINE 連携のセキュリティ強化と技術スタック統一を達成する重要なタスク。

- **セキュリティ**: フロントエンド信頼依存 → サーバー側検証により強化
- **技術統一**: requests → httpx への統一で保守性向上
- **実装複雑度**: 中程度（LINE API 連携、httpx 移行）
- **リスク**: 低い（既存の requests コードとの互換性は高い）

TDD アプローチで段階的に実装し、各フェーズでテストを確認することで、品質を保ちながら実装を進めることが可能。

---

**最終更新**: 2026-02-21
**ステータス**: 準備完了（実装開始可能）
