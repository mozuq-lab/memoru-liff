# interval-adjust TDD開発完了記録

## 確認すべきドキュメント

- `docs/tasks/interval-adjust/TASK-0078.md`
- `docs/implements/interval-adjust/TASK-0078/interval-update-requirements.md`
- `docs/implements/interval-adjust/TASK-0078/interval-adjust-testcases.md`

## 🎯 最終結果 (2026-02-28)
- **実装率**: 129% (22実装/17予定テストケース)
- **テスト成功率**: 100% (22/22全通過)
- **品質判定**: ✅ 高品質（合格）
- **TODO更新**: ✅ 完了マーク追加

## 💡 重要な技術学習

### 実装パターン

- **DynamoDB 予約語エスケープ**: `interval` は予約語のため `ExpressionAttributeNames={"#interval": "interval"}` が必須。`update_review_data` の既存パターンを参照
- **update_parts パターン**: `update_parts` リストに UPDATE 式のパーツを追加し、`SET ` で結合。interval と front/back を同一 UpdateExpression でまとめて更新可能
- **next_review_at の計算**: `datetime.now(timezone.utc) + timedelta(days=interval)` → `.isoformat()` で ISO 8601 形式（UTC）保存
- **ease_factor は string 型**: DynamoDB に `str(float)` 形式で保存。interval 更新時に変更しない

### テスト設計

- **モデル層とサービス層を分離**: `test_card_model_interval.py`（Pydantic バリデーション 11件）と `test_card_service_interval.py`（サービスロジック 11件）に分割
- **datetime モック**: `unittest.mock.patch` で `datetime.now` を固定日時に差し替えて next_review_at の正確な値を検証
- **moto + `@mock_aws`**: DynamoDB テーブルを `dynamodb_table` fixture で作成。`update_card` は通常の `table.update_item()` を使用するため `transact_write_items` のカスタムモックは不要
- **不変性の検証**: ease_factor（string 型 "2.8"）と repetitions（int 型）が interval 更新後も変化しないことを明示的に assert

### 品質保証

- **後方互換性**: interval 未指定時（None）に interval/next_review_at を一切変更しないことを TC-N05 で検証
- **review_history 非記録**: reviews テーブル scan で 0 件であることを TC-N07 で明示的に検証
- **リファクタ適用**: ローカルインポートをファイル先頭へ移動、description 追加、docstring 整理の 3 件を適用

## ⚠️ 注意点・修正が必要な項目

なし。全 22 テストが Refactorフェーズ後もグリーン状態を維持している。

---
*Red → Green → Refactor 全フェーズ完了。22テスト全通過（0.97s）*
