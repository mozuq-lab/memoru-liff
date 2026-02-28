# interval-adjust 設計ヒアリング記録

**作成日**: 2026-02-28
**ヒアリング実施**: step4 既存情報ベースの差分ヒアリング

## ヒアリング目的

要件定義フェーズで主要な設計方針が確定済みのため、軽量設計として追加ヒアリングは実施せず、既存の合意事項に基づいて設計文書を作成しました。

## 要件定義フェーズでの確定事項（設計への入力）

以下は要件定義フェーズのヒアリング（[interview-record.md](../../spec/interval-adjust/interview-record.md)）で確定した設計方針です：

| 項目 | 決定事項 | 信頼性 |
|------|---------|--------|
| UI配置 | CardDetailPageのメタ情報セクション | 🔵 |
| 操作方法 | プリセットボタン（1, 3, 7, 14, 30日） | 🔵 |
| API方式 | 既存 PUT /cards/:id を拡張 | 🔵 |
| SM-2パラメータ | intervalのみ変更、ease_factor/repetitions不変 | 🔵 |
| バリデーション | 1日〜365日 | 🔵 |
| review_history | 記録しない（復習操作ではない） | 🟡 |

## ヒアリング結果サマリー

### 確認できた事項
- 全項目が要件定義フェーズで確定済み

### 設計方針の決定事項
- 既存コンポーネントの拡張のみで実現（新規エンドポイント・テーブル不要）
- フロントエンドの状態管理は既存のパターン（error/successMessage）を再利用

### 残課題
- なし

### 信頼性レベル分布

**設計文書全体**:
- 🔵 青信号: 14件 (88%)
- 🟡 黄信号: 2件 (12%)
- 🔴 赤信号: 0件 (0%)

## 関連文書

- **アーキテクチャ設計**: [architecture.md](architecture.md)
- **データフロー**: [dataflow.md](dataflow.md)
- **要件定義**: [requirements.md](../../spec/interval-adjust/requirements.md)
- **要件ヒアリング記録**: [interview-record.md](../../spec/interval-adjust/interview-record.md)
