# ローカル開発環境構築 受け入れ基準

**作成日**: 2026-02-22
**関連要件定義**: [requirements.md](requirements.md)
**関連ユーザストーリー**: [user-stories.md](user-stories.md)
**ヒアリング記録**: [interview-record.md](interview-record.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: 計画ファイル・ユーザヒアリングから確実な基準
- 🟡 **黄信号**: 実装経験・技術仕様から妥当な推測による基準
- 🔴 **赤信号**: 推測による基準

---

## Phase 1: 基盤構築（TASK-0048）

### REQ-LD-001〜003: インポートパス統一 🔵

**信頼性**: 🔵 *計画ファイルより*

#### Given（前提条件）
- バックエンドソースコードが `backend/src/` に配置されている
- SAM テンプレートの CodeUri が `src/` に設定されている

#### When（実行条件）
- `make test` でテストを実行する
- `make build` で SAM ビルドを実行する

#### Then（期待結果）
- 全 251 テストが pass する
- SAM ビルドが成功する
- Lambda 関数が正常にインポートを解決する

#### テストケース

##### 正常系

- [ ] **TC-LD-001-01**: 全バックエンドテスト pass 🔵
  - **入力**: `pytest tests/ -x -q`
  - **期待結果**: 251 tests passed
  - **信頼性**: 🔵 *計画ファイルより*

- [ ] **TC-LD-001-02**: SAM ビルド成功 🔵
  - **入力**: `sam build`
  - **期待結果**: Build Succeeded
  - **信頼性**: 🔵 *計画ファイルより*

---

### REQ-LD-011〜012: SAM Local ルーティング修正 🔵

**信頼性**: 🔵 *計画ファイルより*

#### Given（前提条件）
- SAM local が stage="dev" でイベントを送信する
- rawPath にステージプレフィックスが含まれない

#### When（実行条件）
- SAM local API にリクエストを送信する

#### Then（期待結果）
- ハンドラーが rawPath に `/{stage}` を前置する
- Powertools の path 解決が正しいパスを返す
- 対応するルートハンドラーが呼び出される

#### テストケース

##### 正常系

- [ ] **TC-LD-011-01**: `/users/me` エンドポイントが 404 にならない 🔵
  - **入力**: `GET http://localhost:8080/users/me`
  - **期待結果**: ルーティングが成功し、ハンドラーが呼び出される（認証エラー or 正常レスポンス）
  - **信頼性**: 🔵 *計画ファイルより*

- [ ] **TC-LD-011-02**: `/cards` エンドポイントが正常にルーティングされる 🔵
  - **入力**: `GET http://localhost:8080/cards`
  - **期待結果**: ルーティング成功
  - **信頼性**: 🔵 *計画ファイルより*

##### 異常系

- [ ] **TC-LD-011-E01**: 本番環境（stage="$default"）では前置処理がスキップされる 🔵
  - **入力**: stage="$default", rawPath="/users/me"
  - **期待結果**: rawPath が変更されない
  - **信頼性**: 🔵 *計画ファイルの条件分岐設計より*

---

### REQ-LD-021〜022: DynamoDB 接続設定 🔵

**信頼性**: 🔵 *計画ファイルより*

#### Given（前提条件）
- `env.json` に `DYNAMODB_ENDPOINT_URL` が設定されている
- `template.yaml` の Globals に `DYNAMODB_ENDPOINT_URL` が定義されている

#### When（実行条件）
- SAM local Lambda がサービスクラスを初期化する

#### Then（期待結果）
- `DYNAMODB_ENDPOINT_URL` の値が boto3 の endpoint_url として使用される
- `DYNAMODB_ENDPOINT_URL` が空の場合はデフォルト AWS エンドポイントに接続する

#### テストケース

##### 正常系

- [ ] **TC-LD-021-01**: DYNAMODB_ENDPOINT_URL が設定されている場合、指定エンドポイントに接続 🔵
  - **入力**: `DYNAMODB_ENDPOINT_URL=http://dynamodb-local:8000`
  - **期待結果**: boto3.resource に endpoint_url が渡される
  - **信頼性**: 🔵 *計画ファイルより*

- [ ] **TC-LD-021-02**: DYNAMODB_ENDPOINT_URL が空で AWS_ENDPOINT_URL が設定されている場合、フォールバック 🔵
  - **入力**: `DYNAMODB_ENDPOINT_URL=""`, `AWS_ENDPOINT_URL=http://dynamodb-local:8000`
  - **期待結果**: AWS_ENDPOINT_URL の値が使用される
  - **信頼性**: 🔵 *計画ファイルのフォールバック設計より*

##### 境界値

- [ ] **TC-LD-021-B01**: 両方とも空の場合、デフォルト AWS エンドポイントに接続 🔵
  - **入力**: `DYNAMODB_ENDPOINT_URL=""`, `AWS_ENDPOINT_URL=""`
  - **期待結果**: boto3 デフォルト（AWS 本番エンドポイント）
  - **信頼性**: 🔵 *計画ファイルより。空文字は falsy のため条件分岐をスキップ*

---

### REQ-LD-031〜034: Keycloak Docker セットアップ 🔵

**信頼性**: 🔵 *計画ファイル・realm-local.json 設計より*

#### テストケース

##### 正常系

- [ ] **TC-LD-031-01**: Keycloak がポート 8180 で起動する 🔵
  - **入力**: `make local-keycloak`
  - **期待結果**: `http://localhost:8180/health/ready` が 200 を返す
  - **信頼性**: 🔵 *計画ファイルより*

- [ ] **TC-LD-031-02**: テストユーザーでログインできる 🔵
  - **入力**: test-user / test-password-123
  - **期待結果**: Keycloak がアクセストークンを発行する
  - **信頼性**: 🔵 *計画ファイルより*

- [ ] **TC-LD-031-03**: LINE IdP が含まれない 🔵
  - **入力**: realm-local.json の内容確認
  - **期待結果**: identityProviders セクションが空
  - **信頼性**: 🔵 *計画ファイルの realm-local.json 設計より*

---

## Phase 2: 残タスク

### REQ-LD-061〜064: Backend JWT フォールバック 🔵

**信頼性**: 🔵 *計画ファイル・ユーザヒアリングより*

#### Given（前提条件）
- `ENVIRONMENT=dev` が設定されている
- API Gateway authorizer context が利用できない（SAM local 環境）
- リクエストに `Authorization: Bearer {jwt}` ヘッダーが含まれている

#### When（実行条件）
- 認証付きエンドポイント（`/users/me`, `/cards` 等）にリクエストが到達する

#### Then（期待結果）
- JWT ペイロードの `sub` クレームがユーザー ID として使用される
- 正しいユーザーのデータが返却される

#### テストケース

##### 正常系

- [ ] **TC-LD-061-01**: 正規の Keycloak トークンからユーザー ID を抽出 🔵
  - **入力**: Keycloak が発行した有効な JWT（`Authorization: Bearer eyJ...`）
  - **期待結果**: `sub` クレームの値がユーザー ID として使用される
  - **信頼性**: 🔵 *計画ファイル・Keycloak の標準 JWT 仕様*

- [ ] **TC-LD-061-02**: API Gateway authorizer context がある場合はフォールバック不使用 🔵
  - **入力**: authorizer context に `sub` が含まれるイベント
  - **期待結果**: authorizer context の `sub` が優先される
  - **信頼性**: 🔵 *REQ-LD-101 制約。本番互換性*

##### 異常系

- [ ] **TC-LD-061-E01**: Authorization ヘッダーがない場合 🟡
  - **入力**: Authorization ヘッダーなしのリクエスト
  - **期待結果**: 401 Unauthorized
  - **信頼性**: 🟡 *セキュリティのベストプラクティスから推測*

- [ ] **TC-LD-061-E02**: JWT が不正な形式（ドットが 2 個ない）の場合 🟡
  - **入力**: `Authorization: Bearer invalid-token`
  - **期待結果**: 401 Unauthorized（安全に失敗）
  - **信頼性**: 🟡 *EDGE-LD-003 エッジケース*

- [ ] **TC-LD-061-E03**: JWT ペイロードの base64 デコードに失敗した場合 🟡
  - **入力**: `Authorization: Bearer eyJ.!!!invalid!!!.sig`
  - **期待結果**: 401 Unauthorized（安全に失敗）
  - **信頼性**: 🟡 *EDGE-LD-003 エッジケース*

##### 境界値

- [ ] **TC-LD-061-B01**: ENVIRONMENT が "dev" 以外（"staging", "prod"）の場合 🔵
  - **入力**: `ENVIRONMENT=prod`、Authorization ヘッダーあり
  - **期待結果**: JWT フォールバックは無効。authorizer context のみ使用
  - **信頼性**: 🔵 *REQ-LD-063 制約*

- [ ] **TC-LD-061-B02**: Bearer プレフィックスがない場合 🟡
  - **入力**: `Authorization: eyJ...`（Bearer なし）
  - **期待結果**: JWT フォールバックがスキップされる
  - **信頼性**: 🟡 *EDGE-LD-102 エッジケース*

---

### REQ-LD-071〜073: DynamoDB Local 接続問題解決 🔵

**信頼性**: 🔵 *ユーザヒアリングより*

#### Given（前提条件）
- DynamoDB local が Docker で起動している（ポート 8000）
- テーブルが作成済み

#### When（実行条件）
- boto3 経由で DynamoDB local にリクエストを送信する

#### Then（期待結果）
- リクエストがハングせず、正常にレスポンスが返る
- CRUD 操作が正常に動作する

#### テストケース

##### 正常系

- [ ] **TC-LD-071-01**: ホストマシンから DynamoDB local にテーブル一覧を取得 🔵
  - **入力**: `aws dynamodb list-tables --endpoint-url http://localhost:8000`
  - **期待結果**: 3 テーブル（memoru-users-dev, memoru-cards-dev, memoru-reviews-dev）
  - **信頼性**: 🔵 *基本的な接続確認*

- [ ] **TC-LD-071-02**: boto3 から DynamoDB local にデータを読み書き 🔵
  - **入力**: Python スクリプトで put_item / get_item
  - **期待結果**: タイムアウトなしで正常完了
  - **信頼性**: 🔵 *SigV4 問題の解決確認*

- [ ] **TC-LD-071-03**: SAM local Lambda から DynamoDB local にアクセス 🔵
  - **入力**: `GET /users/me`（JWT フォールバック有効）
  - **期待結果**: ユーザーデータが返却される（または新規作成される）
  - **信頼性**: 🔵 *Docker ネットワーク経由の接続確認*

##### 異常系

- [ ] **TC-LD-071-E01**: DynamoDB local 未起動時のエラーハンドリング 🟡
  - **入力**: DynamoDB local を停止した状態で API にアクセス
  - **期待結果**: 接続エラーが適切にハンドリングされる（500 エラー）
  - **信頼性**: 🟡 *エラーハンドリングの一般的なパターン*

---

## 非機能要件テスト

### NFR-LD-001: 起動性能 🟡

**信頼性**: 🟡 *Keycloak 24.0 の起動時間から推測*

- [ ] **TC-NFR-LD-001-01**: 全サービス起動時間
  - **測定項目**: `make local-all` の実行時間
  - **目標値**: 120 秒以内
  - **測定条件**: 初回起動（Docker イメージ pull 済み）
  - **信頼性**: 🟡 *Keycloak healthcheck の start_period: 60s から推測*

### NFR-LD-101: セキュリティ 🔵

**信頼性**: 🔵 *API Gateway アーキテクチャより*

- [ ] **TC-NFR-LD-101-01**: JWT フォールバックの本番非適用
  - **検証内容**: `ENVIRONMENT=prod` で JWT フォールバックが無効であること
  - **期待結果**: authorizer context のみで認証される
  - **信頼性**: 🔵 *REQ-LD-063 制約の検証*

---

## Edge ケーステスト

### EDGE-LD-001: Keycloak 未起動 🟡

**信頼性**: 🟡 *計画ファイルより*

- [ ] **TC-EDGE-LD-001-01**: Keycloak 未起動時のフロントエンド表示
  - **条件**: Keycloak がポート 8180 で未起動
  - **期待結果**: 接続エラーが表示される（クラッシュしない）
  - **信頼性**: 🟡 *計画ファイルより*

### EDGE-LD-002: DynamoDB local 未起動 🟡

**信頼性**: 🟡 *計画ファイルより*

- [ ] **TC-EDGE-LD-002-01**: DynamoDB 未起動時のフロントエンド表示
  - **条件**: DynamoDB local がポート 8000 で未起動（または SigV4 ハング）
  - **期待結果**: 各画面でエラーメッセージと再試行ボタンが表示される
  - **信頼性**: 🟡 *計画ファイルより*

### EDGE-LD-101: ルートパスのルーティング 🟡

**信頼性**: 🟡 *計画ファイルから推測*

- [ ] **TC-EDGE-LD-101-01**: rawPath が "/" のみの場合
  - **条件**: stage="dev", rawPath="/"
  - **期待結果**: rawPath が "/dev/" に変換され、ルーティングが正常動作
  - **信頼性**: 🟡 *計画ファイルの前置ロジック設計から推測*

---

## テストケースサマリー

### カテゴリ別件数

| カテゴリ | 正常系 | 異常系 | 境界値 | 合計 |
|---------|--------|--------|--------|------|
| Phase 1（実装済み） | 8 | 1 | 1 | 10 |
| Phase 2（JWT フォールバック） | 2 | 3 | 2 | 7 |
| Phase 2（DynamoDB 問題） | 3 | 1 | 0 | 4 |
| 非機能要件 | 1 | 0 | 0 | 1 |
| Edge ケース | 0 | 0 | 0 | 3 |
| **合計** | **14** | **5** | **3** | **25** |

### 信頼性レベル分布

- 🔵 青信号: 17件 (68%)
- 🟡 黄信号: 8件 (32%)
- 🔴 赤信号: 0件 (0%)

**品質評価**: ✅ 高品質（赤信号なし）

### 優先度別テストケース

- **Must Have**: 25件（全テストケース）
- **Should Have**: 0件
- **Could Have**: 0件

### 実施状況

- **❌ 未実施**: 25件（全テストケース）

---

## テスト実施計画

### Phase 1: 基本機能テスト
- TC-LD-001-01 〜 TC-LD-031-03
- 優先度: Must Have
- 実施予定: TASK-0048 実装時

### Phase 2: 残タスクテスト
- TC-LD-061-01 〜 TC-LD-071-E01
- 優先度: Must Have
- 実施予定: 次回タスク実装時

### Phase 3: 非機能・Edge ケーステスト
- TC-NFR-LD-001-01 〜 TC-EDGE-LD-101-01
- 優先度: Must Have
- 実施予定: Phase 2 完了後
