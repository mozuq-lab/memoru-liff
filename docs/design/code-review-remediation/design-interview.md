# code-review-remediation 設計ヒアリング記録

**作成日**: 2026-02-15
**ヒアリング実施**: step4 既存情報ベースの差分ヒアリング

## ヒアリング目的

コードレビュー修正の技術設計にあたり、実装パターンの選択肢がある箇所について設計方針を確定するためのヒアリングを実施しました。

## 質問と回答

### Q1: 既存実装の詳細分析の必要性

**質問日時**: 2026-02-15
**カテゴリ**: コード分析
**背景**: コードレビューで既に全ソースコードを分析済みのため、追加のコード分析が必要かを確認。

**回答**: 不要（コードレビュー結果と設計文書のみで設計を作成）

**信頼性への影響**:
- 追加分析なしでも、コードレビュー結果に具体的なファイルパスと行番号が記載されているため、設計の信頼性に影響なし

---

### Q2: トークンリフレッシュの実装パターン

**質問日時**: 2026-02-15
**カテゴリ**: 技術選択
**背景**: H-08（Token リフレッシュ機能の欠如）の修正にあたり、API クライアント interceptor パターンと oidc-client-ts の automaticSilentRenew 機能のどちらを採用するかの選択が必要。LIFF WebView での Silent Renew の動作は未検証のリスクがあった。

**回答**: API クライアント interceptor パターン

**信頼性への影響**:
- REQ-CR-007, REQ-CR-102, REQ-CR-103 の設計が 🟡 → 🟡 のまま（実装パターンは確定したが、LIFF WebView での具体的な動作は実装時に検証が必要）
- EDGE-CR-003（並行リフレッシュ防止）の設計が具体化（`isRefreshing` フラグパターン）

---

### Q3: カード数制限 Race Condition の対策方式

**質問日時**: 2026-02-15
**カテゴリ**: データモデル
**背景**: H-06（カード数制限の Race Condition）の修正にあたり、DynamoDB の ConditionExpression と Atomic Counter パターンのどちらを採用するかの選択が必要。既存の TransactWriteItems への組み込み容易性を考慮。

**回答**: ConditionExpression 方式

**信頼性への影響**:
- REQ-CR-015 の設計が 🟡 → 🔵 に向上（DynamoDB のネイティブ機能で確実に実現可能）
- EDGE-CR-101（並行カード作成）のテスト戦略が明確化

---

### Q4: CSP 強化の方針

**質問日時**: 2026-02-15
**カテゴリ**: セキュリティ
**背景**: H-02（CSP の unsafe-inline/unsafe-eval 許可）の修正にあたり、LIFF SDK が inline script を使用するため `unsafe-inline` の完全除去が難しい可能性があった。

**回答**: unsafe-eval のみ除去（unsafe-inline は LIFF SDK 互換性のため維持）

**信頼性への影響**:
- REQ-CR-010 の設計が 🔵 に確定（安全に実施可能な範囲が明確化）
- LIFF SDK 互換性リスクが軽減（`unsafe-inline` を維持するため）

---

## ヒアリング結果サマリー

### 確認できた事項

- コードレビュー結果の情報量で追加コード分析は不要
- トークンリフレッシュは API クライアント interceptor パターン
- Race Condition 対策は DynamoDB ConditionExpression
- CSP 強化は unsafe-eval のみ除去

### 設計方針の決定事項

1. **API クライアント interceptor**: `isRefreshing` フラグ + `Promise` 共有で並行リクエストのリフレッシュを 1 回に制限
2. **ConditionExpression**: 既存 TransactWriteItems に `card_count < 2000` 条件を追加
3. **CSP**: `unsafe-eval` 除去、`unsafe-inline` 維持。Vite ビルドの互換性は実装時に検証

### 残課題

- LIFF WebView での `silentRenew()` の動作検証（実装時）
- Vite ビルド出力が `unsafe-eval` なしで動作するかの確認（実装時）
- ConditionExpression 失敗時のユーザーフレンドリーなエラーメッセージ設計

### 信頼性レベル分布

**ヒアリング前**:

- 🔵 青信号: 30件
- 🟡 黄信号: 8件
- 🔴 赤信号: 0件

**ヒアリング後**:

- 🔵 青信号: 35件 (+5)
- 🟡 黄信号: 5件 (-3)
- 🔴 赤信号: 0件 (±0)

## 関連文書

- **アーキテクチャ設計**: [architecture.md](architecture.md)
- **データフロー**: [dataflow.md](dataflow.md)
- **API 仕様**: [api-endpoints.md](api-endpoints.md)
- **要件定義**: [requirements.md](../../spec/code-review-remediation/requirements.md)
