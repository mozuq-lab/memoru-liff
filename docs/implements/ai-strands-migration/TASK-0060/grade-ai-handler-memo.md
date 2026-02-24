# TDD開発メモ: grade-ai-handler

## 概要

- 機能名: grade-ai-handler
- 開発開始: 2026-02-24
- 現在のフェーズ: Red（完了）

## 関連ファイル

- 元タスクファイル: `docs/tasks/ai-strands-migration/TASK-0060.md`
- 要件定義: `docs/implements/ai-strands-migration/TASK-0060/requirements.md`
- テストケース定義: `docs/implements/ai-strands-migration/TASK-0060/testcases.md`
- 実装ファイル: `backend/src/api/handler.py`（`grade_ai_handler` 関数）
- テストファイル: `backend/tests/unit/test_handler_grade_ai.py`

## Redフェーズ（失敗するテスト作成）

### 作成日時

2026-02-24

### テストケース概要

全 35 テストケースを実装。テストケースはすべて 🔵 青信号（既存ドキュメントに基づく）。

| カテゴリ | 件数 |
|---------|------|
| 認証テスト（TestGradeAiHandlerAuth） | 3 |
| パスパラメータテスト（TestGradeAiHandlerPathParams） | 2 |
| バリデーションテスト（TestGradeAiHandlerValidation） | 6 |
| カード関連テスト（TestGradeAiHandlerCardErrors） | 3 |
| AI 呼び出しテスト（TestGradeAiHandlerAICall） | 4 |
| 正常系レスポンステスト（TestGradeAiHandlerSuccess） | 7 |
| AI エラーテスト（TestGradeAiHandlerAIErrors） | 7 |
| ロギングテスト（TestGradeAiHandlerLogging） | 3 |
| **合計** | **35** |

### テスト実行結果

```
35 failed in 0.60s
```

全 35 件が FAIL（期待通りの Red フェーズ）。

### 期待される失敗の理由

現在の `grade_ai_handler` はスタブ実装で、すべてのリクエストに対して以下を返す:

```python
return {
    "statusCode": 501,
    "headers": {"Content-Type": "application/json"},
    "body": json.dumps({"error": "Not implemented"}),
}
```

このため:
- 認証チェックがなく → 401 が期待されるテストで 501 が返る
- バリデーションがなく → 400 が期待されるテストで 501 が返る
- カード取得がなく → 404 が期待されるテストで 501 が返る
- AI 採点がなく → 200 が期待されるテストで 501 が返る
- エラーハンドリングがなく → 504/429/503/500 が期待されるテストで 501 が返る
- ロギングがなく → logger の呼び出しが確認できない

### 次のフェーズへの要求事項

Green フェーズで実装すべき内容:

1. `_get_user_id_from_event(event)` ヘルパー（複数 JWT パスをサポート）
2. `grade_ai_handler` の本実装:
   - `event.requestContext.authorizer.jwt.claims.sub` から user_id 抽出
   - `event.pathParameters.cardId` から card_id 取得（camelCase）
   - `event.body` の JSON パース + `GradeAnswerRequest` Pydantic バリデーション
   - `card_service.get_card(user_id, card_id)` でカード取得
   - `event.queryStringParameters.language` からの language 取得（デフォルト "ja"）
   - `create_ai_service().grade_answer()` で AI 採点
   - `GradeAnswerResponse` 形式でのレスポンス返却
   - 全エラーの適切な HTTP マッピング
   - 適切なロギング（リクエスト受信時・成功時・AI エラー時・予期しない例外時）
3. 既存テスト `test_grade_ai_handler_returns_501`（TC-056-014）の削除または条件付きスキップ

## Greenフェーズ（最小実装）

### 実装日時

（未実施）

## Refactorフェーズ（品質改善）

### リファクタ日時

（未実施）
