# review-reconfirm 設計ヒアリング記録

**作成日**: 2026-02-28
**ヒアリング実施**: step4 既存情報ベースの差分ヒアリング

## ヒアリング目的

既存の復習フロー実装（ReviewPage.tsx）を分析した上で、再確認ループ機能の状態管理アプローチを確定するためのヒアリングを実施しました。

## 事前分析結果

以下の既存実装を分析済み:
- `frontend/src/pages/ReviewPage.tsx` - 復習セッション状態管理
- `frontend/src/components/GradeButtons.tsx` - 評価ボタンUI
- `frontend/src/components/ReviewComplete.tsx` - 完了画面
- `frontend/src/components/ReviewResultItem.tsx` - 結果表示
- `frontend/src/types/card.ts` - 型定義
- `docs/design/review-flow/architecture.md` - 既存設計文書
- `docs/design/review-undo/architecture.md` - Undo設計文書

## 質問と回答

### Q1: ReviewPageの状態管理アプローチ

**カテゴリ**: アーキテクチャ
**背景**: ReviewPage.txは現在useStateフラットパターンで10個以上のstate変数を管理している。再確認キュー（reconfirmQueue, isReconfirmMode）の追加でさらに状態が増えるため、リファクタリングの必要性を確認した。

**回答**: useState維持（推奨）を選択

**信頼性への影響**:
- この回答により、状態管理設計の信頼性レベルが 🟡 → 🔵 に向上
- useReducerやカスタムフックへのリファクタリングは不要と確定
- 既存パターンとの一貫性を維持する方針が確定

---

## ヒアリング結果サマリー

### 確認できた事項
- 状態管理はuseStateフラットパターンを維持する
- 再確認キュー状態は2-3個のuseState追加で対応する
- 既存のリファクタリングは実施しない（最小変更方針）

### 設計方針の決定事項
- useState追加: `reconfirmQueue`, `isReconfirmMode`
- GradeButtonsにモードフラグを追加して条件分岐
- 新規コンポーネント: ReconfirmBadge（シンプルなバッジ表示のみ）

### 残課題
- なし（フロントエンドのみの変更で設計完結）

### 信頼性レベル分布

**ヒアリング前**:
- 🔵 青信号: 13件
- 🟡 黄信号: 4件
- 🔴 赤信号: 0件

**ヒアリング後**:
- 🔵 青信号: 14件 (+1)
- 🟡 黄信号: 3件 (-1)
- 🔴 赤信号: 0件

## 関連文書

- **アーキテクチャ設計**: [architecture.md](architecture.md)
- **データフロー**: [dataflow.md](dataflow.md)
- **要件定義**: [requirements.md](../../spec/review-reconfirm/requirements.md)
