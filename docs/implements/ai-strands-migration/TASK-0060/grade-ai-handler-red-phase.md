# TDD Red フェーズ記録: grade-ai-handler

## 概要

- 機能名: grade-ai-handler
- タスクID: TASK-0060
- 要件名: ai-strands-migration
- フェーズ: Red（失敗テスト作成完了）
- 作成日時: 2026-02-24

## 作成したテストケース一覧（全 35 件）

| テストクラス | TC ID | テスト名 | 信頼性 |
|------------|-------|---------|--------|
| TestGradeAiHandlerAuth | TC-060-AUTH-001 | test_grade_ai_returns_401_when_no_authorizer | 🔵 |
| TestGradeAiHandlerAuth | TC-060-AUTH-002 | test_grade_ai_returns_401_when_no_sub_claim | 🔵 |
| TestGradeAiHandlerAuth | TC-060-AUTH-003 | test_grade_ai_extracts_user_id_from_jwt_claims | 🔵 |
| TestGradeAiHandlerPathParams | TC-060-PATH-001 | test_grade_ai_extracts_card_id_from_path_params | 🔵 |
| TestGradeAiHandlerPathParams | TC-060-PATH-002 | test_grade_ai_returns_400_when_card_id_missing | 🔵 |
| TestGradeAiHandlerValidation | TC-060-VAL-001 | test_grade_ai_returns_400_when_body_is_null | 🔵 |
| TestGradeAiHandlerValidation | TC-060-VAL-002 | test_grade_ai_returns_400_when_body_is_invalid_json | 🔵 |
| TestGradeAiHandlerValidation | TC-060-VAL-003 | test_grade_ai_returns_400_when_user_answer_empty | 🔵 |
| TestGradeAiHandlerValidation | TC-060-VAL-004 | test_grade_ai_returns_400_when_user_answer_whitespace_only | 🔵 |
| TestGradeAiHandlerValidation | TC-060-VAL-005 | test_grade_ai_returns_400_when_user_answer_too_long | 🔵 |
| TestGradeAiHandlerValidation | TC-060-VAL-006 | test_grade_ai_returns_400_when_user_answer_missing | 🔵 |
| TestGradeAiHandlerCardErrors | TC-060-CARD-001 | test_grade_ai_returns_404_when_card_not_found | 🔵 |
| TestGradeAiHandlerCardErrors | TC-060-CARD-002 | test_grade_ai_passes_card_front_back_to_ai_service | 🔵 |
| TestGradeAiHandlerCardErrors | TC-060-CARD-003 | test_grade_ai_returns_404_for_other_users_card | 🔵 |
| TestGradeAiHandlerAICall | TC-060-AI-001 | test_grade_ai_calls_create_ai_service_factory | 🔵 |
| TestGradeAiHandlerAICall | TC-060-AI-002 | test_grade_ai_passes_correct_args_to_grade_answer | 🔵 |
| TestGradeAiHandlerAICall | TC-060-AI-003 | test_grade_ai_passes_language_param_to_grade_answer | 🔵 |
| TestGradeAiHandlerAICall | TC-060-AI-004 | test_grade_ai_uses_default_language_ja | 🔵 |
| TestGradeAiHandlerSuccess | TC-060-RES-001 | test_grade_ai_success_returns_200 | 🔵 |
| TestGradeAiHandlerSuccess | TC-060-RES-002 | test_grade_ai_success_response_contains_grade | 🔵 |
| TestGradeAiHandlerSuccess | TC-060-RES-003 | test_grade_ai_success_response_contains_reasoning | 🔵 |
| TestGradeAiHandlerSuccess | TC-060-RES-004 | test_grade_ai_success_response_contains_card_front_back | 🔵 |
| TestGradeAiHandlerSuccess | TC-060-RES-005 | test_grade_ai_success_response_contains_grading_info | 🔵 |
| TestGradeAiHandlerSuccess | TC-060-RES-006 | test_grade_ai_success_response_is_json | 🔵 |
| TestGradeAiHandlerSuccess | TC-060-RES-007 | test_grade_ai_success_full_e2e_flow | 🔵 |
| TestGradeAiHandlerAIErrors | TC-060-ERR-001 | test_grade_ai_returns_504_on_ai_timeout | 🔵 |
| TestGradeAiHandlerAIErrors | TC-060-ERR-002 | test_grade_ai_returns_429_on_ai_rate_limit | 🔵 |
| TestGradeAiHandlerAIErrors | TC-060-ERR-003 | test_grade_ai_returns_503_on_ai_provider_error | 🔵 |
| TestGradeAiHandlerAIErrors | TC-060-ERR-004 | test_grade_ai_returns_500_on_ai_parse_error | 🔵 |
| TestGradeAiHandlerAIErrors | TC-060-ERR-005 | test_grade_ai_returns_500_on_ai_internal_error | 🔵 |
| TestGradeAiHandlerAIErrors | TC-060-ERR-006 | test_grade_ai_returns_503_on_factory_init_failure | 🔵 |
| TestGradeAiHandlerAIErrors | TC-060-ERR-007 | test_grade_ai_returns_500_on_unexpected_exception | 🔵 |
| TestGradeAiHandlerLogging | TC-060-LOG-001 | test_grade_ai_logs_request_info | 🔵 |
| TestGradeAiHandlerLogging | TC-060-LOG-002 | test_grade_ai_logs_success_info | 🔵 |
| TestGradeAiHandlerLogging | TC-060-LOG-003 | test_grade_ai_logs_ai_error | 🔵 |

**信頼性サマリー**: 🔵 35件 (100%) / 🟡 0件 / 🔴 0件

## テストファイル

`backend/tests/unit/test_handler_grade_ai.py`

## テスト実行結果（Red フェーズ確認）

```
35 failed in 0.60s
```

全 35 件が FAIL（期待通り）。

### 主な失敗メッセージ

- AUTH テスト: `assert 501 == 401` / `assert 501 == 400` （スタブが 501 を返すため）
- PATH テスト: `assert 501 == 400` （pathParameters=None でも 501 を返す）
- VALIDATION テスト: `assert 501 == 400` （body バリデーションなし）
- CARD テスト: `assert 501 == 404` （CardService が呼ばれないため）
- AI テスト: `create_ai_service() が呼ばれない` （スタブは即 501 を返す）
- SUCCESS テスト: `assert 501 == 200` （スタブが 501 を返す）
- ERROR テスト: `assert 501 == 504/429/503/500` （エラーハンドリングなし）
- LOG テスト: `logger.info が呼ばれない` / `logger.warning/error が呼ばれない`

## Green フェーズで実装すべき内容

### 1. grade_ai_handler の本実装（backend/src/api/handler.py）

```python
def grade_ai_handler(event: dict, context: Any) -> dict:
    """POST /reviews/{cardId}/grade-ai の Lambda ハンドラー。"""
    # Step 1: JWT claims から user_id 抽出
    user_id = _get_user_id_from_event(event)
    if not user_id:
        return {"statusCode": 401, "headers": {...}, "body": json.dumps({"error": "Unauthorized"})}

    # Step 2: pathParameters.cardId から card_id 取得（camelCase）
    card_id = (event.get("pathParameters") or {}).get("cardId")
    if not card_id:
        return {"statusCode": 400, "headers": {...}, "body": json.dumps({"error": "..."})}

    # Step 3: リクエストボディの JSON パース + GradeAnswerRequest バリデーション
    try:
        body_str = event.get("body")
        body_dict = json.loads(body_str)
        request_data = GradeAnswerRequest(**body_dict)
    except (json.JSONDecodeError, TypeError, ValidationError) as e:
        return {"statusCode": 400, ...}

    # Step 4: CardService.get_card(user_id, card_id)
    try:
        card = card_service.get_card(user_id, card_id)
    except CardNotFoundError:
        return {"statusCode": 404, ..., "body": json.dumps({"error": "Not Found"})}

    # Step 5: queryStringParameters から language 取得（デフォルト "ja"）
    query_params = event.get("queryStringParameters") or {}
    language = query_params.get("language", "ja")

    # Step 6: create_ai_service().grade_answer() で AI 採点
    try:
        ai_service = create_ai_service()
        grading_result = ai_service.grade_answer(
            card_front=card.front,
            card_back=card.back,
            user_answer=request_data.user_answer,
            language=language,
        )
    except AIServiceError as e:
        response = _map_ai_error_to_http(e)
        return {"statusCode": response.status_code, "headers": {...}, "body": response.body}
    except Exception as e:
        logger.exception(...)
        return {"statusCode": 500, ..., "body": json.dumps({"error": "Internal Server Error"})}

    # Step 7: GradeAnswerResponse 構築と返却
    response_data = GradeAnswerResponse(
        grade=grading_result.grade,
        reasoning=grading_result.reasoning,
        card_front=card.front,
        card_back=card.back,
        grading_info={
            "model_used": grading_result.model_used,
            "processing_time_ms": grading_result.processing_time_ms,
        },
    )
    return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps(response_data.model_dump())}
```

### 2. _get_user_id_from_event() ヘルパー追加

JWT claims から user_id を抽出するヘルパー関数（複数パスをサポート）。

### 3. ロギング追加

- リクエスト受信時: `logger.info` で card_id, user_id, user_answer_length
- 採点成功時: `logger.info` で grade, model_used, processing_time_ms
- AI エラー時: `logger.warning` または `logger.error`
- 予期しない例外: `logger.exception`

### 4. 既存テストの更新（Green フェーズ完了後）

`backend/tests/unit/test_handler_ai_service_factory.py` の `TestStubHandlers.test_grade_ai_handler_returns_501`（TC-056-014）は削除または条件付きスキップに変更する。
