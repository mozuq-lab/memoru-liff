# 001-card-speech バグ修正 設計ヒアリング記録

**作成日**: 2026-03-05
**ヒアリング実施**: step4 既存情報ベースの差分ヒアリング

## ヒアリング目的

レビュー指摘事項の修正設計にあたり、技術的方針の確認を行いました。

## 質問と回答

### Q1: 設計規模の確認

**カテゴリ**: アーキテクチャ
**背景**: バグ修正5件の設計規模を確認。全件がフロントエンドのみの変更であり、DB・API・インフラ変更なし

**回答**: 軽量設計を選択

**信頼性への影響**:

- 全設計項目の信頼性が既存文書（spec.md, contracts/）で裏付けられており、追加ヒアリング不要と判断

---

## ヒアリング結果サマリー

### 確認できた事項

- 修正はフロントエンドのみ（hooks, components, pages）
- `useSpeech` hook のインターフェースは変更不要
- `FlipCardSpeechProps` インターフェースも変更不要
- 停止トグルの修正は ReviewPage のコールバック定義のみで対応可能

### 設計方針の決定事項

- REQ-001: ReviewPage の `onSpeakFront`/`onSpeakBack` で `isSpeaking` 判定を追加
- REQ-002: `useSpeechSettings` に `useEffect([userId])` を追加
- REQ-101: `aria-label="自動読み上げ"` を追加
- REQ-102: `setItem` を `try/catch` で保護
- REQ-103: 統合テストを既存テストファイルに追加

### 残課題

- なし（全修正の設計が確定）

### 信頼性レベル分布

**ヒアリング前**:

- 🔵 青信号: 12件
- 🟡 黄信号: 2件
- 🔴 赤信号: 0件

**ヒアリング後**:

- 🔵 青信号: 12件 (±0)
- 🟡 黄信号: 2件 (±0)
- 🔴 赤信号: 0件 (±0)

## 関連文書

- **アーキテクチャ設計**: [architecture.md](architecture.md)
- **データフロー**: [dataflow.md](dataflow.md)
- **要件定義**: [requirements.md](../../spec/001-card-speech-bugfix/requirements.md)
