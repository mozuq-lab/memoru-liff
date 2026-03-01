# TASK-0090 設定作業実行

## 作業概要

- **タスクID**: TASK-0090
- **作業内容**: `deck_service.py` の `get_deck_card_counts` / `get_deck_due_counts` メソッドに TODO コメント追加
- **実行日時**: 2026-03-01
- **実行者**: Claude Code

## 設計文書参照

- **参照文書**: `docs/tasks/deck-review-fixes/TASK-0090.md`
- **関連要件**: REQ-404

## 実行した作業

### 1. TODO コメント追加

**変更ファイル**: `backend/src/services/deck_service.py`

#### `get_deck_card_counts` メソッド（line 359-360）

```python
# TODO: パフォーマンス改善 - 全カードスキャンを GSI カウントまたは
# DynamoDB Streams + カウンターテーブルに置き換える（MVP後対応）
```

コメントを `if not deck_ids: return {}` の直後、`counts` 辞書初期化の前に追加した。

#### `get_deck_due_counts` メソッド（line 405-406）

```python
# TODO: パフォーマンス改善 - 全カードスキャンを GSI カウントまたは
# DynamoDB Streams + カウンターテーブルに置き換える（MVP後対応）
```

同一パターンで `if not deck_ids: return {}` の直後に追加した。

## 作業結果

- [x] `get_deck_card_counts` に TODO コメント追加
- [x] `get_deck_due_counts` に TODO コメント追加
- [x] コメントに改善案（GSI カウント / DynamoDB Streams + カウンターテーブル）を記載

## 次のステップ

- `/tsumiki:direct-verify` を実行して変更を確認
