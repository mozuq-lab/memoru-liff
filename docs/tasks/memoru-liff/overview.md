# memoru-liff タスク概要

**作成日**: 2026-01-05
**プロジェクト期間**: Phase 1-4（約144時間）
**推定工数**: 144時間
**総タスク数**: 22件

## 関連文書

- **要件定義書**: [📋 requirements.md](../../spec/memoru-liff/requirements.md)
- **ユーザストーリー**: [📖 user-stories.md](../../spec/memoru-liff/user-stories.md)
- **受け入れ基準**: [✅ acceptance-criteria.md](../../spec/memoru-liff/acceptance-criteria.md)
- **設計文書**: [📐 architecture.md](../../design/memoru-liff/architecture.md)
- **API仕様**: [🔌 api-endpoints.md](../../design/memoru-liff/api-endpoints.md)
- **データベース設計**: [🗄️ database-schema.md](../../design/memoru-liff/database-schema.md)
- **データフロー図**: [🔄 dataflow.md](../../design/memoru-liff/dataflow.md)
- **コンテキストノート**: [📝 note.md](../../spec/memoru-liff/note.md)

## フェーズ構成

| フェーズ | 成果物 | タスク数 | 工数 | ファイル |
|---------|--------|----------|------|----------|
| Phase 1 | 基盤インフラ構築完了 | 5件 | 28h | [TASK-0001~0005](#phase-1-基盤構築) |
| Phase 2 | バックエンドAPI実装完了 | 6件 | 48h | [TASK-0006~0011](#phase-2-バックエンド実装) |
| Phase 3 | フロントエンドUI実装完了 | 8件 | 46h | [TASK-0012~0019](#phase-3-フロントエンド実装) |
| Phase 4 | 統合テスト・デプロイ準備完了 | 3件 | 20h | [TASK-0020~0022](#phase-4-統合テスト) |

## タスク番号管理

**使用済みタスク番号**: TASK-0001 ~ TASK-0022
**次回開始番号**: TASK-0023

## 全体進捗

- [ ] Phase 1: 基盤構築 (5タスク) - IaCテンプレート作成完了、デプロイ待ち
- [x] Phase 2: バックエンド実装 (6タスク) - ✅ 完了
- [ ] Phase 3: フロントエンド実装 (8タスク)
- [ ] Phase 4: 統合テスト (3タスク)

## マイルストーン

- **M1: 基盤完成**: Keycloak、DynamoDB、API Gateway、CloudFront構築完了
- **M2: API完成**: バックエンドAPI全エンドポイント実装完了
- **M3: UI完成**: フロントエンド全画面実装完了
- **M4: リリース準備完了**: E2Eテスト・本番デプロイ準備完了

---

## Phase 1: 基盤構築

**目標**: AWS基盤インフラとKeycloak認証基盤の構築
**成果物**: ECS/Fargate上のKeycloak、DynamoDBテーブル、CloudFront+S3、API Gateway

### タスク一覧

| 状態 | タスクID | タスク名 | 工数 | タイプ | 信頼性 |
|------|----------|---------|------|--------|--------|
| [~] | [TASK-0001](TASK-0001.md) | Keycloak ECS/Fargate インフラ構築 | 8h | DIRECT | 🔵 |
| [ ] | [TASK-0002](TASK-0002.md) | Keycloak Realm/Client 設定 | 4h | DIRECT | 🔵 |
| [x] | [TASK-0003](TASK-0003.md) | DynamoDB テーブル作成 | 4h | DIRECT | 🔵 |
| [~] | [TASK-0004](TASK-0004.md) | CloudFront + S3 LIFF ホスティング構築 | 4h | DIRECT | 🔵 |
| [x] | [TASK-0005](TASK-0005.md) | API Gateway + Lambda 基盤構築 | 8h | DIRECT | 🔵 |

### 依存関係

```
TASK-0001 ──┬──► TASK-0002
            │
            └──► TASK-0005
                    ▲
TASK-0003 ──────────┘

TASK-0004 （独立）
```

### Phase 1 完了条件

- [ ] Keycloakがhttps://keycloak.example.comでアクセス可能
- [ ] DynamoDB 3テーブル（users, cards, reviews）作成完了
- [ ] CloudFrontディストリビューション作成完了
- [ ] API Gateway REST API + Lambda Authorizer動作確認

---

## Phase 2: バックエンド実装

**目標**: REST API全エンドポイントの実装
**成果物**: ユーザー管理、カード管理、復習、AI生成、LINE連携のAPI

### タスク一覧

| 状態 | タスクID | タスク名 | 工数 | タイプ | 信頼性 |
|------|----------|---------|------|--------|--------|
| [x] | [TASK-0006](TASK-0006.md) | ユーザー管理API実装 | 8h | TDD | 🔵 |
| [x] | [TASK-0007](TASK-0007.md) | カード管理API実装 | 8h | TDD | 🔵 |
| [x] | [TASK-0008](TASK-0008.md) | SM-2アルゴリズム・復習API実装 | 8h | TDD | 🔵 |
| [x] | [TASK-0009](TASK-0009.md) | AIカード生成API実装 | 8h | TDD | 🔵 |
| [x] | [TASK-0010](TASK-0010.md) | LINE Webhook・Postback処理実装 | 8h | TDD | 🔵 |
| [x] | [TASK-0011](TASK-0011.md) | 定期通知Lambda実装 | 8h | TDD | 🔵 |

### 依存関係

```
TASK-0005 ──► TASK-0006 ──► TASK-0007 ──┬──► TASK-0008 ──► TASK-0010 ──► TASK-0011
                                        │
                                        └──► TASK-0009
```

### Phase 2 完了条件

- [x] 全APIエンドポイントが動作確認完了
- [x] 単体テストカバレッジ80%以上
- [x] SM-2アルゴリズムが正確に動作
- [x] LINE Webhookが署名検証を通過

---

## Phase 3: フロントエンド実装

**目標**: LIFF React アプリケーションの実装
**成果物**: 認証連携、全画面UI、LINE連携機能

### タスク一覧

| 状態 | タスクID | タスク名 | 工数 | タイプ | 信頼性 |
|------|----------|---------|------|--------|--------|
| [x] | [TASK-0012](TASK-0012.md) | LIFF SDK + Keycloak OIDC 認証連携 | 8h | TDD | 🔵 |
| [x] | [TASK-0013](TASK-0013.md) | React アプリ基盤構築 | 4h | DIRECT | 🔵 |
| [x] | [TASK-0014](TASK-0014.md) | ホーム画面・ナビゲーション | 6h | TDD | 🟡 |
| [x] | [TASK-0015](TASK-0015.md) | AIカード生成画面 | 8h | TDD | 🔵 |
| [x] | [TASK-0016](TASK-0016.md) | カード一覧画面 | 6h | TDD | 🟡 |
| [x] | [TASK-0017](TASK-0017.md) | カード詳細・編集画面 | 6h | TDD | 🟡 |
| [x] | [TASK-0018](TASK-0018.md) | 設定画面（通知時間設定） | 4h | TDD | 🔵 |
| [ ] | [TASK-0019](TASK-0019.md) | LINE連携画面 | 4h | TDD | 🔵 |

### 依存関係

```
TASK-0002 ──┬──► TASK-0012 ──┬──► TASK-0014 ──┬──► TASK-0015
TASK-0004 ──┘               │               │
                            │               ├──► TASK-0016 ──► TASK-0017
TASK-0013 ──────────────────┘               │
                                            ├──► TASK-0018
                                            │
                                            └──► TASK-0019

（バックエンドAPI依存）
TASK-0009 ──► TASK-0015
TASK-0007 ──► TASK-0016
TASK-0006 ──► TASK-0018
TASK-0006 ──► TASK-0019
```

### Phase 3 完了条件

- [ ] LINE WebView内で全画面が正常動作
- [ ] Keycloak OIDC認証フローが完全動作
- [ ] モバイルファーストUIが実現
- [ ] 単体テストカバレッジ80%以上

---

## Phase 4: 統合テスト

**目標**: E2Eテスト実施と本番デプロイ準備
**成果物**: E2Eテストスイート、CI/CDパイプライン、本番環境設定

### タスク一覧

| 状態 | タスクID | タスク名 | 工数 | タイプ | 信頼性 |
|------|----------|---------|------|--------|--------|
| [ ] | [TASK-0020](TASK-0020.md) | E2Eテスト（認証フロー） | 8h | TDD | 🟡 |
| [ ] | [TASK-0021](TASK-0021.md) | LINE統合テスト | 8h | TDD | 🟡 |
| [ ] | [TASK-0022](TASK-0022.md) | 本番デプロイ準備 | 4h | DIRECT | 🟡 |

### 依存関係

```
TASK-0012 ──┬──► TASK-0020 ──┐
TASK-0019 ──┘               │
                            ├──► TASK-0022
TASK-0010 ──┬──► TASK-0021 ──┘
TASK-0011 ──┘
```

### Phase 4 完了条件

- [ ] E2Eテスト全件パス
- [ ] LINE統合テスト全件パス
- [ ] CI/CDパイプライン動作確認
- [ ] 本番環境デプロイ可能状態

---

## 信頼性レベルサマリー

### 全タスク統計

- **総タスク数**: 22件
- 🔵 **青信号**: 16件 (73%)
- 🟡 **黄信号**: 6件 (27%)
- 🔴 **赤信号**: 0件 (0%)

### フェーズ別信頼性

| フェーズ | 🔵 青 | 🟡 黄 | 🔴 赤 | 合計 |
|---------|-------|-------|-------|------|
| Phase 1 | 5件 | 0件 | 0件 | 5件 |
| Phase 2 | 6件 | 0件 | 0件 | 6件 |
| Phase 3 | 5件 | 3件 | 0件 | 8件 |
| Phase 4 | 0件 | 3件 | 0件 | 3件 |

**品質評価**: ✅ 高品質（青信号が70%以上）

### 黄信号タスク（要確認）

- **TASK-0014**: ホーム画面・ナビゲーション（UI詳細が要件から推測）
- **TASK-0016**: カード一覧画面（UI詳細が要件から推測）
- **TASK-0017**: カード詳細・編集画面（UI詳細が要件から推測）
- **TASK-0020**: E2Eテスト（テスト詳細がacceptance-criteriaから推測）
- **TASK-0021**: LINE統合テスト（テスト詳細がacceptance-criteriaから推測）
- **TASK-0022**: 本番デプロイ準備（一般的なベストプラクティスから推測）

---

## クリティカルパス

```
TASK-0001 → TASK-0005 → TASK-0006 → TASK-0007 → TASK-0008 → TASK-0010 → TASK-0011 → TASK-0021 → TASK-0022
```

**クリティカルパス工数**: 76時間
**並行作業可能工数**: 68時間

---

## タスクタイプ別集計

| タイプ | 件数 | 工数 | 説明 |
|--------|------|------|------|
| TDD | 16件 | 112h | テスト駆動開発でコーディング |
| DIRECT | 6件 | 32h | 環境構築・設定作業 |

---

## 次のステップ

タスクを実装するには:

```bash
# 全タスクを順番に実装
/tsumiki:kairo-implement

# 特定タスクを実装
/tsumiki:kairo-implement TASK-0001
```

### 推奨実装順序

1. **Phase 1を並行実行**:
   - TASK-0001, TASK-0003, TASK-0004 を並行
   - TASK-0002 は TASK-0001 完了後
   - TASK-0005 は TASK-0001, TASK-0003 完了後

2. **Phase 2を順次実行**:
   - TASK-0006 → TASK-0007 → TASK-0008/TASK-0009 → TASK-0010 → TASK-0011

3. **Phase 3を並行実行**:
   - TASK-0012, TASK-0013 を並行
   - TASK-0014 完了後、残りの画面を並行

4. **Phase 4を順次実行**:
   - TASK-0020, TASK-0021 を並行
   - TASK-0022 は最後
