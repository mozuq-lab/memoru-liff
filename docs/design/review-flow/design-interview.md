# review-flow 設計ヒアリング記録

**作成日**: 2026-02-25
**ヒアリング実施**: step4 既存情報ベースの差分ヒアリング

## ヒアリング目的

既存の要件定義（review-flow/requirements.md）および既存アーキテクチャ設計（memoru-liff/architecture.md）を確認し、フロントエンド復習画面の技術設計に必要な方針を決定するためのヒアリングを実施しました。

## 質問と回答

### Q1: 復習セッションの状態管理方式

**カテゴリ**: アーキテクチャ
**背景**: 既存プロジェクトでは CardsContext（React Context）でカード状態を管理している。復習セッションの状態（現在のカードインデックス、フリップ状態、採点結果等）をどこで管理するかを確認。

**回答**: **ReviewPage ローカル状態**
- ReviewPage 内の useState で完結。他ページとの状態共有は不要。
- シンプルでテストしやすい。

**信頼性への影響**:
- フロントエンドアーキテクチャの状態管理方針が明確化 → 信頼性 🔵
- 新規 Context は不要。既存の CardsContext の dueCards/fetchDueCards はカード取得にのみ利用

---

### Q2: フリップアニメーションの実装方式

**カテゴリ**: 技術選択
**背景**: フリップアニメーションの実装方法として、CSS transform のみで実装するか、framer-motion 等のアニメーションライブラリを使用するかを確認。

**回答**: **CSS transform のみ**
- CSS perspective + rotateY で実装。ライブラリ依存なし。
- パフォーマンスが良く、バンドルサイズに影響しない。

**信頼性への影響**:
- アニメーション実装方針が明確化 → 信頼性 🔵
- 依存関係追加なし。既存の Tailwind CSS と組み合わせて実装

---

## ヒアリング結果サマリー

### 確認できた事項
- 状態管理は ReviewPage ローカル（useState）で完結
- フリップアニメーションは CSS transform のみ（ライブラリ不要）

### 設計方針の決定事項
- 新規 React Context は作成しない
- 新規 npm パッケージの追加は不要
- 既存の API クライアント（reviewsApi, cardsApi）をそのまま利用

### 残課題
- 特になし。既存実装パターンに従い設計可能

### 信頼性レベル分布

**ヒアリング前**:
- 🔵 青信号: 0件
- 🟡 黄信号: 2件（状態管理、アニメーション方式）
- 🔴 赤信号: 0件

**ヒアリング後**:
- 🔵 青信号: 2件 (+2)
- 🟡 黄信号: 0件 (-2)
- 🔴 赤信号: 0件 (0)

## 関連文書

- **アーキテクチャ設計**: [architecture.md](architecture.md)
- **データフロー**: [dataflow.md](dataflow.md)
- **型定義**: [interfaces.ts](interfaces.ts)
- **要件定義**: [requirements.md](../../spec/review-flow/requirements.md)
