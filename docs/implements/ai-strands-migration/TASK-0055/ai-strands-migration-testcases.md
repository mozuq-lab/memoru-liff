# TDD テストケース定義: TASK-0055 BedrockAIService Protocol 準拠改修

**機能名**: ai-strands-migration
**タスクID**: TASK-0055
**要件名**: BedrockAIService Protocol 準拠改修
**出力ファイル名**: `docs/implements/ai-strands-migration/TASK-0055/ai-strands-migration-testcases.md`
**作成日**: 2026-02-23

---

## 開発言語・フレームワーク

- **プログラミング言語**: Python 3.12
  - **言語選択の理由**: プロジェクト全体が Python バックエンドで統一されており、既存テストも Python で記述済み
  - **テストに適した機能**: dataclass、Protocol（structural subtyping）、多重継承、Literal 型
- **テストフレームワーク**: pytest + unittest.mock (MagicMock)
  - **フレームワーク選択の理由**: 既存テスト (`test_bedrock.py`) が pytest + MagicMock で記述されている
  - **テスト実行環境**: `cd backend && make test` もしくは `pytest backend/tests/unit/test_bedrock.py -v`
- **重要な注意事項**:
  - 全メソッドは**同期**（`def`、`async def` ではない）— `pytest.mark.asyncio` は不要
  - 既存テストは 24 テストケース（`test_bedrock.py` のクラス 6 個）
  - Bedrock クライアントのモックは `BedrockService(bedrock_client=mock_client)` で注入
- 🔵 既存テスト `backend/tests/unit/test_bedrock.py` と `backend/src/services/ai_service.py` の実際のコードから確定

---

## 要件定義との対応関係

- **参照した機能概要**: 要件定義書 1 節 - BedrockService を AIService Protocol に完全準拠改修
- **参照した入力・出力仕様**: 要件定義書 2 節 - generate_cards() / grade_answer() / get_learning_advice() のシグネチャと戻り値型
- **参照した制約条件**: 要件定義書 3 節 - 同期メソッド、既存互換性、例外階層統合、JSON パース、パフォーマンス
- **参照した使用例**: 要件定義書 4 節 - 正常系・エラー系・エッジケースの具体的シナリオ
- **参照した実装ファイル**:
  - `backend/src/services/ai_service.py` - AIService Protocol 定義、共通型、例外階層
  - `backend/src/services/bedrock.py` - 既存 BedrockService 実装（332行）
  - `backend/src/services/prompts/grading.py` - `get_grading_prompt()`、`GRADING_SYSTEM_PROMPT`
  - `backend/src/services/prompts/advice.py` - `get_advice_prompt()`、`ADVICE_SYSTEM_PROMPT`
  - `backend/tests/unit/test_bedrock.py` - 既存テスト 24 ケース

---

## テストケース実装時の日本語コメント指針

各テストケースの実装時には以下の日本語コメントを必ず含める:

```python
# 【テスト目的】: このテストで何を確認するかを日本語で明記
# 【テスト内容】: 具体的にどのような処理をテストするかを説明
# 【期待される動作】: 正常に動作した場合の結果を説明

# Given
# 【テストデータ準備】: なぜこのデータを用意するかの理由
# 【前提条件確認】: テスト実行に必要な前提条件

# When
# 【実際の処理実行】: どの機能/メソッドを呼び出すかを説明

# Then
# 【結果検証】: 何を検証するかを具体的に説明
# 【検証項目】: この検証で確認している具体的な項目
```

---

## 1. 正常系テストケース

### 1.1 Protocol 準拠テスト

#### TC-055-001: BedrockService が AIService Protocol を実装していることの確認

- **テスト名**: BedrockService の AIService Protocol 準拠確認
  - **何をテストするか**: `isinstance(BedrockService(...), AIService)` が True を返すこと
  - **期待される動作**: `@runtime_checkable` Protocol により、Protocol の全メソッドを持つインスタンスが isinstance チェックを通過する
- **入力値**: `BedrockService(bedrock_client=mock_client)` インスタンス
  - **入力データの意味**: モッククライアントを注入した実際のサービスインスタンス
- **期待される結果**: `isinstance(service, AIService)` が `True`
  - **期待結果の理由**: `AIService` は `@runtime_checkable` Protocol であり、BedrockService が `generate_cards()`、`grade_answer()`、`get_learning_advice()` の全3メソッドを持てば `True` を返す
- **テストの目的**: Protocol 準拠の確認（構造的部分型付けの検証）
  - **確認ポイント**: `hasattr` ではなく `isinstance` で Protocol チェックを行うこと
- 🔵 `ai_service.py` の `@runtime_checkable class AIService(Protocol)` 定義から確定

```python
def test_bedrock_service_implements_ai_service_protocol():
    # 【テスト目的】: BedrockService が AIService Protocol を満たすことを確認
    # 【テスト内容】: runtime_checkable Protocol の isinstance チェック
    # 【期待される動作】: 3メソッドを実装していれば True を返す
    # 🔵

    # Given
    # 【テストデータ準備】: モッククライアントでサービスインスタンス作成
    mock_client = MagicMock()
    service = BedrockService(bedrock_client=mock_client)

    # Then
    # 【結果検証】: Protocol 準拠チェック
    # 【検証項目】: isinstance で Protocol 適合を確認
    assert isinstance(service, AIService)  # 【確認内容】: AIService Protocol を満たすこと
```

#### TC-055-002: BedrockService が全 Protocol メソッドを持つことの確認

- **テスト名**: Protocol 定義メソッドの存在確認
  - **何をテストするか**: `generate_cards`、`grade_answer`、`get_learning_advice` メソッドが存在し callable であること
  - **期待される動作**: 全3メソッドが callable 属性として存在する
- **入力値**: `BedrockService(bedrock_client=mock_client)` インスタンス
  - **入力データの意味**: 実際のサービスインスタンスのメソッド有無を確認
- **期待される結果**: 全メソッドが存在し callable
  - **期待結果の理由**: Protocol 定義の3メソッドが全て実装されている必要がある
- **テストの目的**: Protocol 完全準拠の追加検証
  - **確認ポイント**: hasattr + callable で個別メソッドの存在を確認
- 🔵 `ai_service.py` の AIService Protocol 定義（3メソッド）から確定

```python
def test_bedrock_service_has_all_protocol_methods():
    # 【テスト目的】: Protocol で定義された全メソッドが存在することを確認
    # 【テスト内容】: hasattr + callable で各メソッドを検証
    # 🔵

    # Given
    mock_client = MagicMock()
    service = BedrockService(bedrock_client=mock_client)

    # Then
    assert hasattr(service, 'generate_cards') and callable(service.generate_cards)
    assert hasattr(service, 'grade_answer') and callable(service.grade_answer)
    assert hasattr(service, 'get_learning_advice') and callable(service.get_learning_advice)
```

---

### 1.2 grade_answer() 正常系テスト

#### TC-055-003: grade_answer() が正解回答で高グレードの GradingResult を返す

- **テスト名**: 正解回答の採点（高グレード）
  - **何をテストするか**: 完全一致する回答に対して `GradingResult` が返り、grade が 0-5 範囲内であること
  - **期待される動作**: プロンプト生成 → Bedrock API 呼び出し → JSON パース → GradingResult 構築
- **入力値**:
  - `card_front="日本の首都は？"`, `card_back="東京"`, `user_answer="東京"`, `language="ja"`
  - モック Bedrock レスポンス: `{"grade": 5, "reasoning": "完全一致です。", "feedback": "素晴らしいです。"}`
  - **入力データの意味**: 完全に正しい回答を採点するケース
- **期待される結果**:
  - `result.grade == 5`
  - `result.reasoning == "完全一致です。"`
  - `result.model_used` がモデルID文字列
  - `result.processing_time_ms >= 0`
  - **期待結果の理由**: Bedrock レスポンスの grade/reasoning がそのまま GradingResult に格納される
- **テストの目的**: grade_answer() の基本動作（正解ケース）の確認
  - **確認ポイント**: GradingResult の全4フィールドが正しく設定されること、`feedback` フィールドは GradingResult に含まれないこと
- 🔵 要件定義書 4.1 節の使用例、`ai_service.py` の GradingResult dataclass から確定

```python
def test_grade_answer_correct_answer_japanese():
    # 【テスト目的】: 日本語の正解回答が高グレードで採点されることを確認
    # 【テスト内容】: card_front/card_back/user_answer を日本語で指定し、grade=5 のレスポンスを検証
    # 【期待される動作】: GradingResult(grade=5, reasoning="完全一致です。", ...) が返る
    # 🔵

    # Given
    # 【テストデータ準備】: 正解と一致するユーザー回答を用意
    mock_client = MagicMock()
    service = BedrockService(bedrock_client=mock_client)

    grading_response = {
        "grade": 5,
        "reasoning": "完全一致です。",
        "feedback": "素晴らしいです。"
    }
    mock_response_body = MagicMock()
    mock_response_body.read.return_value = json.dumps({
        "content": [{"text": json.dumps(grading_response)}]
    }).encode()
    mock_client.invoke_model.return_value = {"body": mock_response_body}

    # When
    # 【実際の処理実行】: grade_answer() を日本語パラメータで呼び出し
    result = service.grade_answer(
        card_front="日本の首都は？",
        card_back="東京",
        user_answer="東京",
        language="ja",
    )

    # Then
    # 【結果検証】: GradingResult の全フィールドを検証
    assert isinstance(result, GradingResult)
    assert result.grade == 5                      # 【検証項目】: グレードが5であること
    assert result.reasoning == "完全一致です。"      # 【検証項目】: 推論理由が設定されること
    assert isinstance(result.model_used, str)      # 【検証項目】: モデルIDが文字列であること
    assert result.processing_time_ms >= 0          # 【検証項目】: 処理時間が非負であること
    mock_client.invoke_model.assert_called_once()  # 【検証項目】: API が1回呼ばれること
```

#### TC-055-004: grade_answer() が不正解回答で低グレードの GradingResult を返す

- **テスト名**: 不正解回答の採点（低グレード）
  - **何をテストするか**: 完全に誤った回答に対して低い grade が返ること
  - **期待される動作**: AI が grade=0 を判定し、GradingResult に格納
- **入力値**:
  - `card_front="What is Python?"`, `card_back="A programming language"`, `user_answer="A type of snake"`, `language="en"`
  - モック Bedrock レスポンス: `{"grade": 0, "reasoning": "Completely incorrect.", "feedback": "..."}`
  - **入力データの意味**: 全く関係のない回答で、grade=0 (Complete blackout) が想定されるケース
- **期待される結果**: `result.grade == 0`, `result.reasoning` が非空文字列
  - **期待結果の理由**: SM-2 スケールで完全不正解は grade=0
- **テストの目的**: 低グレード採点の動作確認
  - **確認ポイント**: grade=0 が正しく GradingResult に格納される
- 🔵 要件定義書 4.1 節、SM-2 グレード定義（`prompts/grading.py` の `SM2_GRADE_DEFINITIONS`）から確定

```python
def test_grade_answer_wrong_answer_english():
    # 【テスト目的】: 誤った回答が低グレードで採点されることを確認
    # 【テスト内容】: 全く関係ない回答に対して grade=0 のレスポンスを検証
    # 🔵

    # Given
    mock_client = MagicMock()
    service = BedrockService(bedrock_client=mock_client)

    grading_response = {
        "grade": 0,
        "reasoning": "Completely incorrect. The answer is unrelated.",
        "feedback": "Review the concept of programming languages."
    }
    mock_response_body = MagicMock()
    mock_response_body.read.return_value = json.dumps({
        "content": [{"text": json.dumps(grading_response)}]
    }).encode()
    mock_client.invoke_model.return_value = {"body": mock_response_body}

    # When
    result = service.grade_answer(
        card_front="What is Python?",
        card_back="A programming language",
        user_answer="A type of snake",
        language="en",
    )

    # Then
    assert isinstance(result, GradingResult)
    assert result.grade == 0
    assert len(result.reasoning) > 0
```

#### TC-055-005: grade_answer() が部分正解で中間グレードの GradingResult を返す

- **テスト名**: 部分正解の採点（中間グレード）
  - **何をテストするか**: 部分的に正しい回答に対して中間 grade (2-3) が返ること
  - **期待される動作**: AI が grade=3（正解だが困難あり）を判定
- **入力値**:
  - `card_front="光合成とは？"`, `card_back="植物が光エネルギーを使って二酸化炭素と水から有機物を合成する反応"`, `user_answer="植物が光で何かを作る反応"`, `language="ja"`
  - モック Bedrock レスポンス: `{"grade": 3, "reasoning": "概念は理解しているが詳細が不足", "feedback": "..."}`
  - **入力データの意味**: 方向性は正しいが不完全な回答
- **期待される結果**: `result.grade == 3`, `0 <= result.grade <= 5`
  - **期待結果の理由**: SM-2 grade=3 は「正解だが重大な困難あり」
- **テストの目的**: 中間グレード採点の動作確認
- 🟡 要件定義書 4.1 節から妥当な推測（部分正解の具体的 grade 値は AI 依存だが、テストではモックで固定）

```python
def test_grade_answer_partial_answer():
    # 【テスト目的】: 部分的に正しい回答が中間グレードで採点されることを確認
    # 🟡

    # Given
    mock_client = MagicMock()
    service = BedrockService(bedrock_client=mock_client)

    grading_response = {
        "grade": 3,
        "reasoning": "概念は理解しているが詳細が不足しています。",
        "feedback": "もう少し具体的に回答してみましょう。"
    }
    mock_response_body = MagicMock()
    mock_response_body.read.return_value = json.dumps({
        "content": [{"text": json.dumps(grading_response)}]
    }).encode()
    mock_client.invoke_model.return_value = {"body": mock_response_body}

    # When
    result = service.grade_answer(
        card_front="光合成とは？",
        card_back="植物が光エネルギーを使って二酸化炭素と水から有機物を合成する反応",
        user_answer="植物が光で何かを作る反応",
        language="ja",
    )

    # Then
    assert isinstance(result, GradingResult)
    assert result.grade == 3
    assert 0 <= result.grade <= 5
```

#### TC-055-006: grade_answer() が英語で動作すること

- **テスト名**: 英語での採点動作確認
  - **何をテストするか**: `language="en"` パラメータでの採点が正常動作すること
  - **期待される動作**: 英語のプロンプトが生成され、英語の reasoning が返る
- **入力値**: 英語のカード情報と `language="en"`
  - **入力データの意味**: 英語ユーザー向けの採点シナリオ
- **期待される結果**: GradingResult が正常に返り、`invoke_model` が呼ばれること
  - **期待結果の理由**: `get_grading_prompt()` が language パラメータを使用して言語指示を埋め込む
- **テストの目的**: 多言語対応の確認
  - **確認ポイント**: language パラメータが正しくプロンプトに伝播される
- 🔵 `prompts/grading.py` の `get_grading_prompt()` が language パラメータを受け付けることから確定

```python
def test_grade_answer_english_language():
    # 【テスト目的】: 英語での採点が正常に動作することを確認
    # 🔵

    # Given
    mock_client = MagicMock()
    service = BedrockService(bedrock_client=mock_client)

    grading_response = {
        "grade": 4,
        "reasoning": "Correct with minor hesitation.",
        "feedback": "Good job!"
    }
    mock_response_body = MagicMock()
    mock_response_body.read.return_value = json.dumps({
        "content": [{"text": json.dumps(grading_response)}]
    }).encode()
    mock_client.invoke_model.return_value = {"body": mock_response_body}

    # When
    result = service.grade_answer(
        card_front="What is the capital of France?",
        card_back="Paris",
        user_answer="Paris",
        language="en",
    )

    # Then
    assert isinstance(result, GradingResult)
    assert result.grade == 4
    assert result.reasoning == "Correct with minor hesitation."
    mock_client.invoke_model.assert_called_once()
```

#### TC-055-007: grade_answer() が _invoke_with_retry() を使用してリトライ付きで呼び出すこと

- **テスト名**: grade_answer() のリトライ機構使用確認
  - **何をテストするか**: grade_answer() が既存の `_invoke_with_retry()` を内部で使用していること
  - **期待される動作**: リトライ可能なエラー（RateLimit）時にリトライされる
- **入力値**: 1回目 ThrottlingException、2回目成功のモック
  - **入力データの意味**: リトライにより回復するシナリオ
- **期待される結果**: `invoke_model` が 2 回呼ばれ、最終的に成功する
  - **期待結果の理由**: `_invoke_with_retry()` は RateLimit で最大 2 回リトライする（MAX_RETRIES=2）
- **テストの目的**: 新規メソッドが既存リトライ基盤を再利用していることの確認
  - **確認ポイント**: call_count が 2 であること（1回失敗 + 1回成功）
- 🔵 要件定義書 3.4 節「新規メソッドは既存の `_invoke_with_retry()` パターンを再利用」から確定

```python
def test_grade_answer_uses_retry_logic():
    # 【テスト目的】: grade_answer() がリトライ機構を使用することを確認
    # 🔵

    # Given
    mock_client = MagicMock()
    service = BedrockService(bedrock_client=mock_client)

    grading_response = {"grade": 4, "reasoning": "Good.", "feedback": "OK."}
    mock_response_body = MagicMock()
    mock_response_body.read.return_value = json.dumps({
        "content": [{"text": json.dumps(grading_response)}]
    }).encode()

    mock_client.invoke_model.side_effect = [
        ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate limit"}},
            "InvokeModel",
        ),
        {"body": mock_response_body},
    ]

    # When
    result = service.grade_answer(
        card_front="Q", card_back="A", user_answer="A",
    )

    # Then
    assert isinstance(result, GradingResult)
    assert mock_client.invoke_model.call_count == 2  # 【検証項目】: リトライで2回呼ばれること
```

---

### 1.3 get_learning_advice() 正常系テスト

#### TC-055-008: get_learning_advice() が dict 入力で LearningAdvice を返す

- **テスト名**: dict 形式の review_summary での学習アドバイス生成
  - **何をテストするか**: Protocol 定義通り `review_summary: dict` を渡して LearningAdvice が返ること
  - **期待される動作**: プロンプト生成 → Bedrock API 呼び出し → JSON パース → LearningAdvice 構築
- **入力値**:
  - `review_summary={"total_reviews": 100, "average_grade": 3.2, "total_cards": 50, "cards_due_today": 10, "streak_days": 5, "tag_performance": {"生物学": 3.8, "有機化学": 2.1}}`
  - `language="ja"`
  - モック Bedrock レスポンス: `{"advice_text": "...", "weak_areas": ["有機化学"], "recommendations": ["..."]}`
  - **入力データの意味**: 典型的な学習統計データ（弱点分野あり）
- **期待される結果**:
  - `result.advice_text` が非空文字列
  - `result.weak_areas == ["有機化学"]`
  - `result.recommendations` がリスト
  - `result.model_used` が文字列
  - `result.processing_time_ms >= 0`
  - **期待結果の理由**: Bedrock レスポンスの JSON フィールドが LearningAdvice に格納される
- **テストの目的**: get_learning_advice() の基本動作確認
  - **確認ポイント**: LearningAdvice の全5フィールドが正しく設定されること
- 🔵 要件定義書 4.2 節の使用例、`ai_service.py` の LearningAdvice dataclass から確定

```python
def test_get_learning_advice_with_dict_input():
    # 【テスト目的】: dict 形式の入力で学習アドバイスが正常に生成されることを確認
    # 【テスト内容】: 典型的な復習統計データを渡し、LearningAdvice の全フィールドを検証
    # 🔵

    # Given
    mock_client = MagicMock()
    service = BedrockService(bedrock_client=mock_client)

    advice_response = {
        "advice_text": "有機化学の復習を重点的に行いましょう。",
        "weak_areas": ["有機化学"],
        "recommendations": ["有機化学のカードを毎日5枚復習する", "間隔を短くして反復回数を増やす"]
    }
    mock_response_body = MagicMock()
    mock_response_body.read.return_value = json.dumps({
        "content": [{"text": json.dumps(advice_response)}]
    }).encode()
    mock_client.invoke_model.return_value = {"body": mock_response_body}

    review_summary = {
        "total_reviews": 100,
        "average_grade": 3.2,
        "total_cards": 50,
        "cards_due_today": 10,
        "streak_days": 5,
        "tag_performance": {"生物学": 3.8, "有機化学": 2.1},
    }

    # When
    result = service.get_learning_advice(
        review_summary=review_summary,
        language="ja",
    )

    # Then
    assert isinstance(result, LearningAdvice)
    assert result.advice_text == "有機化学の復習を重点的に行いましょう。"
    assert result.weak_areas == ["有機化学"]
    assert len(result.recommendations) == 2
    assert isinstance(result.model_used, str)
    assert result.processing_time_ms >= 0
    mock_client.invoke_model.assert_called_once()
```

#### TC-055-009: get_learning_advice() が英語で動作すること

- **テスト名**: 英語での学習アドバイス生成
  - **何をテストするか**: `language="en"` での動作確認
  - **期待される動作**: 英語のプロンプトが生成され、英語のアドバイスが返る
- **入力値**: 英語の review_summary と `language="en"`
  - **入力データの意味**: 英語ユーザー向けのアドバイスシナリオ
- **期待される結果**: LearningAdvice が正常に返ること
- **テストの目的**: 多言語対応の確認
- 🔵 `prompts/advice.py` の `get_advice_prompt()` が language パラメータを受け付けることから確定

```python
def test_get_learning_advice_english_language():
    # 【テスト目的】: 英語での学習アドバイス生成が正常に動作することを確認
    # 🔵

    # Given
    mock_client = MagicMock()
    service = BedrockService(bedrock_client=mock_client)

    advice_response = {
        "advice_text": "Focus on improving your vocabulary section.",
        "weak_areas": ["vocabulary"],
        "recommendations": ["Review vocabulary cards daily"]
    }
    mock_response_body = MagicMock()
    mock_response_body.read.return_value = json.dumps({
        "content": [{"text": json.dumps(advice_response)}]
    }).encode()
    mock_client.invoke_model.return_value = {"body": mock_response_body}

    # When
    result = service.get_learning_advice(
        review_summary={"total_reviews": 50, "average_grade": 2.5, "total_cards": 30,
                        "cards_due_today": 5, "streak_days": 3, "tag_performance": {"vocabulary": 2.0}},
        language="en",
    )

    # Then
    assert isinstance(result, LearningAdvice)
    assert result.advice_text == "Focus on improving your vocabulary section."
    assert result.weak_areas == ["vocabulary"]
```

#### TC-055-010: get_learning_advice() が低スコアの復習データで動作すること

- **テスト名**: 低スコアデータでの学習アドバイス生成
  - **何をテストするか**: 平均グレードが低い（2.0 以下）場合でも正常に LearningAdvice を返すこと
  - **期待される動作**: 弱点分野が複数特定され、具体的な推奨事項が生成される
- **入力値**: `average_grade=1.5`, 複数の低スコアタグ
  - **入力データの意味**: 学習が苦戦している状態の統計データ
- **期待される結果**: weak_areas と recommendations が非空リスト
- **テストの目的**: 低パフォーマンスケースの動作確認
- 🟡 要件定義書 4.2 節から妥当な推測（低スコアの具体的な AI 出力は不定だがモックで制御）

```python
def test_get_learning_advice_with_low_scores():
    # 【テスト目的】: 低スコアの復習データでアドバイスが正常に生成されることを確認
    # 🟡

    # Given
    mock_client = MagicMock()
    service = BedrockService(bedrock_client=mock_client)

    advice_response = {
        "advice_text": "全体的にスコアが低いため、基礎から見直しましょう。",
        "weak_areas": ["数学", "物理", "化学"],
        "recommendations": ["基礎カードから始める", "毎日の学習時間を増やす"]
    }
    mock_response_body = MagicMock()
    mock_response_body.read.return_value = json.dumps({
        "content": [{"text": json.dumps(advice_response)}]
    }).encode()
    mock_client.invoke_model.return_value = {"body": mock_response_body}

    # When
    result = service.get_learning_advice(
        review_summary={
            "total_reviews": 30,
            "average_grade": 1.5,
            "total_cards": 20,
            "cards_due_today": 15,
            "streak_days": 1,
            "tag_performance": {"数学": 1.2, "物理": 1.5, "化学": 1.8},
        },
        language="ja",
    )

    # Then
    assert isinstance(result, LearningAdvice)
    assert len(result.weak_areas) > 0
    assert len(result.recommendations) > 0
```

#### TC-055-011: get_learning_advice() がリトライ機構を使用すること

- **テスト名**: get_learning_advice() のリトライ機構使用確認
  - **何をテストするか**: RateLimit エラー後にリトライして成功するケース
  - **期待される動作**: 1回目失敗、2回目成功で最終的に LearningAdvice が返る
- **入力値**: 1回目 ThrottlingException、2回目成功のモック
- **期待される結果**: `invoke_model` が 2 回呼ばれ、成功する
- **テストの目的**: 新規メソッドが既存リトライ基盤を使用していることの確認
- 🔵 要件定義書 3.4 節から確定

```python
def test_get_learning_advice_uses_retry_logic():
    # 【テスト目的】: get_learning_advice() がリトライ機構を使用することを確認
    # 🔵

    # Given
    mock_client = MagicMock()
    service = BedrockService(bedrock_client=mock_client)

    advice_response = {"advice_text": "...", "weak_areas": [], "recommendations": []}
    mock_response_body = MagicMock()
    mock_response_body.read.return_value = json.dumps({
        "content": [{"text": json.dumps(advice_response)}]
    }).encode()

    mock_client.invoke_model.side_effect = [
        ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate limit"}},
            "InvokeModel",
        ),
        {"body": mock_response_body},
    ]

    # When
    result = service.get_learning_advice(
        review_summary={"total_reviews": 10, "average_grade": 3.0, "total_cards": 5,
                        "cards_due_today": 2, "streak_days": 1, "tag_performance": {}},
    )

    # Then
    assert isinstance(result, LearningAdvice)
    assert mock_client.invoke_model.call_count == 2
```

---

### 1.4 generate_cards() 既存互換性テスト

#### TC-055-012: generate_cards() が改修後も既存と同じ動作をすること

- **テスト名**: generate_cards() 既存互換性確認
  - **何をテストするか**: 例外クラスの改修後も generate_cards() が正常に動作すること
  - **期待される動作**: 既存の generate_cards() フローが変更なく機能する
- **入力値**: 既存テストと同じパターン（`input_text`, `card_count=1`）
  - **入力データの意味**: 既存テストの再現
- **期待される結果**: GenerationResult が正常に返り、cards/model_used/processing_time_ms が設定される
  - **期待結果の理由**: 既存実装の非回帰確認
- **テストの目的**: 既存機能の後方互換性保証
  - **確認ポイント**: 例外統合後も既存の動作が一切変わらないこと
- 🔵 要件定義書 3.2 節「generate_cards() のシグネチャ・動作・戻り値は一切変更しない」から確定

```python
def test_generate_cards_still_works_after_protocol_adaptation():
    # 【テスト目的】: Protocol 準拠改修後も generate_cards() が正常動作することを確認
    # 🔵

    # Given
    mock_client = MagicMock()
    service = BedrockService(bedrock_client=mock_client)

    mock_response_body = MagicMock()
    mock_response_body.read.return_value = json.dumps({
        "content": [{"text": '{"cards": [{"front": "Q", "back": "A", "tags": []}]}'}]
    }).encode()
    mock_client.invoke_model.return_value = {"body": mock_response_body}

    # When
    result = service.generate_cards(
        input_text="Test input text for card generation",
        card_count=1,
    )

    # Then
    assert len(result.cards) == 1
    assert result.cards[0].front == "Q"
    assert result.cards[0].back == "A"
    assert result.processing_time_ms >= 0
    assert isinstance(result.model_used, str)
```

---

## 2. 異常系テストケース

### 2.1 grade_answer() エラーハンドリング

#### TC-055-013: grade_answer() が Bedrock API タイムアウトで BedrockTimeoutError / AITimeoutError を送出

- **テスト名**: grade_answer() タイムアウトエラー処理
  - **エラーケースの概要**: Bedrock API がタイムアウトした場合の例外処理
  - **エラー処理の重要性**: ユーザーに適切なフィードバックを返し、リトライしない（タイムアウトは再試行で解決しにくい）
- **入力値**: `invoke_model` が `ClientError(ReadTimeoutError)` を送出
  - **不正な理由**: API のレスポンス遅延によるタイムアウト
  - **実際の発生シナリオ**: Bedrock のモデル推論が DEFAULT_TIMEOUT(30秒) を超えた場合
- **期待される結果**: `BedrockTimeoutError` が送出され、`AITimeoutError` でもキャッチ可能
  - **エラーメッセージの内容**: タイムアウトを示すメッセージ
  - **システムの安全性**: リトライせず即座にエラーを返す（_invoke_with_retry のタイムアウト非リトライ方針）
- **テストの目的**: タイムアウト時のエラーハンドリングと例外階層の確認
  - **品質保証の観点**: タイムアウトが AITimeoutError としても捕捉可能であること
- 🔵 要件定義書 4.4 節、bedrock.py `_invoke_with_retry()` のタイムアウト非リトライロジックから確定

```python
def test_grade_answer_timeout_error():
    # 【テスト目的】: タイムアウト時に BedrockTimeoutError が発生することを確認
    # 【テスト内容】: ReadTimeoutError を発生させ、例外の型と階層を検証
    # 🔵

    # Given
    mock_client = MagicMock()
    service = BedrockService(bedrock_client=mock_client)
    mock_client.invoke_model.side_effect = ClientError(
        {"Error": {"Code": "ReadTimeoutError", "Message": "Timeout"}},
        "InvokeModel",
    )

    # When / Then
    with pytest.raises(BedrockTimeoutError):
        service.grade_answer(card_front="Q", card_back="A", user_answer="A")

    # 【検証項目】: リトライなし（タイムアウトはリトライしない）
    assert mock_client.invoke_model.call_count == 1
```

#### TC-055-014: grade_answer() タイムアウトが AITimeoutError でもキャッチ可能

- **テスト名**: grade_answer() タイムアウトの AITimeoutError キャッチ確認
  - **エラーケースの概要**: BedrockTimeoutError が AITimeoutError としてもキャッチできること
  - **エラー処理の重要性**: Protocol 統一のエラーハンドリングが機能すること
- **入力値**: 同上
- **期待される結果**: `except AITimeoutError` でキャッチ可能
- **テストの目的**: 例外階層の多重継承による統一ハンドリングの確認
- 🔵 要件定義書 3.3 節の多重継承例外設計から確定

```python
def test_grade_answer_timeout_caught_as_ai_timeout_error():
    # 【テスト目的】: BedrockTimeoutError が AITimeoutError でもキャッチできることを確認
    # 🔵

    # Given
    mock_client = MagicMock()
    service = BedrockService(bedrock_client=mock_client)
    mock_client.invoke_model.side_effect = ClientError(
        {"Error": {"Code": "ReadTimeoutError", "Message": "Timeout"}},
        "InvokeModel",
    )

    # When / Then
    # 【結果検証】: AITimeoutError でキャッチ可能であること
    with pytest.raises(AITimeoutError):
        service.grade_answer(card_front="Q", card_back="A", user_answer="A")
```

#### TC-055-015: grade_answer() が Bedrock API レート制限で BedrockRateLimitError を送出

- **テスト名**: grade_answer() レート制限エラー処理
  - **エラーケースの概要**: Bedrock API がスロットリングした場合、リトライ後に例外が送出
  - **エラー処理の重要性**: リトライで回復を試みつつ、最終的に適切な例外を返す
- **入力値**: `invoke_model` が ThrottlingException を 3 回連続送出（初回 + MAX_RETRIES=2）
  - **実際の発生シナリオ**: 高トラフィック時に Bedrock API がスロットリング
- **期待される結果**: `BedrockRateLimitError` が送出、`invoke_model` が 3 回呼ばれる
  - **システムの安全性**: Full Jitter 指数バックオフでリトライ後にエラー
- **テストの目的**: レート制限時のリトライとエラーハンドリング
- 🔵 要件定義書 4.5 節、bedrock.py `_invoke_with_retry()` のリトライロジックから確定

```python
def test_grade_answer_rate_limit_error():
    # 【テスト目的】: レート制限時にリトライ後 BedrockRateLimitError が発生することを確認
    # 🔵

    # Given
    mock_client = MagicMock()
    service = BedrockService(bedrock_client=mock_client)
    mock_client.invoke_model.side_effect = ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "Rate limit"}},
        "InvokeModel",
    )

    # When / Then
    with pytest.raises(BedrockRateLimitError):
        service.grade_answer(card_front="Q", card_back="A", user_answer="A")

    # 【検証項目】: 初回 + 2回リトライ = 3回呼ばれること
    assert mock_client.invoke_model.call_count == 3
```

#### TC-055-016: grade_answer() が JSON パースエラーで BedrockParseError / AIParseError を送出

- **テスト名**: grade_answer() レスポンスパースエラー処理
  - **エラーケースの概要**: Bedrock レスポンスが不正な JSON の場合の例外処理
  - **エラー処理の重要性**: AI の不安定な出力に対して安全にエラーを返す
- **入力値**: `invoke_model` が `"This is not valid JSON"` を返すモック
  - **不正な理由**: AI が JSON 以外のテキストを返した
  - **実際の発生シナリオ**: AI が指示を無視してプレーンテキストで応答した場合
- **期待される結果**: `BedrockParseError` が送出、`AIParseError` でもキャッチ可能
  - **エラーメッセージの内容**: JSON パース失敗を示すメッセージ
- **テストの目的**: JSON パースエラーのハンドリング確認
- 🔵 要件定義書 3.5 節、4.6 節から確定

```python
def test_grade_answer_parse_error():
    # 【テスト目的】: 不正な JSON レスポンスで BedrockParseError が発生することを確認
    # 🔵

    # Given
    mock_client = MagicMock()
    service = BedrockService(bedrock_client=mock_client)

    mock_response_body = MagicMock()
    mock_response_body.read.return_value = json.dumps({
        "content": [{"text": "This is not valid JSON at all"}]
    }).encode()
    mock_client.invoke_model.return_value = {"body": mock_response_body}

    # When / Then
    with pytest.raises(BedrockParseError):
        service.grade_answer(card_front="Q", card_back="A", user_answer="A")
```

#### TC-055-017: grade_answer() パースエラーが AIParseError でもキャッチ可能

- **テスト名**: grade_answer() パースエラーの AIParseError キャッチ確認
  - **エラーケースの概要**: BedrockParseError が AIParseError としてもキャッチできること
- **入力値**: 同上
- **期待される結果**: `except AIParseError` でキャッチ可能
- **テストの目的**: 例外階層の統一ハンドリング
- 🔵 要件定義書 3.3 節から確定

```python
def test_grade_answer_parse_error_caught_as_ai_parse_error():
    # 【テスト目的】: BedrockParseError が AIParseError でもキャッチできることを確認
    # 🔵

    # Given
    mock_client = MagicMock()
    service = BedrockService(bedrock_client=mock_client)

    mock_response_body = MagicMock()
    mock_response_body.read.return_value = json.dumps({
        "content": [{"text": "Not JSON"}]
    }).encode()
    mock_client.invoke_model.return_value = {"body": mock_response_body}

    # When / Then
    with pytest.raises(AIParseError):
        service.grade_answer(card_front="Q", card_back="A", user_answer="A")
```

#### TC-055-018: grade_answer() が Bedrock API 内部エラーで BedrockInternalError を送出

- **テスト名**: grade_answer() 内部エラー処理
  - **エラーケースの概要**: Bedrock API が InternalServerException を返した場合
  - **エラー処理の重要性**: サーバー側エラーに対して適切にリトライし、最終的にエラーを返す
- **入力値**: `invoke_model` が `InternalServerException` を 3 回連続送出
  - **実際の発生シナリオ**: Bedrock サービス側の一時的な障害
- **期待される結果**: `BedrockInternalError` が送出、`invoke_model` が 3 回呼ばれる（リトライあり）
- **テストの目的**: 内部エラー時のリトライとエラーハンドリング確認
- 🔵 bedrock.py `_invoke_claude()` のエラーコードマッピング、`_invoke_with_retry()` のリトライロジックから確定

```python
def test_grade_answer_internal_error():
    # 【テスト目的】: Bedrock API 内部エラー時に BedrockInternalError が発生することを確認
    # 🔵

    # Given
    mock_client = MagicMock()
    service = BedrockService(bedrock_client=mock_client)
    mock_client.invoke_model.side_effect = ClientError(
        {"Error": {"Code": "InternalServerException", "Message": "Internal"}},
        "InvokeModel",
    )

    # When / Then
    with pytest.raises(BedrockInternalError):
        service.grade_answer(card_front="Q", card_back="A", user_answer="A")

    # 【検証項目】: 内部エラーはリトライされる（3回呼ばれる）
    assert mock_client.invoke_model.call_count == 3
```

---

### 2.2 get_learning_advice() エラーハンドリング

#### TC-055-019: get_learning_advice() が Bedrock API タイムアウトで BedrockTimeoutError を送出

- **テスト名**: get_learning_advice() タイムアウトエラー処理
  - **エラーケースの概要**: アドバイス生成時のタイムアウト
- **入力値**: `invoke_model` が `ReadTimeoutError` を送出
- **期待される結果**: `BedrockTimeoutError` が送出、リトライなし
- **テストの目的**: get_learning_advice() のタイムアウトハンドリング確認
- 🔵 grade_answer() と同じパターン、要件定義書 4.4 節から確定

```python
def test_get_learning_advice_timeout_error():
    # 【テスト目的】: get_learning_advice() のタイムアウトエラーを確認
    # 🔵

    # Given
    mock_client = MagicMock()
    service = BedrockService(bedrock_client=mock_client)
    mock_client.invoke_model.side_effect = ClientError(
        {"Error": {"Code": "ReadTimeoutError", "Message": "Timeout"}},
        "InvokeModel",
    )

    # When / Then
    with pytest.raises(BedrockTimeoutError):
        service.get_learning_advice(
            review_summary={"total_reviews": 10, "average_grade": 3.0, "total_cards": 5,
                            "cards_due_today": 2, "streak_days": 1, "tag_performance": {}},
        )

    assert mock_client.invoke_model.call_count == 1
```

#### TC-055-020: get_learning_advice() が JSON パースエラーで BedrockParseError を送出

- **テスト名**: get_learning_advice() パースエラー処理
  - **エラーケースの概要**: アドバイス生成時のレスポンスが不正な JSON
- **入力値**: `invoke_model` が不正な JSON テキストを返す
- **期待される結果**: `BedrockParseError` が送出
- **テストの目的**: get_learning_advice() の JSON パースエラーハンドリング
- 🔵 grade_answer() と同じパターンから確定

```python
def test_get_learning_advice_parse_error():
    # 【テスト目的】: get_learning_advice() のパースエラーを確認
    # 🔵

    # Given
    mock_client = MagicMock()
    service = BedrockService(bedrock_client=mock_client)

    mock_response_body = MagicMock()
    mock_response_body.read.return_value = json.dumps({
        "content": [{"text": "Invalid response text"}]
    }).encode()
    mock_client.invoke_model.return_value = {"body": mock_response_body}

    # When / Then
    with pytest.raises(BedrockParseError):
        service.get_learning_advice(
            review_summary={"total_reviews": 10, "average_grade": 3.0, "total_cards": 5,
                            "cards_due_today": 2, "streak_days": 1, "tag_performance": {}},
        )
```

#### TC-055-021: get_learning_advice() が Bedrock API レート制限で BedrockRateLimitError を送出

- **テスト名**: get_learning_advice() レート制限エラー処理
  - **エラーケースの概要**: アドバイス生成時のレート制限
- **入力値**: `invoke_model` が ThrottlingException を 3 回連続送出
- **期待される結果**: `BedrockRateLimitError` が送出、3 回呼ばれること
- **テストの目的**: get_learning_advice() のレート制限ハンドリング
- 🔵 grade_answer() と同じパターンから確定

```python
def test_get_learning_advice_rate_limit_error():
    # 【テスト目的】: get_learning_advice() のレート制限エラーを確認
    # 🔵

    # Given
    mock_client = MagicMock()
    service = BedrockService(bedrock_client=mock_client)
    mock_client.invoke_model.side_effect = ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "Rate limit"}},
        "InvokeModel",
    )

    # When / Then
    with pytest.raises(BedrockRateLimitError):
        service.get_learning_advice(
            review_summary={"total_reviews": 10, "average_grade": 3.0, "total_cards": 5,
                            "cards_due_today": 2, "streak_days": 1, "tag_performance": {}},
        )

    assert mock_client.invoke_model.call_count == 3
```

---

### 2.3 例外階層テスト

#### TC-055-022: 例外クラスの AIServiceError 階層への統合確認

- **テスト名**: 例外クラス階層の issubclass 検証
  - **エラーケースの概要**: 全ての Bedrock 例外が対応する AI 例外を継承していること
  - **エラー処理の重要性**: Protocol 統一のエラーハンドリングが機能するための前提条件
- **入力値**: 各例外クラスの `issubclass()` チェック
  - **不正な理由**: N/A（静的な型階層チェック）
  - **実際の発生シナリオ**: 開発者が `except AIServiceError` で統一的にエラーハンドリングするケース
- **期待される結果**:
  - `issubclass(BedrockServiceError, AIServiceError)` == True
  - `issubclass(BedrockTimeoutError, AITimeoutError)` == True
  - `issubclass(BedrockTimeoutError, BedrockServiceError)` == True
  - `issubclass(BedrockTimeoutError, AIServiceError)` == True
  - `issubclass(BedrockRateLimitError, AIRateLimitError)` == True
  - `issubclass(BedrockRateLimitError, BedrockServiceError)` == True
  - `issubclass(BedrockInternalError, AIInternalError)` == True
  - `issubclass(BedrockInternalError, BedrockServiceError)` == True
  - `issubclass(BedrockParseError, AIParseError)` == True
  - `issubclass(BedrockParseError, BedrockServiceError)` == True
  - **期待結果の理由**: 多重継承により、両方の階層からキャッチ可能であること
- **テストの目的**: 例外階層の完全性と後方互換性の確認
  - **品質保証の観点**: 既存コードの `except BedrockServiceError` と新規コードの `except AIServiceError` が両方動作すること
- 🔵 要件定義書 3.3 節の多重継承設計から確定

```python
def test_exception_hierarchy_ai_service_error():
    # 【テスト目的】: 全 Bedrock 例外が AIServiceError 階層に統合されていることを確認
    # 🔵

    # BedrockServiceError → AIServiceError
    assert issubclass(BedrockServiceError, AIServiceError)

    # BedrockTimeoutError → AITimeoutError + BedrockServiceError
    assert issubclass(BedrockTimeoutError, AITimeoutError)
    assert issubclass(BedrockTimeoutError, BedrockServiceError)
    assert issubclass(BedrockTimeoutError, AIServiceError)

    # BedrockRateLimitError → AIRateLimitError + BedrockServiceError
    assert issubclass(BedrockRateLimitError, AIRateLimitError)
    assert issubclass(BedrockRateLimitError, BedrockServiceError)
    assert issubclass(BedrockRateLimitError, AIServiceError)

    # BedrockInternalError → AIInternalError + BedrockServiceError
    assert issubclass(BedrockInternalError, AIInternalError)
    assert issubclass(BedrockInternalError, BedrockServiceError)
    assert issubclass(BedrockInternalError, AIServiceError)

    # BedrockParseError → AIParseError + BedrockServiceError
    assert issubclass(BedrockParseError, AIParseError)
    assert issubclass(BedrockParseError, BedrockServiceError)
    assert issubclass(BedrockParseError, AIServiceError)
```

#### TC-055-023: 後方互換性 - except BedrockServiceError で新例外をキャッチ可能

- **テスト名**: 後方互換性テスト - BedrockServiceError でのキャッチ
  - **エラーケースの概要**: 既存コードの `except BedrockServiceError` が改修後の例外もキャッチできること
  - **エラー処理の重要性**: 既存コードの破壊を防ぐ
- **入力値**: 各具体的例外のインスタンスを `except BedrockServiceError` でキャッチ
- **期待される結果**: 全例外がキャッチされること
  - **システムの安全性**: 既存のエラーハンドリングコードが引き続き動作する
- **テストの目的**: 後方互換性の実際の動作確認
- 🔵 要件定義書 3.3 節「後方互換性保証」、4.9 節「例外階層の互換性確認」から確定

```python
def test_backward_compatibility_bedrock_service_error_catches_all():
    # 【テスト目的】: except BedrockServiceError が全 Bedrock 例外をキャッチできることを確認
    # 🔵

    # 【テストデータ準備】: 各例外インスタンスを作成
    exceptions = [
        BedrockTimeoutError("timeout"),
        BedrockRateLimitError("rate limit"),
        BedrockInternalError("internal"),
        BedrockParseError("parse"),
    ]

    for exc in exceptions:
        # 【結果検証】: except BedrockServiceError でキャッチ可能
        try:
            raise exc
        except BedrockServiceError:
            pass  # 期待通りキャッチされた
        except Exception:
            pytest.fail(f"{type(exc).__name__} was not caught by except BedrockServiceError")
```

#### TC-055-024: Protocol 統一ハンドリング - except AIServiceError で Bedrock 例外をキャッチ可能

- **テスト名**: Protocol 統一ハンドリングテスト - AIServiceError でのキャッチ
  - **エラーケースの概要**: 新規コードの `except AIServiceError` が Bedrock 例外をキャッチできること
  - **エラー処理の重要性**: Protocol 統一のエラーハンドリングが機能すること
- **入力値**: 各 Bedrock 例外のインスタンスを `except AIServiceError` でキャッチ
- **期待される結果**: 全例外がキャッチされること
- **テストの目的**: Protocol 統一エラーハンドリングの確認
- 🔵 要件定義書 3.3 節、4.9 節から確定

```python
def test_ai_service_error_catches_bedrock_exceptions():
    # 【テスト目的】: except AIServiceError が全 Bedrock 例外をキャッチできることを確認
    # 🔵

    exceptions = [
        BedrockServiceError("base"),
        BedrockTimeoutError("timeout"),
        BedrockRateLimitError("rate limit"),
        BedrockInternalError("internal"),
        BedrockParseError("parse"),
    ]

    for exc in exceptions:
        try:
            raise exc
        except AIServiceError:
            pass
        except Exception:
            pytest.fail(f"{type(exc).__name__} was not caught by except AIServiceError")
```

#### TC-055-025: 具体的な AIError でも Bedrock 例外をキャッチ可能

- **テスト名**: 具体的 AI 例外での Bedrock 例外キャッチ確認
  - **エラーケースの概要**: `except AITimeoutError` が `BedrockTimeoutError` をキャッチできること
  - **エラー処理の重要性**: 型ごとのエラーハンドリングが機能すること
- **入力値**: 各 Bedrock 例外を対応する AI 例外でキャッチ
- **期待される結果**: 対応する AI 例外でキャッチ可能
- **テストの目的**: 多重継承による具体的例外の統一ハンドリング確認
- 🔵 要件定義書 3.3 節から確定

```python
def test_specific_ai_errors_catch_bedrock_exceptions():
    # 【テスト目的】: 具体的な AI 例外が対応する Bedrock 例外をキャッチできることを確認
    # 🔵

    # AITimeoutError → BedrockTimeoutError
    with pytest.raises(AITimeoutError):
        raise BedrockTimeoutError("timeout")

    # AIRateLimitError → BedrockRateLimitError
    with pytest.raises(AIRateLimitError):
        raise BedrockRateLimitError("rate limit")

    # AIInternalError → BedrockInternalError
    with pytest.raises(AIInternalError):
        raise BedrockInternalError("internal")

    # AIParseError → BedrockParseError
    with pytest.raises(AIParseError):
        raise BedrockParseError("parse")
```

---

## 3. 境界値テストケース

#### TC-055-026: grade_answer() の grade 値境界 - 最小値 0

- **テスト名**: grade 最小値（0）の正常処理
  - **境界値の意味**: SM-2 グレードの最小値。Complete blackout を表す
  - **境界値での動作保証**: grade=0 が正しく GradingResult に格納される
- **入力値**: モック Bedrock レスポンス `{"grade": 0, "reasoning": "...", "feedback": "..."}`
  - **境界値選択の根拠**: SM-2 グレード定義の下限
- **期待される結果**: `result.grade == 0`
  - **境界での正確性**: 0 が int として正しく変換される
- **テストの目的**: SM-2 グレード最小値の処理確認
  - **堅牢性の確認**: 下限値での動作安定性
- 🔵 `prompts/grading.py` の SM2_GRADE_DEFINITIONS (Grade 0: Complete blackout) から確定

```python
def test_grade_answer_minimum_grade_zero():
    # 【テスト目的】: grade=0（最小値）が正しく処理されることを確認
    # 🔵

    # Given
    mock_client = MagicMock()
    service = BedrockService(bedrock_client=mock_client)

    mock_response_body = MagicMock()
    mock_response_body.read.return_value = json.dumps({
        "content": [{"text": json.dumps({"grade": 0, "reasoning": "Complete blackout", "feedback": "..."})}]
    }).encode()
    mock_client.invoke_model.return_value = {"body": mock_response_body}

    # When
    result = service.grade_answer(card_front="Q", card_back="A", user_answer="")

    # Then
    assert result.grade == 0
```

#### TC-055-027: grade_answer() の grade 値境界 - 最大値 5

- **テスト名**: grade 最大値（5）の正常処理
  - **境界値の意味**: SM-2 グレードの最大値。Perfect response を表す
  - **境界値での動作保証**: grade=5 が正しく GradingResult に格納される
- **入力値**: モック Bedrock レスポンス `{"grade": 5, "reasoning": "...", "feedback": "..."}`
  - **境界値選択の根拠**: SM-2 グレード定義の上限
- **期待される結果**: `result.grade == 5`
- **テストの目的**: SM-2 グレード最大値の処理確認
- 🔵 `prompts/grading.py` の SM2_GRADE_DEFINITIONS (Grade 5: Perfect response) から確定

```python
def test_grade_answer_maximum_grade_five():
    # 【テスト目的】: grade=5（最大値）が正しく処理されることを確認
    # 🔵

    # Given
    mock_client = MagicMock()
    service = BedrockService(bedrock_client=mock_client)

    mock_response_body = MagicMock()
    mock_response_body.read.return_value = json.dumps({
        "content": [{"text": json.dumps({"grade": 5, "reasoning": "Perfect", "feedback": "..."})}]
    }).encode()
    mock_client.invoke_model.return_value = {"body": mock_response_body}

    # When
    result = service.grade_answer(card_front="Q", card_back="A", user_answer="A")

    # Then
    assert result.grade == 5
```

#### TC-055-028: grade_answer() の grade 値が範囲外（6以上）の場合

- **テスト名**: grade 範囲外（上限超過）のハンドリング
  - **境界値の意味**: SM-2 グレードは 0-5 のみ。6 以上は不正値
  - **境界値での動作保証**: 範囲外の値が適切に処理されること（エラーまたはクランプ）
- **入力値**: モック Bedrock レスポンス `{"grade": 6, "reasoning": "...", "feedback": "..."}`
  - **境界値選択の根拠**: SM-2 定義の上限(5)の直上
  - **実際の使用場面**: AI が不正な grade 値を返した場合
- **期待される結果**: `BedrockParseError` / `AIParseError` が送出される、または grade が 0-5 にクランプされる
  - **一貫した動作**: 実装判断に依存するが、不正値を無条件に許容しないこと
- **テストの目的**: 不正な AI 出力に対する堅牢性確認
- 🟡 要件定義書 4.7 節「grade 値のバリデーション」から妥当な推測。具体的な動作（エラー or クランプ）は実装判断

```python
def test_grade_answer_out_of_range_grade():
    # 【テスト目的】: grade が範囲外(6)の場合のハンドリングを確認
    # 【注意】: 実装に応じて AIParseError を期待するか、クランプを期待するか調整が必要
    # 🟡

    # Given
    mock_client = MagicMock()
    service = BedrockService(bedrock_client=mock_client)

    mock_response_body = MagicMock()
    mock_response_body.read.return_value = json.dumps({
        "content": [{"text": json.dumps({"grade": 6, "reasoning": "...", "feedback": "..."})}]
    }).encode()
    mock_client.invoke_model.return_value = {"body": mock_response_body}

    # When / Then
    # 実装方針A: エラーを送出する場合
    # with pytest.raises((BedrockParseError, AIParseError)):
    #     service.grade_answer(card_front="Q", card_back="A", user_answer="A")

    # 実装方針B: クランプする場合
    # result = service.grade_answer(card_front="Q", card_back="A", user_answer="A")
    # assert 0 <= result.grade <= 5
    pass  # 実装方針に応じてアサーションを選択
```

#### TC-055-029: get_learning_advice() の空 weak_areas / recommendations

- **テスト名**: 空リストの weak_areas と recommendations の処理
  - **境界値の意味**: AI が弱点分野や推奨事項を特定しない（優秀な学習者の場合）
  - **境界値での動作保証**: 空リストが正常値として処理されること
- **入力値**: モック Bedrock レスポンス `{"advice_text": "...", "weak_areas": [], "recommendations": []}`
  - **境界値選択の根拠**: リストの最小要素数（0）
  - **実際の使用場面**: 全タグで高スコアの学習者にアドバイスを生成する場合
- **期待される結果**: `result.weak_areas == []`, `result.recommendations == []` で正常終了
  - **一貫した動作**: 空リストは有効な値として許容される
- **テストの目的**: 空リスト境界値での動作確認
- 🟡 要件定義書 4.8 節から妥当な推測（空リストの明示的な仕様なし、許容するのが妥当）

```python
def test_get_learning_advice_empty_weak_areas_and_recommendations():
    # 【テスト目的】: 空の weak_areas/recommendations が正常に処理されることを確認
    # 🟡

    # Given
    mock_client = MagicMock()
    service = BedrockService(bedrock_client=mock_client)

    advice_response = {
        "advice_text": "素晴らしい学習成績です！この調子で頑張りましょう。",
        "weak_areas": [],
        "recommendations": []
    }
    mock_response_body = MagicMock()
    mock_response_body.read.return_value = json.dumps({
        "content": [{"text": json.dumps(advice_response)}]
    }).encode()
    mock_client.invoke_model.return_value = {"body": mock_response_body}

    # When
    result = service.get_learning_advice(
        review_summary={
            "total_reviews": 200,
            "average_grade": 4.8,
            "total_cards": 100,
            "cards_due_today": 3,
            "streak_days": 30,
            "tag_performance": {"数学": 4.9, "英語": 4.7},
        },
        language="ja",
    )

    # Then
    assert isinstance(result, LearningAdvice)
    assert result.weak_areas == []
    assert result.recommendations == []
    assert len(result.advice_text) > 0
```

#### TC-055-030: get_learning_advice() の空 tag_performance

- **テスト名**: 空の tag_performance での動作確認
  - **境界値の意味**: タグ別パフォーマンスデータがない場合
  - **境界値での動作保証**: tag_performance が空辞書でも正常動作すること
- **入力値**: `tag_performance={}` の review_summary
  - **実際の使用場面**: 新規ユーザーでまだタグ別統計がない場合
- **期待される結果**: LearningAdvice が正常に返ること
- **テストの目的**: 最小限のデータでの動作確認
- 🟡 `prompts/advice.py` の `get_advice_prompt()` が空 tag_performance で "(no tag data available)" を出力することから推測

```python
def test_get_learning_advice_empty_tag_performance():
    # 【テスト目的】: 空の tag_performance でも正常に動作することを確認
    # 🟡

    # Given
    mock_client = MagicMock()
    service = BedrockService(bedrock_client=mock_client)

    advice_response = {
        "advice_text": "タグ別データがないため、全般的なアドバイスです。",
        "weak_areas": [],
        "recommendations": ["まずカードにタグを付けて学習しましょう"]
    }
    mock_response_body = MagicMock()
    mock_response_body.read.return_value = json.dumps({
        "content": [{"text": json.dumps(advice_response)}]
    }).encode()
    mock_client.invoke_model.return_value = {"body": mock_response_body}

    # When
    result = service.get_learning_advice(
        review_summary={
            "total_reviews": 5,
            "average_grade": 3.0,
            "total_cards": 3,
            "cards_due_today": 1,
            "streak_days": 1,
            "tag_performance": {},
        },
    )

    # Then
    assert isinstance(result, LearningAdvice)
    assert len(result.advice_text) > 0
```

#### TC-055-031: grade_answer() のレスポンスがマークダウンコードブロックで囲まれている場合

- **テスト名**: マークダウンコードブロック内 JSON のパース
  - **境界値の意味**: AI がレスポンスを ` ```json ... ``` ` で囲む場合がある
  - **境界値での動作保証**: コードブロック内の JSON を正しく抽出・パースできること
- **入力値**: ` ```json\n{"grade": 4, ...}\n``` ` 形式のレスポンス
  - **実際の使用場面**: Claude がマークダウン形式で応答するケース
- **期待される結果**: JSON が正しくパースされ、GradingResult が返ること
- **テストの目的**: AI レスポンスの多様な形式への対応
  - **堅牢性の確認**: コードブロック有無にかかわらず正常動作
- 🟡 要件定義書 3.5 節「マークダウンコードブロックからの抽出も考慮する」から推測。既存 `_parse_response()` にはこのロジックがあるが、新規メソッドにも必要

```python
def test_grade_answer_json_in_markdown_code_block():
    # 【テスト目的】: マークダウンコードブロック内の JSON が正しくパースされることを確認
    # 🟡

    # Given
    mock_client = MagicMock()
    service = BedrockService(bedrock_client=mock_client)

    json_in_code_block = '```json\n{"grade": 4, "reasoning": "Good answer.", "feedback": "Nice!"}\n```'
    mock_response_body = MagicMock()
    mock_response_body.read.return_value = json.dumps({
        "content": [{"text": json_in_code_block}]
    }).encode()
    mock_client.invoke_model.return_value = {"body": mock_response_body}

    # When
    result = service.grade_answer(card_front="Q", card_back="A", user_answer="A")

    # Then
    assert isinstance(result, GradingResult)
    assert result.grade == 4
```

#### TC-055-032: get_learning_advice() のレスポンスがマークダウンコードブロックで囲まれている場合

- **テスト名**: get_learning_advice() のマークダウンコードブロックパース
  - **境界値の意味**: AI がアドバイスレスポンスをコードブロックで囲む場合
- **入力値**: ` ```json\n{"advice_text": "...", ...}\n``` ` 形式のレスポンス
- **期待される結果**: JSON が正しくパースされ、LearningAdvice が返ること
- **テストの目的**: AI レスポンス形式の多様性への対応
- 🟡 要件定義書 3.5 節から推測

```python
def test_get_learning_advice_json_in_markdown_code_block():
    # 【テスト目的】: get_learning_advice() がマークダウンコードブロック内 JSON を処理できることを確認
    # 🟡

    # Given
    mock_client = MagicMock()
    service = BedrockService(bedrock_client=mock_client)

    json_in_code_block = '```json\n{"advice_text": "Keep studying!", "weak_areas": ["math"], "recommendations": ["Practice daily"]}\n```'
    mock_response_body = MagicMock()
    mock_response_body.read.return_value = json.dumps({
        "content": [{"text": json_in_code_block}]
    }).encode()
    mock_client.invoke_model.return_value = {"body": mock_response_body}

    # When
    result = service.get_learning_advice(
        review_summary={"total_reviews": 10, "average_grade": 2.5, "total_cards": 5,
                        "cards_due_today": 2, "streak_days": 1, "tag_performance": {}},
    )

    # Then
    assert isinstance(result, LearningAdvice)
    assert result.advice_text == "Keep studying!"
```

#### TC-055-033: processing_time_ms が 0 以上であることの確認

- **テスト名**: processing_time_ms の非負値確認
  - **境界値の意味**: 処理時間は 0 以上の整数であるべき（マイナスにはなり得ない）
  - **境界値での動作保証**: モック環境でも processing_time_ms >= 0
- **入力値**: 正常なモックレスポンス
- **期待される結果**: `result.processing_time_ms >= 0` かつ `isinstance(result.processing_time_ms, int)`
  - **境界での正確性**: 高速なモック環境でも 0 以上になること
- **テストの目的**: メタデータの型と値の確認
- 🔵 要件定義書 2.2 節、2.3 節の GradingResult/LearningAdvice 定義から確定

```python
def test_processing_time_ms_is_non_negative_integer():
    # 【テスト目的】: grade_answer() と get_learning_advice() の processing_time_ms が非負整数であることを確認
    # 🔵

    # Given
    mock_client = MagicMock()
    service = BedrockService(bedrock_client=mock_client)

    # grade_answer 用
    grading_response = {"grade": 3, "reasoning": "OK", "feedback": "..."}
    mock_response_body_grading = MagicMock()
    mock_response_body_grading.read.return_value = json.dumps({
        "content": [{"text": json.dumps(grading_response)}]
    }).encode()
    mock_client.invoke_model.return_value = {"body": mock_response_body_grading}

    result_grading = service.grade_answer(card_front="Q", card_back="A", user_answer="A")
    assert isinstance(result_grading.processing_time_ms, int)
    assert result_grading.processing_time_ms >= 0

    # get_learning_advice 用
    mock_client.reset_mock()
    advice_response = {"advice_text": "...", "weak_areas": [], "recommendations": []}
    mock_response_body_advice = MagicMock()
    mock_response_body_advice.read.return_value = json.dumps({
        "content": [{"text": json.dumps(advice_response)}]
    }).encode()
    mock_client.invoke_model.return_value = {"body": mock_response_body_advice}

    result_advice = service.get_learning_advice(
        review_summary={"total_reviews": 10, "average_grade": 3.0, "total_cards": 5,
                        "cards_due_today": 2, "streak_days": 1, "tag_performance": {}},
    )
    assert isinstance(result_advice.processing_time_ms, int)
    assert result_advice.processing_time_ms >= 0
```

#### TC-055-034: model_used が実際のモデル ID を含むこと

- **テスト名**: model_used フィールドがサービスのモデル ID と一致すること
  - **境界値の意味**: model_used はカスタムまたはデフォルトのモデル ID を正確に反映すべき
  - **境界値での動作保証**: カスタムモデル ID が正しく GradingResult/LearningAdvice に格納される
- **入力値**: `BedrockService(model_id="custom-model-id", bedrock_client=mock_client)`
- **期待される結果**: `result.model_used == "custom-model-id"`
- **テストの目的**: モデル ID の伝播確認
- 🔵 既存テスト `test_model_used_in_result` のパターン + 要件定義書 2.2/2.3 節から確定

```python
def test_model_used_matches_service_model_id():
    # 【テスト目的】: GradingResult/LearningAdvice の model_used がサービスのモデル ID と一致することを確認
    # 🔵

    # Given
    mock_client = MagicMock()
    service = BedrockService(model_id="custom-model-id", bedrock_client=mock_client)

    grading_response = {"grade": 4, "reasoning": "Good", "feedback": "..."}
    mock_response_body = MagicMock()
    mock_response_body.read.return_value = json.dumps({
        "content": [{"text": json.dumps(grading_response)}]
    }).encode()
    mock_client.invoke_model.return_value = {"body": mock_response_body}

    # When
    result = service.grade_answer(card_front="Q", card_back="A", user_answer="A")

    # Then
    assert result.model_used == "custom-model-id"
```

---

## テストケースサマリー

| ID | カテゴリ | テスト名 | 信頼性 |
|----|---------|---------|--------|
| TC-055-001 | 正常系 | Protocol 準拠 isinstance チェック | 🔵 |
| TC-055-002 | 正常系 | Protocol メソッド存在確認 | 🔵 |
| TC-055-003 | 正常系 | grade_answer() 正解回答（日本語） | 🔵 |
| TC-055-004 | 正常系 | grade_answer() 不正解回答（英語） | 🔵 |
| TC-055-005 | 正常系 | grade_answer() 部分正解 | 🟡 |
| TC-055-006 | 正常系 | grade_answer() 英語言語 | 🔵 |
| TC-055-007 | 正常系 | grade_answer() リトライ機構使用 | 🔵 |
| TC-055-008 | 正常系 | get_learning_advice() dict 入力 | 🔵 |
| TC-055-009 | 正常系 | get_learning_advice() 英語言語 | 🔵 |
| TC-055-010 | 正常系 | get_learning_advice() 低スコアデータ | 🟡 |
| TC-055-011 | 正常系 | get_learning_advice() リトライ機構 | 🔵 |
| TC-055-012 | 正常系 | generate_cards() 既存互換性 | 🔵 |
| TC-055-013 | 異常系 | grade_answer() タイムアウト | 🔵 |
| TC-055-014 | 異常系 | grade_answer() タイムアウト AITimeoutError キャッチ | 🔵 |
| TC-055-015 | 異常系 | grade_answer() レート制限 | 🔵 |
| TC-055-016 | 異常系 | grade_answer() パースエラー | 🔵 |
| TC-055-017 | 異常系 | grade_answer() パースエラー AIParseError キャッチ | 🔵 |
| TC-055-018 | 異常系 | grade_answer() 内部エラー | 🔵 |
| TC-055-019 | 異常系 | get_learning_advice() タイムアウト | 🔵 |
| TC-055-020 | 異常系 | get_learning_advice() パースエラー | 🔵 |
| TC-055-021 | 異常系 | get_learning_advice() レート制限 | 🔵 |
| TC-055-022 | 異常系 | 例外階層 issubclass 検証 | 🔵 |
| TC-055-023 | 異常系 | 後方互換性 BedrockServiceError キャッチ | 🔵 |
| TC-055-024 | 異常系 | Protocol 統一 AIServiceError キャッチ | 🔵 |
| TC-055-025 | 異常系 | 具体的 AI 例外キャッチ | 🔵 |
| TC-055-026 | 境界値 | grade 最小値 0 | 🔵 |
| TC-055-027 | 境界値 | grade 最大値 5 | 🔵 |
| TC-055-028 | 境界値 | grade 範囲外 6 | 🟡 |
| TC-055-029 | 境界値 | 空 weak_areas/recommendations | 🟡 |
| TC-055-030 | 境界値 | 空 tag_performance | 🟡 |
| TC-055-031 | 境界値 | JSON マークダウンコードブロック（grade） | 🟡 |
| TC-055-032 | 境界値 | JSON マークダウンコードブロック（advice） | 🟡 |
| TC-055-033 | 境界値 | processing_time_ms 非負整数 | 🔵 |
| TC-055-034 | 境界値 | model_used モデル ID 一致 | 🔵 |

---

## 信頼性レベルサマリー

### 統計

- 🔵 **青信号**: 27 件 (79%)
- 🟡 **黄信号**: 7 件 (21%)
- 🔴 **赤信号**: 0 件 (0%)

### 黄信号の詳細

| ID | テスト名 | 黄信号の理由 |
|----|---------|-------------|
| TC-055-005 | 部分正解の採点 | 部分正解の具体的 grade 値は AI 依存だがモックで制御するため影響小 |
| TC-055-010 | 低スコアデータのアドバイス | 低スコアの具体的出力は AI 依存だがモックで制御 |
| TC-055-028 | grade 範囲外のハンドリング | バリデーション方法（エラー or クランプ）は実装判断 |
| TC-055-029 | 空 weak_areas/recommendations | プロンプトは非空を期待するが、空リストの明示的仕様なし |
| TC-055-030 | 空 tag_performance | データなし時の動作は advice.py の実装から推測 |
| TC-055-031 | grade_answer マークダウンコードブロック | 新規メソッドにコードブロック抽出が実装されるかは実装判断 |
| TC-055-032 | get_learning_advice マークダウンコードブロック | 同上 |

---

## テスト実装時の import 一覧

```python
import io
import json
import pytest
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError

from services.bedrock import (
    BedrockService,
    BedrockServiceError,
    BedrockTimeoutError,
    BedrockRateLimitError,
    BedrockInternalError,
    BedrockParseError,
    GeneratedCard,
)
from services.ai_service import (
    AIService,
    AIServiceError,
    AITimeoutError,
    AIRateLimitError,
    AIInternalError,
    AIParseError,
    GradingResult,
    LearningAdvice,
)
from services.prompts import get_card_generation_prompt
```

---

## テストクラス構成案

```python
class TestBedrockServiceProtocol:
    """Protocol 準拠テスト"""
    # TC-055-001, TC-055-002

class TestGradeAnswerSuccess:
    """grade_answer() 正常系テスト"""
    # TC-055-003, TC-055-004, TC-055-005, TC-055-006, TC-055-007

class TestGetLearningAdviceSuccess:
    """get_learning_advice() 正常系テスト"""
    # TC-055-008, TC-055-009, TC-055-010, TC-055-011

class TestGenerateCardsCompatibility:
    """generate_cards() 既存互換性テスト"""
    # TC-055-012

class TestGradeAnswerErrors:
    """grade_answer() エラーハンドリングテスト"""
    # TC-055-013, TC-055-014, TC-055-015, TC-055-016, TC-055-017, TC-055-018

class TestGetLearningAdviceErrors:
    """get_learning_advice() エラーハンドリングテスト"""
    # TC-055-019, TC-055-020, TC-055-021

class TestExceptionHierarchy:
    """例外階層テスト"""
    # TC-055-022, TC-055-023, TC-055-024, TC-055-025

class TestBoundaryValues:
    """境界値テスト"""
    # TC-055-026 ~ TC-055-034
```
