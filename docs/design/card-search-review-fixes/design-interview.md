# card-search-review-fixes 設計ヒアリング記録

**作成日**: 2026-03-01
**ヒアリング実施**: 設計フェーズ

## ヒアリング目的

フロントエンドのみのバグ修正・テスト追加タスクのため、設計フェーズでの追加ヒアリングは不要と判断。要件定義フェーズでの決定事項をそのまま設計に反映。

## 要件定義フェーズからの引き継ぎ事項

### 確認済み設計方針
- C-1（FilterChips 非表示）: FE のみの条件レンダリングで対応
- C-2（reset メモ化）: `useCallback` でラップ
- Mi-2（normalize 共通化）: `utils/text.ts` に抽出

### 残課題
- `dueCardToCard` の `repetitions: 0` 問題の根本解決は将来課題（DueCard API 拡張が必要）

## 関連文書

- **アーキテクチャ設計**: [architecture.md](architecture.md)
- **データフロー**: [dataflow.md](dataflow.md)
- **要件定義**: [requirements.md](../../spec/card-search-review-fixes/requirements.md)
- **要件ヒアリング記録**: [interview-record.md](../../spec/card-search-review-fixes/interview-record.md)
