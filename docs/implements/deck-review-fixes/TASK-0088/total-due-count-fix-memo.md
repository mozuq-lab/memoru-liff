# total_due_count 修正 TDD開発完了記録

## 確認すべきドキュメント

- `docs/tasks/deck-review-fixes/TASK-0088.md`
- `docs/implements/deck-review-fixes/TASK-0088/total-due-count-fix-requirements.md`
- `docs/implements/deck-review-fixes/TASK-0088/total-due-count-fix-testcases.md`

## 最終結果 (2026-03-01)

- **実装率**: 100% (12/12 テストケース)
- **テスト成功率**: 100% (49/49 review_service テスト全通過)
- **品質判定**: 合格
- **TODO更新**: 完了マーク追加済み

## 重要な技術学習

### 実装パターン

- **バグ1修正**: `card_service.get_due_cards()` の `limit` パラメータを `Optional[int] = None` に変更し、DynamoDB Query レベルの切り詰めを防ぐ
- **バグ2修正**: `total_due_count = len(all_due_cards)` を `all_due_cards[:limit]` スライス前に計算する
- **全件取得後 limit 適用**パターン: deck_id フィルタが必要な場合は全件取得→フィルタ→カウント→limit 適用の順序が正しい
- **limit=None サポート**: `Optional[int] = None` + DynamoDB クエリで `Limit` キーを渡さないことで全件取得を実現

### テスト設計

- `TestGetDueCardsTotalDueCountFix` クラスに TASK-0088 専用テスト12件を集約
- `_put_due_card()` ヘルパー関数で DynamoDB 投入を共通化
- TC-011 が最重要: card_service レベルの limit 切り詰めバグ（バグ1）を deck_id との組み合わせで検証
- moto `mock_aws` でインメモリ DynamoDB を使用（実 AWS 不要）

### 品質保証

- Refactor フェーズでは機能変更なし、コメント・docstring のみ改善
- `【設計方針】` セクションを docstring に追加し "なぜそうするか" を記述
- `get_due_card_count()` は notification_service で引き続き使用（削除対象外）
- MVP 段階の全件取得によるパフォーマンス影響: 最大2000件・許容範囲内

## 注意事項（後工程向け）

### TASK-0088 スコープ外の既存テスト失敗（別タスクで対応予定）

以下のテスト失敗は TASK-0088 の修正内容とは無関係。デッキ管理機能追加（TASK-0084 以降）により template.yaml・env.json が更新されたことに起因する古いテスト。

| テストファイル | テスト名 | 失敗内容 |
|---|---|---|
| `tests/unit/test_handler_ai_service_factory.py` | `test_template_yaml_global_timeout_is_60` | template.yaml の Timeout=120 だが期待値60 |
| `tests/unit/test_handler_ai_service_factory.py` | `test_env_json_existing_functions_have_new_vars` | env.json の USE_STRANDS='true' だが期待値'false' |
| `tests/unit/test_handler_ai_service_factory.py` | `test_env_json_new_functions_defined` | 同上 |
| `tests/test_template_routes.py` | `test_total_http_api_event_count` | イベント数18だが期待値13 |
| `tests/test_template_routes.py` | `test_no_duplicate_event_names` | 同上 |
| `tests/integration/test_integration.py` | `test_existing_test_suite_passes` | 上記失敗の連鎖 |
| `tests/unit/test_migration_compat.py` | `test_existing_test_suite_passes` | 同上 |

- **失敗件数**: 7件（TASK-0088 とは無関係）
- **修正方針**: 別タスク（template.yaml 設定・env.json・ルート数テスト更新）で対応
- **TASK-0088 対象テスト**: 49/49 全通過（影響なし）

### テスト実行速度

- **全体テスト実行時間**: 48.25秒（30秒以上）
- review_service 単体: 3.38秒（問題なし）
- 全テストスイートは統合テスト含むため時間がかかる

---

*Red → Green → Refactor → Verify 完了。TDD サイクル完全終了。*
