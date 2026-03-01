# deck-review-fixes 設計ヒアリング記録

**作成日**: 2026-03-01
**ヒアリング実施**: step4 既存情報ベースの差分ヒアリング

## ヒアリング目的

要件定義書・レビュー文書・既存実装を分析した結果、以下の設計判断について確認が必要だった：
1. handler.py の分割方式（アーキテクチャ変更の影響範囲が大きいため）
2. H-4（レースコンディション）の具体的な DynamoDB 実装パターン

## 質問と回答

### Q1: handler.py の分割方式

**質問日時**: 2026-03-01
**カテゴリ**: アーキテクチャ
**背景**: REQ-401（handler.py ドメイン別分割）の実装方式として、Lambda Powertools の Router 機能を活用する方法と、handler.py をそのまま分割する方法がある。Router 方式は handler.py をルーターとして維持しつつ、各ドメインハンドラを別ファイルに分割できる。一方、完全分割はディレクトリ構造が大きく変わる。

**選択肢**:
- ルーター分割: handler.py はルーターとして維持し、ドメインハンドラを `handlers/` 配下に分割。Lambda Powertools の `include_router()` を使用
- 完全分割: handler.py を廃止し、ドメインごとに独立したハンドラファイルを作成

**回答**: ルーター分割（推奨）

**信頼性への影響**:
- REQ-401 の実装方針が確定（信頼性レベル: 🔵）
- handler.py の Lambda エントリポイントを維持しつつ、ドメインハンドラを分離
- 既存テストへの影響を最小化

---

### Q2: H-4（レースコンディション）の DynamoDB 実装パターン

**質問日時**: 2026-03-01
**カテゴリ**: 技術制約
**背景**: DynamoDB ではテーブル内のアイテム数に基づく ConditionExpression を直接記述できない。H-4 の修正では、デッキ数制限（50）のアトミック検証が必要。以下の 2 つのアプローチが考えられる：

1. **Query+Condition**: Query(Select=COUNT) でデッキ数を取得 → PutItem with `attribute_not_exists` で重複防止 → 作成後に再カウントでレース検出
2. **TransactWriteItems**: カウンターテーブルを使用し、TransactWriteItems でアトミックにインクリメント + 条件チェック

**選択肢**:
- Query+Condition: 既存テーブル構造を維持。楽観的チェック + PutItem + 作成後検証。完全なアトミック性はないがレース窓を最小化
- TransactWriteItems: カウンターテーブル追加が必要。完全なアトミック性を保証するが、テーブル追加のオーバーヘッドあり

**回答**: Query+Condition（推奨）

**信頼性への影響**:
- REQ-004 の実装方針が確定（信頼性レベル: 🔵）
- 既存テーブル構造を変更せずに実装可能
- MVP 段階では十分な堅牢性（レース窓は非常に小さい）

---

## ヒアリング結果サマリー

### 確認できた事項
- handler.py の分割方式: ルーター分割（Lambda Powertools Router 活用）
- H-4 の DynamoDB 実装: Query+Condition パターン（カウンターテーブル不要）
- 既存テーブル構造・Lambda エントリポイントの変更は不要

### 設計方針の決定事項
- `backend/src/api/handlers/` ディレクトリを新設し、5 つのドメインハンドラに分割
- `backend/src/api/shared.py` に共通関数を切り出し
- デッキ作成時は 楽観的チェック → PutItem → 作成後検証 の 3 段階で制限を実施

### 残課題
- なし（全設計判断について方針決定済み）

### 信頼性レベル分布

**ヒアリング前**:
- 🔵 青信号: 16件
- 🟡 黄信号: 4件
- 🔴 赤信号: 0件

**ヒアリング後**:
- 🔵 青信号: 18件 (+2)
- 🟡 黄信号: 2件 (-2)
- 🔴 赤信号: 0件 (±0)

## 関連文書

- **アーキテクチャ設計**: [architecture.md](architecture.md)
- **データフロー**: [dataflow.md](dataflow.md)
- **要件定義**: [requirements.md](../../spec/deck-review-fixes/requirements.md)
- **要件ヒアリング記録**: [interview-record.md](../../spec/deck-review-fixes/interview-record.md)
