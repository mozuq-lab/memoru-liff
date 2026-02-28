# review-undo 設計ヒアリング記録

**作成日**: 2026-02-28
**ヒアリング実施**: step4 既存情報ベースの差分ヒアリング

## ヒアリング目的

既存の復習機能（review-flow）の設計・実装を確認し、復習取り消し機能のAPI設計とUI遷移方式を確定するためのヒアリングを実施しました。

## 質問と回答

### Q1: Undo APIエンドポイントパス

**質問日時**: 2026-02-28
**カテゴリ**: API設計
**背景**: 既存の `POST /reviews/{cardId}` に合わせたパス設計が適切か、またはRESTfulなセマンティクス（DELETE）を採用すべきか確認が必要。

**回答**: `POST /reviews/{cardId}/undo`（推奨）

**信頼性への影響**:
- この回答により、REQ-009（Undo APIエンドポイント）の信頼性レベルが 🟡 → 🔵 に向上
- 既存のPOSTベースのAPIパターンと統一された設計が確定

---

### Q2: 完了画面からカード復習画面への遷移方式

**質問日時**: 2026-02-28
**カテゴリ**: アーキテクチャ
**背景**: 取り消し後の再採点UIへの遷移方式として、同一ページ内での状態切替と別ルートへの遷移の2つの選択肢があった。ReviewPageは既にuseStateで複数の表示状態を管理しているため、状態切替が自然な拡張となるが、ルート分離の方が独立性が高い。

**回答**: 同一ページ内で状態切替（推奨）

**信頼性への影響**:
- この回答により、フロントエンドのアーキテクチャ設計の信頼性が 🟡 → 🔵 に向上
- ReviewPage内のisComplete/regradeCardIndex stateによる状態管理方式が確定
- 新規ルート追加が不要となり、実装がシンプルに

---

## ヒアリング結果サマリー

### 確認できた事項
- Undo APIは `POST /reviews/{cardId}/undo` で実装
- 再採点UI遷移は ReviewPage 内の状態切替で実現
- 新規ルート追加は不要

### 設計方針の決定事項
- APIパスは既存の `POST /reviews/{cardId}` パターンに合わせてネスト
- フロントエンドは既存のReviewPage stateモデルを拡張（regradeCardIndex追加）
- ReviewCompleteコンポーネントのpropsを大幅変更（reviewedCount → results配列）

### 残課題
- review_historyエントリへのrepetitions_before/next_review_at_before追加の後方互換性確認（実装時に対応）
- 再採点時のプログレスバー表示の詳細（1枚のみの再採点なのでプログレス非表示が適切か）

### 信頼性レベル分布

**ヒアリング前**:
- 🔵 青信号: 40件
- 🟡 黄信号: 15件
- 🔴 赤信号: 0件

**ヒアリング後**:
- 🔵 青信号: 44件 (+4)
- 🟡 黄信号: 11件 (-4)
- 🔴 赤信号: 0件

## 関連文書

- **アーキテクチャ設計**: [architecture.md](architecture.md)
- **データフロー**: [dataflow.md](dataflow.md)
- **型定義**: [interfaces.ts](interfaces.ts)
- **API仕様**: [api-endpoints.md](api-endpoints.md)
- **要件定義**: [requirements.md](../../spec/review-undo/requirements.md)
