# TASK-0054: プロンプトモジュールディレクトリ化 - TDD テストケース定義

**タスクID**: TASK-0054
**機能名**: プロンプトモジュールディレクトリ化
**要件名**: ai-strands-migration
**出力ファイル**: `docs/implements/ai-strands-migration/TASK-0054/prompt-module-dir-testcases.md`
**作成日**: 2026-02-23

---

## 1. 正常系テストケース（基本的な動作）

### TC-001: generate.py - 日本語カード生成プロンプト（既存互換）

- **テスト名**: 日本語カード生成プロンプトが正しく生成されること
  - **何をテストするか**: `get_card_generation_prompt()` が日本語プロンプト文字列を正しく生成する
  - **期待される動作**: 入力テキスト・カード数・難易度・言語がプロンプト文字列に埋め込まれる
- **入力値**: `input_text="テスト入力テキスト"`, `card_count=5`, `difficulty="medium"`, `language="ja"`
  - **入力データの意味**: 既存テスト `test_bedrock.py::test_japanese_prompt_generation` と同一入力。互換性確認の基準値
- **期待される結果**:
  - 戻り値は `str` 型
  - `"フラッシュカード作成の専門家"` を含む
  - `"5枚作成"` を含む
  - `"テスト入力テキスト"` を含む
  - `"medium"` を含む
  - **期待結果の理由**: 既存 `prompts.py` の日本語プロンプトテンプレートと完全互換であること
- **テストの目的**: 既存テストとの後方互換性を確認
  - **確認ポイント**: import パスが `services.prompts.generate` または `services.prompts` 経由で動作すること
- 🔵 **青信号**: 既存テスト `test_bedrock.py` の TestPrompts クラスと同一のアサーション

```python
# 【テスト目的】: generate.py の日本語プロンプト生成が既存 prompts.py と完全互換であることを確認
# 【テスト内容】: get_card_generation_prompt を日本語パラメータで呼び出し、出力文字列を検証
# 【期待される動作】: 既存テストと同一のアサーションがすべて通過する
# 🔵 既存テスト test_bedrock.py::test_japanese_prompt_generation から移植

def test_japanese_prompt_generation():
    # 【テストデータ準備】: 既存テストと同じ入力パラメータを使用
    # 【初期条件設定】: prompts パッケージが正しく初期化されていること
    # 【前提条件確認】: services.prompts.generate モジュールが import 可能であること

    # 【実際の処理実行】: get_card_generation_prompt を日本語設定で呼び出す
    from services.prompts.generate import get_card_generation_prompt
    prompt = get_card_generation_prompt(
        input_text="テスト入力テキスト",
        card_count=5,
        difficulty="medium",
        language="ja",
    )

    # 【結果検証】: 日本語テンプレートのキーフレーズが含まれていること
    # 【期待値確認】: 既存 prompts.py と同じ出力が得られること
    # 【品質保証】: 既存機能の後方互換性を保証

    # 【検証項目】: プロンプトが文字列であること
    # 🔵 基本的な型チェック
    assert isinstance(prompt, str)
    # 【検証項目】: 日本語テンプレートの専門家フレーズが含まれること
    # 🔵 既存テストと同一
    assert "フラッシュカード作成の専門家" in prompt
    # 【検証項目】: カード枚数が正しく埋め込まれること
    # 🔵 既存テストと同一
    assert "5枚作成" in prompt
    # 【検証項目】: 入力テキストが正しく埋め込まれること
    # 🔵 既存テストと同一
    assert "テスト入力テキスト" in prompt
    # 【検証項目】: 難易度が正しく埋め込まれること
    # 🔵 既存テストと同一
    assert "medium" in prompt
```

### TC-002: generate.py - 英語カード生成プロンプト（既存互換）

- **テスト名**: 英語カード生成プロンプトが正しく生成されること
  - **何をテストするか**: `get_card_generation_prompt()` が英語プロンプト文字列を正しく生成する
  - **期待される動作**: 英語テンプレートが使用され、全パラメータが埋め込まれる
- **入力値**: `input_text="Test input text"`, `card_count=3`, `difficulty="hard"`, `language="en"`
  - **入力データの意味**: 既存テスト `test_bedrock.py::test_english_prompt_generation` と同一入力
- **期待される結果**:
  - `"expert at creating flashcards"` を含む
  - `"3 effective flashcards"` を含む
  - `"Test input text"` を含む
  - `"hard"` を含む
  - **期待結果の理由**: 既存 `prompts.py` の英語プロンプトテンプレートと完全互換
- **テストの目的**: 英語テンプレート分岐の後方互換性を確認
  - **確認ポイント**: language="en" 時に英語テンプレートが使用されること
- 🔵 **青信号**: 既存テスト `test_bedrock.py` の TestPrompts クラスと同一のアサーション

```python
# 【テスト目的】: generate.py の英語プロンプト生成が既存 prompts.py と完全互換であることを確認
# 【テスト内容】: get_card_generation_prompt を英語パラメータで呼び出し、出力文字列を検証
# 【期待される動作】: 既存テストと同一のアサーションがすべて通過する
# 🔵 既存テスト test_bedrock.py::test_english_prompt_generation から移植

def test_english_prompt_generation():
    from services.prompts.generate import get_card_generation_prompt
    prompt = get_card_generation_prompt(
        input_text="Test input text",
        card_count=3,
        difficulty="hard",
        language="en",
    )

    # 【検証項目】: 英語テンプレートの専門家フレーズが含まれること
    # 🔵 既存テストと同一
    assert "expert at creating flashcards" in prompt
    # 【検証項目】: カード枚数が正しく埋め込まれること
    # 🔵 既存テストと同一
    assert "3 effective flashcards" in prompt
    # 【検証項目】: 入力テキストが正しく埋め込まれること
    # 🔵 既存テストと同一
    assert "Test input text" in prompt
    # 【検証項目】: 難易度が正しく埋め込まれること
    # 🔵 既存テストと同一
    assert "hard" in prompt
```

### TC-003: generate.py - 全難易度レベル対応（既存互換）

- **テスト名**: 全難易度レベルがプロンプトに含まれること
  - **何をテストするか**: easy/medium/hard の3難易度すべてでプロンプト生成が正常に動作する
  - **期待される動作**: 各難易度名がプロンプト文字列に含まれる
- **入力値**: `difficulty` を "easy", "medium", "hard" で各々実行
  - **入力データの意味**: 全難易度パターンの網羅テスト
- **期待される結果**: 各難易度名がプロンプトに含まれること
  - **期待結果の理由**: `DIFFICULTY_GUIDELINES` 辞書に全難易度が定義されているため
- **テストの目的**: 難易度バリエーションの網羅確認
  - **確認ポイント**: 各 difficulty 値が出力プロンプトに反映されること
- 🔵 **青信号**: 既存テスト `test_bedrock.py::test_difficulty_levels` と同一

```python
# 【テスト目的】: 全難易度レベルでプロンプトが正しく生成されることを確認
# 【テスト内容】: easy/medium/hard の3パターンで get_card_generation_prompt を呼び出す
# 【期待される動作】: 各難易度名がプロンプト文字列に含まれる
# 🔵 既存テスト test_bedrock.py::test_difficulty_levels から移植

def test_difficulty_levels():
    from services.prompts.generate import get_card_generation_prompt
    for difficulty in ["easy", "medium", "hard"]:
        # 【実際の処理実行】: 各難易度でプロンプト生成
        prompt = get_card_generation_prompt(
            input_text="Test",
            card_count=1,
            difficulty=difficulty,
            language="ja",
        )
        # 【検証項目】: 難易度名がプロンプトに含まれること
        # 🔵 既存テストと同一
        assert difficulty in prompt
```

### TC-004: generate.py - エクスポートシンボルの存在確認

- **テスト名**: generate.py のエクスポートシンボルが全て利用可能であること
  - **何をテストするか**: `get_card_generation_prompt`, `DIFFICULTY_GUIDELINES`, `DifficultyLevel`, `Language` が import 可能
  - **期待される動作**: 各シンボルが正しい型で存在する
- **入力値**: なし（import テスト）
  - **入力データの意味**: パッケージ構造の正しさを確認
- **期待される結果**:
  - `get_card_generation_prompt` は callable
  - `DIFFICULTY_GUIDELINES` は dict 型で "easy", "medium", "hard" キーを含む
  - **期待結果の理由**: 既存 `prompts.py` と同じシンボルが generate.py で利用可能であること
- **テストの目的**: モジュール分割後のシンボル可用性確認
  - **確認ポイント**: 既存コードが参照する全シンボルが利用可能であること
- 🔵 **青信号**: 既存 `prompts.py` のシンボル一覧から確定

```python
# 【テスト目的】: generate.py のエクスポートシンボルが全て利用可能であることを確認
# 【テスト内容】: generate.py から各シンボルを import し、型と存在を検証
# 【期待される動作】: 全シンボルが正しい型で存在する
# 🔵 既存 prompts.py のシンボル一覧から確定

def test_generate_exports():
    from services.prompts.generate import (
        get_card_generation_prompt,
        DIFFICULTY_GUIDELINES,
        DifficultyLevel,
        Language,
    )

    # 【検証項目】: get_card_generation_prompt が呼び出し可能であること
    # 🔵 既存 prompts.py の関数
    assert callable(get_card_generation_prompt)

    # 【検証項目】: DIFFICULTY_GUIDELINES が辞書型であること
    # 🔵 既存 prompts.py の定数
    assert isinstance(DIFFICULTY_GUIDELINES, dict)

    # 【検証項目】: 全難易度キーが存在すること
    # 🔵 既存 prompts.py の DIFFICULTY_GUIDELINES と同一
    assert "easy" in DIFFICULTY_GUIDELINES
    assert "medium" in DIFFICULTY_GUIDELINES
    assert "hard" in DIFFICULTY_GUIDELINES
```

### TC-005: grading.py - SM-2 グレード定義の存在

- **テスト名**: SM-2 グレード定義文字列が正しく定義されていること
  - **何をテストするか**: `SM2_GRADE_DEFINITIONS` にグレード 0-5 の全定義が含まれている
  - **期待される動作**: 各グレード番号と説明がテキストに含まれる
- **入力値**: なし（定数値テスト）
  - **入力データの意味**: SM-2 アルゴリズムの核となるグレード定義の完全性
- **期待される結果**:
  - `SM2_GRADE_DEFINITIONS` は str 型
  - "5" "4" "3" "2" "1" "0" の各グレード番号を含む
  - **期待結果の理由**: REQ-SM-003 と api-endpoints.md のグレード定義表に基づく
- **テストの目的**: SM-2 グレード定義の完全性確認
  - **確認ポイント**: 0-5 の全グレードが定義されていること
- 🔵 **青信号**: REQ-SM-003、設計ヒアリング Q4、api-endpoints.md グレード定義表

```python
# 【テスト目的】: SM-2 グレード定義文字列が全グレード (0-5) を含むことを確認
# 【テスト内容】: SM2_GRADE_DEFINITIONS 定数の内容を検証
# 【期待される動作】: 0から5までの全グレードが定義テキストに含まれる
# 🔵 REQ-SM-003、設計ヒアリング Q4 から確定

def test_sm2_grade_definitions_contain_all_grades():
    from services.prompts.grading import SM2_GRADE_DEFINITIONS

    # 【検証項目】: SM2_GRADE_DEFINITIONS が文字列であること
    # 🔵 タスク定義で文字列定数と明記
    assert isinstance(SM2_GRADE_DEFINITIONS, str)

    # 【検証項目】: 全グレード番号 (0-5) が含まれること
    # 🔵 api-endpoints.md グレード定義表と一致
    for grade in range(6):
        assert f"{grade}" in SM2_GRADE_DEFINITIONS, f"グレード {grade} が SM2_GRADE_DEFINITIONS に含まれていない"
```

### TC-006: grading.py - システムプロンプトに SM-2 定義が含まれる

- **テスト名**: GRADING_SYSTEM_PROMPT に SM-2 グレード定義が含まれていること
  - **何をテストするか**: システムプロンプトが SM-2 採点基準を AI に指示する内容であること
  - **期待される動作**: GRADING_SYSTEM_PROMPT 内に SM-2 関連の情報が含まれる
- **入力値**: なし（定数値テスト）
  - **入力データの意味**: AI エージェントに渡すシステムプロンプトの正しさ
- **期待される結果**:
  - `GRADING_SYSTEM_PROMPT` は str 型で非空
  - グレード関連キーワード（"grade" や "SM-2" など）を含む
  - JSON 出力形式の指示を含む（"JSON" または "{" を含む）
  - **期待結果の理由**: AI が正しい採点基準で回答を評価するために必要
- **テストの目的**: システムプロンプトの品質確認
  - **確認ポイント**: SM-2 基準と JSON 出力形式指示の存在
- 🔵 **青信号**: タスクファイルの grading.py 実装仕様に基づく

```python
# 【テスト目的】: GRADING_SYSTEM_PROMPT が SM-2 基準と JSON 出力指示を含むことを確認
# 【テスト内容】: システムプロンプト定数の内容を検証
# 【期待される動作】: SM-2 関連情報と JSON 出力形式指示が含まれる
# 🔵 タスクファイルの grading.py 設計仕様から確定

def test_grading_system_prompt_content():
    from services.prompts.grading import GRADING_SYSTEM_PROMPT

    # 【検証項目】: 文字列型で非空であること
    # 🔵 基本チェック
    assert isinstance(GRADING_SYSTEM_PROMPT, str)
    assert len(GRADING_SYSTEM_PROMPT) > 0

    # 【検証項目】: グレード関連キーワードが含まれること
    # 🔵 SM-2 基準を AI に指示するために必要
    prompt_lower = GRADING_SYSTEM_PROMPT.lower()
    assert "grade" in prompt_lower or "sm-2" in prompt_lower

    # 【検証項目】: JSON 出力形式の指示が含まれること
    # 🔵 API レスポンス形式 (api-endpoints.md) に合わせた出力指示
    assert "JSON" in GRADING_SYSTEM_PROMPT or "json" in GRADING_SYSTEM_PROMPT or "{" in GRADING_SYSTEM_PROMPT
```

### TC-007: grading.py - 日本語採点プロンプト生成

- **テスト名**: 日本語での回答採点プロンプトが正しく生成されること
  - **何をテストするか**: `get_grading_prompt()` が card_front, card_back, user_answer を含むプロンプトを生成する
  - **期待される動作**: 3つの入力値と日本語指示がプロンプトに埋め込まれる
- **入力値**: `card_front="日本の首都は？"`, `card_back="東京"`, `user_answer="東京です"`, `language="ja"`
  - **入力データの意味**: 典型的な日本語フラッシュカードの採点シナリオ
- **期待される結果**:
  - 戻り値は str 型
  - `"日本の首都は？"` を含む
  - `"東京"` を含む
  - `"東京です"` を含む
  - `"Japanese"` または `"日本語"` を含む（日本語応答指示）
  - **期待結果の理由**: AI が問題・正解・回答の3要素を把握して採点するために必要
- **テストの目的**: 採点プロンプトの基本構造確認
  - **確認ポイント**: 3つの入力要素と言語指示が正しく埋め込まれること
- 🔵 **青信号**: タスクファイルの `get_grading_prompt` 仕様および要件定義書 2.2 節

```python
# 【テスト目的】: 日本語設定で採点プロンプトが正しく生成されることを確認
# 【テスト内容】: get_grading_prompt を日本語パラメータで呼び出し、出力を検証
# 【期待される動作】: card_front, card_back, user_answer, 言語指示がプロンプトに含まれる
# 🔵 タスクファイルの grading.py 仕様と要件定義書 2.2 節から確定

def test_get_grading_prompt_japanese():
    from services.prompts.grading import get_grading_prompt

    # 【テストデータ準備】: 典型的な日本語フラッシュカードのデータ
    prompt = get_grading_prompt(
        card_front="日本の首都は？",
        card_back="東京",
        user_answer="東京です",
        language="ja",
    )

    # 【検証項目】: 戻り値が文字列であること
    # 🔵 基本型チェック
    assert isinstance(prompt, str)
    # 【検証項目】: 問題文が含まれること
    # 🔵 AI が採点対象を認識するために必要
    assert "日本の首都は？" in prompt
    # 【検証項目】: 正解が含まれること
    # 🔵 AI が正解を参照して採点するために必要
    assert "東京" in prompt
    # 【検証項目】: ユーザー回答が含まれること
    # 🔵 AI が採点対象の回答を認識するために必要
    assert "東京です" in prompt
    # 【検証項目】: 日本語応答指示が含まれること
    # 🔵 language="ja" 時の言語指示
    assert "Japanese" in prompt or "日本語" in prompt
```

### TC-008: grading.py - 英語採点プロンプト生成

- **テスト名**: 英語での回答採点プロンプトが正しく生成されること
  - **何をテストするか**: language="en" 時に英語応答指示が含まれること
  - **期待される動作**: 入力値が埋め込まれ、英語応答指示が含まれる
- **入力値**: `card_front="What is the capital of France?"`, `card_back="Paris"`, `user_answer="Paris"`, `language="en"`
  - **入力データの意味**: 英語フラッシュカードでの完全正解ケース
- **期待される結果**:
  - 戻り値は str 型
  - `"English"` を含む（英語応答指示）
  - 入力値が全て含まれる
  - **期待結果の理由**: language パラメータに応じた言語指示の切り替え確認
- **テストの目的**: 言語切り替え機能の確認
  - **確認ポイント**: language="en" で英語指示が生成されること
- 🔵 **青信号**: タスクファイルの `get_grading_prompt` 実装仕様

```python
# 【テスト目的】: 英語設定で採点プロンプトが正しく生成されることを確認
# 【テスト内容】: get_grading_prompt を英語パラメータで呼び出し、言語指示を検証
# 【期待される動作】: "English" 応答指示がプロンプトに含まれる
# 🔵 タスクファイルの grading.py 仕様から確定

def test_get_grading_prompt_english():
    from services.prompts.grading import get_grading_prompt

    prompt = get_grading_prompt(
        card_front="What is the capital of France?",
        card_back="Paris",
        user_answer="Paris",
        language="en",
    )

    # 【検証項目】: 英語応答指示が含まれること
    # 🔵 language="en" 時の言語指示
    assert "English" in prompt
    # 【検証項目】: 入力値が含まれること
    # 🔵 基本的な埋め込み確認
    assert "What is the capital of France?" in prompt
    assert "Paris" in prompt
```

### TC-009: advice.py - システムプロンプトの存在

- **テスト名**: ADVICE_SYSTEM_PROMPT が正しく定義されていること
  - **何をテストするか**: 学習アドバイス用システムプロンプトが存在し、非空であること
  - **期待される動作**: JSON 出力形式指示とアドバイス関連キーワードを含む
- **入力値**: なし（定数値テスト）
  - **入力データの意味**: AI に学習アドバイス生成を指示するシステムプロンプト
- **期待される結果**:
  - `ADVICE_SYSTEM_PROMPT` は str 型で非空
  - JSON 出力形式の指示を含む
  - **期待結果の理由**: AI が構造化されたアドバイスを生成するために必要
- **テストの目的**: アドバイス用システムプロンプトの品質確認
  - **確認ポイント**: 必要な指示が含まれていること
- 🔵 **青信号**: タスクファイルの advice.py 実装仕様、REQ-SM-004

```python
# 【テスト目的】: ADVICE_SYSTEM_PROMPT が存在し、必要な内容を含むことを確認
# 【テスト内容】: システムプロンプト定数の型と内容を検証
# 【期待される動作】: 非空文字列で JSON 出力形式指示を含む
# 🔵 タスクファイルの advice.py 仕様、REQ-SM-004 から確定

def test_advice_system_prompt_exists():
    from services.prompts.advice import ADVICE_SYSTEM_PROMPT

    # 【検証項目】: 文字列型で非空であること
    # 🔵 基本チェック
    assert isinstance(ADVICE_SYSTEM_PROMPT, str)
    assert len(ADVICE_SYSTEM_PROMPT) > 0

    # 【検証項目】: JSON 出力形式の指示が含まれること
    # 🔵 API レスポンス形式 (api-endpoints.md) に合わせた出力指示
    assert "JSON" in ADVICE_SYSTEM_PROMPT or "json" in ADVICE_SYSTEM_PROMPT or "{" in ADVICE_SYSTEM_PROMPT
```

### TC-010: advice.py - 辞書形式の統計データでプロンプト生成

- **テスト名**: 辞書形式の復習統計でプロンプトが正しく生成されること
  - **何をテストするか**: `get_advice_prompt()` が dict 型の review_summary を受け取り、統計データをプロンプトに埋め込む
  - **期待される動作**: 統計値がプロンプト文字列内に反映される
- **入力値**:
  ```python
  review_summary = {
      "total_reviews": 100,
      "average_grade": 3.5,
      "total_cards": 50,
      "cards_due_today": 10,
      "streak_days": 7,
      "tag_performance": {"noun": 3.8, "verb": 3.2}
  }
  language = "ja"
  ```
  - **入力データの意味**: 典型的な学習統計データ（dict形式）
- **期待される結果**:
  - 戻り値は str 型
  - `"100"` を含む（total_reviews）
  - `"3.5"` を含む（average_grade）
  - **期待結果の理由**: AI が統計データに基づいたアドバイスを生成するために必要な情報が埋め込まれること
- **テストの目的**: dict 入力でのプロンプト生成確認
  - **確認ポイント**: 主要な統計値がプロンプトに反映されること
- 🔵 **青信号**: タスクファイルの advice.py 仕様、設計ヒアリング Q5

```python
# 【テスト目的】: dict 形式の復習統計データからプロンプトが正しく生成されることを確認
# 【テスト内容】: get_advice_prompt を dict 形式の統計データで呼び出し、出力を検証
# 【期待される動作】: 統計値がプロンプト文字列に埋め込まれる
# 🔵 タスクファイルの advice.py 仕様、設計ヒアリング Q5 から確定

def test_get_advice_prompt_with_dict():
    from services.prompts.advice import get_advice_prompt

    # 【テストデータ準備】: 典型的な学習統計データ（dict 形式）
    review_stats = {
        "total_reviews": 100,
        "average_grade": 3.5,
        "total_cards": 50,
        "cards_due_today": 10,
        "streak_days": 7,
        "tag_performance": {"noun": 3.8, "verb": 3.2},
    }

    # 【実際の処理実行】: dict 形式の統計でプロンプト生成
    prompt = get_advice_prompt(review_stats, language="ja")

    # 【検証項目】: 戻り値が文字列であること
    # 🔵 基本型チェック
    assert isinstance(prompt, str)
    # 【検証項目】: total_reviews が埋め込まれること
    # 🔵 統計データの主要指標
    assert "100" in prompt
    # 【検証項目】: average_grade が埋め込まれること
    # 🔵 統計データの主要指標
    assert "3.5" in prompt
```

### TC-011: advice.py - ReviewSummary dataclass でプロンプト生成

- **テスト名**: ReviewSummary dataclass 形式の統計データでプロンプトが正しく生成されること
  - **何をテストするか**: `get_advice_prompt()` が ReviewSummary dataclass も受け取れること
  - **期待される動作**: dataclass のフィールド値がプロンプト文字列に埋め込まれる
- **入力値**: `ReviewSummary(total_reviews=100, average_grade=3.5, ...)`, `language="en"`
  - **入力データの意味**: TASK-0053 で定義された ReviewSummary dataclass による入力
- **期待される結果**:
  - 戻り値は str 型
  - `"100"` を含む（total_reviews）
  - `"English"` を含む（英語応答指示）
  - **期待結果の理由**: dict と ReviewSummary の両方をサポートするポリモーフィック設計
- **テストの目的**: ReviewSummary dataclass 対応の確認
  - **確認ポイント**: dataclass の `__dict__` 属性を利用して値を抽出できること
- 🔵 **青信号**: タスクファイルの advice.py 仕様、interfaces.py ReviewSummary 定義

```python
# 【テスト目的】: ReviewSummary dataclass でプロンプトが正しく生成されることを確認
# 【テスト内容】: get_advice_prompt を ReviewSummary インスタンスで呼び出し、出力を検証
# 【期待される動作】: dataclass のフィールド値がプロンプトに反映される
# 🔵 タスクファイルの advice.py 仕様、interfaces.py ReviewSummary 定義から確定

def test_get_advice_prompt_with_review_summary():
    from services.prompts.advice import get_advice_prompt
    from services.ai_service import ReviewSummary

    # 【テストデータ準備】: ReviewSummary dataclass を使用
    summary = ReviewSummary(
        total_reviews=100,
        average_grade=3.5,
        total_cards=50,
        cards_due_today=10,
        streak_days=7,
        tag_performance={"noun": 3.8, "verb": 3.2},
        recent_review_dates=["2026-02-20"],
    )

    # 【実際の処理実行】: ReviewSummary で英語プロンプト生成
    prompt = get_advice_prompt(summary, language="en")

    # 【検証項目】: 戻り値が文字列であること
    # 🔵 基本型チェック
    assert isinstance(prompt, str)
    # 【検証項目】: total_reviews が埋め込まれること
    # 🔵 dataclass フィールドの値が反映されること
    assert "100" in prompt
    # 【検証項目】: 英語応答指示が含まれること
    # 🔵 language="en" 時の言語指示
    assert "English" in prompt
```

### TC-012: __init__.py - パッケージ経由の import 互換性

- **テスト名**: services.prompts パッケージ経由で全シンボルが import 可能であること
  - **何をテストするか**: `from services.prompts import ...` で全エクスポートシンボルが利用可能
  - **期待される動作**: `__init__.py` による再エクスポートが正しく動作する
- **入力値**: なし（import テスト）
  - **入力データの意味**: 既存 `from services.prompts import get_card_generation_prompt` の互換性維持
- **期待される結果**:
  - 全シンボルが import エラーなく利用可能
  - **期待結果の理由**: `__init__.py` の `__all__` と再エクスポートにより後方互換性を維持
- **テストの目的**: パッケージ構造の後方互換性確認
  - **確認ポイント**: 特に `test_bedrock.py` の既存 import パスが動作すること
- 🔵 **青信号**: 要件定義書 2.4 節、タスクファイルの __init__.py 仕様

```python
# 【テスト目的】: services.prompts パッケージ経由の import 互換性を確認
# 【テスト内容】: __init__.py から全シンボルを import し、存在を確認
# 【期待される動作】: 全シンボルが import エラーなく利用可能
# 🔵 要件定義書 2.4 節、互換性要件 REQ-SM-402 から確定

def test_package_imports():
    # 【実際の処理実行】: パッケージレベルの import
    from services.prompts import (
        # generate.py
        get_card_generation_prompt,
        DIFFICULTY_GUIDELINES,
        # grading.py
        get_grading_prompt,
        GRADING_SYSTEM_PROMPT,
        SM2_GRADE_DEFINITIONS,
        # advice.py
        get_advice_prompt,
        ADVICE_SYSTEM_PROMPT,
    )

    # 【検証項目】: 全シンボルが callable または適切な型であること
    # 🔵 パッケージ構造の整合性確認
    assert callable(get_card_generation_prompt)
    assert callable(get_grading_prompt)
    assert callable(get_advice_prompt)
    assert isinstance(DIFFICULTY_GUIDELINES, dict)
    assert isinstance(GRADING_SYSTEM_PROMPT, str)
    assert isinstance(SM2_GRADE_DEFINITIONS, str)
    assert isinstance(ADVICE_SYSTEM_PROMPT, str)
```

### TC-013: advice.py - プロンプトに弱点分析の指示が含まれる

- **テスト名**: プロンプトが弱点分野への焦点指示を含むこと
  - **何をテストするか**: 生成されたプロンプトに学習改善に関する指示が含まれていること
  - **期待される動作**: "struggling", "weak", "improve" などのキーワードが含まれる
- **入力値**: `review_summary` に低い平均グレード (2.0) を設定
  - **入力データの意味**: 成績が低い学生に対するアドバイス生成シナリオ
- **期待される結果**:
  - プロンプトに改善指示のキーワードが含まれること
  - **期待結果の理由**: タスクファイルの advice.py テンプレートに "struggling" が含まれている
- **テストの目的**: プロンプトテンプレートの内容品質確認
  - **確認ポイント**: AI に適切な指示が与えられること
- 🔵 **青信号**: タスクファイルの `get_advice_prompt` テンプレート内容

```python
# 【テスト目的】: プロンプトが弱点分析の指示を含むことを確認
# 【テスト内容】: 低い平均グレードの統計でプロンプトを生成し、改善指示キーワードを検証
# 【期待される動作】: "struggling", "weak", "improve" のいずれかが含まれる
# 🔵 タスクファイルの advice.py テンプレート内容から確定

def test_get_advice_prompt_contains_improvement_focus():
    from services.prompts.advice import get_advice_prompt

    stats = {
        "total_reviews": 50,
        "average_grade": 2.0,
        "total_cards": 25,
        "cards_due_today": 8,
        "streak_days": 2,
        "tag_performance": {"weak_area": 1.5},
    }

    prompt = get_advice_prompt(stats)

    # 【検証項目】: 改善指示のキーワードが含まれること
    # 🔵 タスクファイルのテンプレートに "struggling" が含まれている
    prompt_lower = prompt.lower()
    assert "struggling" in prompt_lower or "weak" in prompt_lower or "improve" in prompt_lower
```

---

## 2. 異常系テストケース（エラーハンドリング）

### TC-014: grading.py - language フォールバック（未知の言語値）

- **テスト名**: 未知の language 値で日本語にフォールバックすること
  - **エラーケースの概要**: サポート外の言語コードが渡された場合の安全なフォールバック
  - **エラー処理の重要性**: ランタイムエラーを防ぎ、安全なデフォルト動作を保証
- **入力値**: `language="fr"` (フランス語、サポート外)
  - **不正な理由**: `Language = Literal["ja", "en"]` に "fr" は含まれない
  - **実際の発生シナリオ**: API パラメータバリデーションの前段で直接呼ばれた場合
- **期待される結果**:
  - エラーが発生しない（例外なし）
  - `"Japanese"` にフォールバックする
  - **エラーメッセージの内容**: N/A（エラーなし）
  - **システムの安全性**: デフォルト言語で正常動作する
- **テストの目的**: 言語フォールバックの安全性確認
  - **品質保証の観点**: 予期しない入力値でもシステムが安全に動作すること
- 🟡 **黄信号**: 要件定義書 4.7 節のエッジケースから妥当な推測。タスクファイルの実装仕様では `.get(language, "Respond in Japanese.")` で実装されている

```python
# 【テスト目的】: 未知の language 値で例外が発生せずフォールバックすることを確認
# 【テスト内容】: language="fr" で get_grading_prompt を呼び出し、フォールバック動作を検証
# 【期待される動作】: エラーなしで日本語フォールバックが適用される
# 🟡 要件定義書 4.7 節、タスクファイルの .get() フォールバック仕様から推測

def test_grading_prompt_language_fallback():
    from services.prompts.grading import get_grading_prompt

    # 【テストデータ準備】: サポート外の言語コード
    # 【前提条件確認】: Language 型は Literal["ja", "en"] だが、ランタイムでは型強制なし
    prompt = get_grading_prompt(
        card_front="Q",
        card_back="A",
        user_answer="A",
        language="fr",
    )

    # 【検証項目】: エラーなしでプロンプトが生成されること
    # 🟡 ランタイムでの型チェックなし前提の推測
    assert isinstance(prompt, str)
    # 【検証項目】: 日本語フォールバックが適用されること
    # 🟡 タスクファイルの .get() 実装から推測
    assert "Japanese" in prompt
```

### TC-015: advice.py - language フォールバック（未知の言語値）

- **テスト名**: advice.py で未知の language 値で日本語にフォールバックすること
  - **エラーケースの概要**: grading.py と同様の言語フォールバック動作
  - **エラー処理の重要性**: advice.py でも同じ安全なデフォルト動作を保証
- **入力値**: `language="de"` (ドイツ語、サポート外)
  - **不正な理由**: Language 型のサポート外
  - **実際の発生シナリオ**: grading.py と同様
- **期待される結果**:
  - エラーが発生しない
  - `"Japanese"` にフォールバックする
  - **システムの安全性**: デフォルト言語で正常動作
- **テストの目的**: advice.py の言語フォールバック確認
  - **品質保証の観点**: 両モジュールで一貫したフォールバック動作
- 🟡 **黄信号**: 要件定義書 4.7 節から推測。grading.py と同じフォールバックパターン

```python
# 【テスト目的】: advice.py で未知の language 値のフォールバック動作を確認
# 【テスト内容】: language="de" で get_advice_prompt を呼び出し、フォールバックを検証
# 【期待される動作】: 日本語フォールバックが適用される
# 🟡 要件定義書 4.7 節から推測

def test_advice_prompt_language_fallback():
    from services.prompts.advice import get_advice_prompt

    stats = {
        "total_reviews": 10,
        "average_grade": 3.0,
        "total_cards": 5,
        "cards_due_today": 2,
        "streak_days": 1,
        "tag_performance": {},
    }

    prompt = get_advice_prompt(stats, language="de")

    # 【検証項目】: エラーなしでプロンプトが生成されること
    # 🟡 ランタイムでの型チェックなし前提の推測
    assert isinstance(prompt, str)
    # 【検証項目】: 日本語フォールバックが適用されること
    # 🟡 タスクファイルの .get() 実装から推測
    assert "Japanese" in prompt
```

---

## 3. 境界値テストケース（最小値、最大値、null等）

### TC-016: grading.py - デフォルト language 値

- **テスト名**: language パラメータ省略時にデフォルト "ja" が適用されること
  - **境界値の意味**: オプショナルパラメータのデフォルト値動作
  - **境界値での動作保証**: パラメータ省略時の一貫した動作
- **入力値**: `card_front="Q"`, `card_back="A"`, `user_answer="A"` (language 省略)
  - **境界値選択の根拠**: 関数シグネチャの `language: Language = "ja"` デフォルト値テスト
  - **実際の使用場面**: API から language パラメータが省略された場合
- **期待される結果**:
  - エラーなしでプロンプトが生成される
  - `"Japanese"` が含まれる（デフォルト "ja"）
  - **境界での正確性**: デフォルト値が正しく適用されること
  - **一貫した動作**: 明示的に `language="ja"` を渡した場合と同じ結果
- **テストの目的**: デフォルト値の動作確認
  - **堅牢性の確認**: パラメータ省略時の安全な動作
- 🔵 **青信号**: タスクファイルのシグネチャ定義、要件定義書 4.4 節

```python
# 【テスト目的】: language 省略時にデフォルト値 "ja" が適用されることを確認
# 【テスト内容】: language パラメータなしで get_grading_prompt を呼び出す
# 【期待される動作】: 日本語指示がプロンプトに含まれる
# 🔵 タスクファイルのシグネチャ定義、要件定義書 4.4 節から確定

def test_grading_prompt_default_language():
    from services.prompts.grading import get_grading_prompt

    # 【実際の処理実行】: language パラメータを省略
    prompt = get_grading_prompt(
        card_front="Q",
        card_back="A",
        user_answer="A",
    )

    # 【検証項目】: エラーなしでプロンプトが生成されること
    # 🔵 デフォルト値テスト
    assert isinstance(prompt, str)
    # 【検証項目】: 日本語指示が含まれること（デフォルト "ja"）
    # 🔵 シグネチャの language="ja" デフォルト
    assert "Japanese" in prompt
```

### TC-017: advice.py - デフォルト language 値

- **テスト名**: advice.py で language パラメータ省略時にデフォルト "ja" が適用されること
  - **境界値の意味**: grading.py と同様のデフォルト値動作
  - **境界値での動作保証**: 両モジュールで一貫したデフォルト動作
- **入力値**: `review_summary` (最低限のデータ), language 省略
  - **境界値選択の根拠**: advice.py のシグネチャ `language: Language = "ja"` テスト
  - **実際の使用場面**: API から language パラメータが省略された場合
- **期待される結果**:
  - エラーなしでプロンプトが生成される
  - `"Japanese"` が含まれる
  - **一貫した動作**: 明示的に `language="ja"` を渡した場合と同じ結果
- **テストの目的**: advice.py のデフォルト値確認
  - **堅牢性の確認**: パラメータ省略時の安全な動作
- 🔵 **青信号**: タスクファイルのシグネチャ定義

```python
# 【テスト目的】: advice.py で language 省略時にデフォルト "ja" が適用されることを確認
# 【テスト内容】: language なしで get_advice_prompt を呼び出す
# 【期待される動作】: 日本語指示がプロンプトに含まれる
# 🔵 タスクファイルのシグネチャ定義から確定

def test_advice_prompt_default_language():
    from services.prompts.advice import get_advice_prompt

    stats = {
        "total_reviews": 10,
        "average_grade": 3.0,
        "total_cards": 5,
        "cards_due_today": 2,
        "streak_days": 1,
        "tag_performance": {},
    }

    # 【実際の処理実行】: language パラメータを省略
    prompt = get_advice_prompt(stats)

    # 【検証項目】: 日本語指示が含まれること（デフォルト "ja"）
    # 🔵 シグネチャの language="ja" デフォルト
    assert isinstance(prompt, str)
    assert "Japanese" in prompt
```

### TC-018: advice.py - 空の tag_performance

- **テスト名**: tag_performance が空辞書でもプロンプトが正常に生成されること
  - **境界値の意味**: コレクション型フィールドの空状態
  - **境界値での動作保証**: データが存在しない初期段階の学習者でも動作する
- **入力値**: `tag_performance: {}`（空辞書）
  - **境界値選択の根拠**: 新規ユーザーはまだタグ別の学習履歴がない
  - **実際の使用場面**: 学習を始めたばかりのユーザーに対するアドバイス生成
- **期待される結果**:
  - エラーなしでプロンプトが生成される
  - `"{}"` または空の表現がプロンプトに含まれる
  - **境界での正確性**: 空辞書の文字列表現が正しく埋め込まれること
  - **一貫した動作**: データ有無に関わらずプロンプト生成が成功すること
- **テストの目的**: 空データでの堅牢性確認
  - **堅牢性の確認**: 初期状態のユーザーデータでもシステムが安定動作する
- 🟡 **黄信号**: 要件定義書 4.6 節のエッジケースから推測。設計文書に明記なし

```python
# 【テスト目的】: 空の tag_performance でプロンプトが正常に生成されることを確認
# 【テスト内容】: tag_performance を空辞書にしてプロンプト生成を実行
# 【期待される動作】: エラーなしでプロンプトが生成される
# 🟡 要件定義書 4.6 節のエッジケースから推測

def test_advice_prompt_empty_tag_performance():
    from services.prompts.advice import get_advice_prompt

    # 【テストデータ準備】: 新規ユーザーを想定した最小限データ
    stats = {
        "total_reviews": 0,
        "average_grade": 0.0,
        "total_cards": 0,
        "cards_due_today": 0,
        "streak_days": 0,
        "tag_performance": {},
    }

    # 【実際の処理実行】: 空の tag_performance でプロンプト生成
    prompt = get_advice_prompt(stats)

    # 【検証項目】: エラーなしで文字列が生成されること
    # 🟡 空データでの堅牢性は設計文書に明記なし
    assert isinstance(prompt, str)
    assert len(prompt) > 0
```

### TC-019: advice.py - ゼロ値の統計データ

- **テスト名**: 全ての統計値がゼロでもプロンプトが正常に生成されること
  - **境界値の意味**: 数値フィールドの最小値（ゼロ）
  - **境界値での動作保証**: 学習未開始の状態でもシステムが動作する
- **入力値**: 全数値を 0 に設定
  - **境界値選択の根拠**: `average_grade` は `{stats.get('average_grade', 0):.1f}` でフォーマットされるため、0.0 の表示確認
  - **実際の使用場面**: 新規ユーザーが学習アドバイス画面を初めて開いた場合
- **期待される結果**:
  - エラーなしでプロンプトが生成される
  - `"0"` がプロンプトに含まれる（ゼロ値の表現）
  - `"0.0"` がプロンプトに含まれる（average_grade のフォーマット）
  - **境界での正確性**: `:.1f` フォーマットで 0 が "0.0" として表示されること
- **テストの目的**: ゼロ値境界での動作確認
  - **堅牢性の確認**: 除算エラー等が発生しないこと
- 🟡 **黄信号**: 要件定義書のエッジケースから推測。`:.1f` フォーマットはタスクファイルの実装仕様

```python
# 【テスト目的】: 全ゼロ統計データでプロンプトが正常に生成されることを確認
# 【テスト内容】: 全数値をゼロに設定してプロンプト生成を実行
# 【期待される動作】: ゼロ値が正しくフォーマットされ、エラーなしで生成される
# 🟡 要件定義書のエッジケースとタスクファイルの実装仕様から推測

def test_advice_prompt_zero_stats():
    from services.prompts.advice import get_advice_prompt

    # 【テストデータ準備】: 全ゼロの統計データ（学習未開始ユーザー）
    stats = {
        "total_reviews": 0,
        "average_grade": 0.0,
        "total_cards": 0,
        "cards_due_today": 0,
        "streak_days": 0,
        "tag_performance": {},
    }

    prompt = get_advice_prompt(stats)

    # 【検証項目】: プロンプトが生成されること
    # 🟡 ゼロ値での堅牢性
    assert isinstance(prompt, str)
    # 【検証項目】: average_grade が "0.0" としてフォーマットされること
    # 🟡 タスクファイルの :.1f フォーマット仕様から推測
    assert "0.0" in prompt
```

### TC-020: generate.py - __init__.py 経由の既存 import パス互換性

- **テスト名**: 既存の `from services.prompts import get_card_generation_prompt` が動作すること
  - **境界値の意味**: ファイルからパッケージへの変更時の import 互換性の境界
  - **境界値での動作保証**: `prompts.py` が `prompts/` に変わっても既存コードが動作する
- **入力値**: なし（import + 関数呼び出しテスト）
  - **境界値選択の根拠**: `test_bedrock.py:16` の既存 import パスがそのまま動作すること
  - **実際の使用場面**: 既存のテストコードと本番コードの後方互換性
- **期待される結果**:
  - `from services.prompts import get_card_generation_prompt` が ImportError なく成功
  - 呼び出し結果が `services.prompts.generate` からの直接 import と同一
  - **境界での正確性**: `__init__.py` のエクスポートが正しく動作すること
  - **一貫した動作**: 直接 import とパッケージ経由 import が同じオブジェクトを参照すること
- **テストの目的**: 後方互換性の保証
  - **堅牢性の確認**: import パスの変更がユーザーコードに影響しないこと
- 🔵 **青信号**: 要件定義書 3 節 互換性要件、REQ-SM-402

```python
# 【テスト目的】: 既存の import パスが __init__.py 経由で動作することを確認
# 【テスト内容】: パッケージ経由と直接 import の両方でシンボルを取得し、同一性を検証
# 【期待される動作】: 両方の import パスが同じオブジェクトを参照する
# 🔵 要件定義書 3 節 互換性要件、REQ-SM-402 から確定

def test_backward_compatible_import():
    # 【実際の処理実行】: 2つの import パスでシンボルを取得
    from services.prompts import get_card_generation_prompt as from_package
    from services.prompts.generate import get_card_generation_prompt as from_module

    # 【検証項目】: 両方の import パスが同じオブジェクトを参照すること
    # 🔵 __init__.py の再エクスポートにより保証
    assert from_package is from_module

    # 【検証項目】: パッケージ経由で生成したプロンプトが正しいこと
    # 🔵 既存互換性の実用テスト
    prompt = from_package(
        input_text="テスト",
        card_count=1,
        difficulty="easy",
        language="ja",
    )
    assert isinstance(prompt, str)
    assert len(prompt) > 0
```

### TC-021: grading.py - grading エクスポートシンボルの型確認

- **テスト名**: grading.py のエクスポートシンボルが全て正しい型であること
  - **境界値の意味**: 新規モジュールのシンボルの型整合性
  - **境界値での動作保証**: 後続タスク (TASK-0057) が依存するシンボルの正しさ
- **入力値**: なし（import + 型チェックテスト）
  - **境界値選択の根拠**: grading.py の全エクスポートシンボルの型確認
  - **実際の使用場面**: TASK-0057 の StrandsAIService が grading.py のシンボルを使用する
- **期待される結果**:
  - `get_grading_prompt` は callable
  - `GRADING_SYSTEM_PROMPT` は str 型で非空
  - `SM2_GRADE_DEFINITIONS` は str 型で非空
  - **境界での正確性**: 全シンボルが期待される型であること
- **テストの目的**: 新規モジュールのシンボル整合性確認
  - **堅牢性の確認**: 後続タスクが安全にこのモジュールを使用できること
- 🔵 **青信号**: タスクファイル 2 節、要件定義書 2.2 節

```python
# 【テスト目的】: grading.py の全エクスポートシンボルが正しい型であることを確認
# 【テスト内容】: grading.py から全シンボルを import し、型を検証
# 【期待される動作】: callable と str 型が正しく設定されている
# 🔵 タスクファイル 2 節、要件定義書 2.2 節から確定

def test_grading_exports():
    from services.prompts.grading import (
        get_grading_prompt,
        GRADING_SYSTEM_PROMPT,
        SM2_GRADE_DEFINITIONS,
    )

    # 【検証項目】: get_grading_prompt が呼び出し可能であること
    # 🔵 関数エクスポート
    assert callable(get_grading_prompt)

    # 【検証項目】: GRADING_SYSTEM_PROMPT が非空文字列であること
    # 🔵 定数エクスポート
    assert isinstance(GRADING_SYSTEM_PROMPT, str)
    assert len(GRADING_SYSTEM_PROMPT) > 0

    # 【検証項目】: SM2_GRADE_DEFINITIONS が非空文字列であること
    # 🔵 定数エクスポート
    assert isinstance(SM2_GRADE_DEFINITIONS, str)
    assert len(SM2_GRADE_DEFINITIONS) > 0
```

### TC-022: advice.py - advice エクスポートシンボルの型確認

- **テスト名**: advice.py のエクスポートシンボルが全て正しい型であること
  - **境界値の意味**: 新規モジュールのシンボルの型整合性
  - **境界値での動作保証**: 後続タスク (TASK-0059) が依存するシンボルの正しさ
- **入力値**: なし（import + 型チェックテスト）
  - **境界値選択の根拠**: advice.py の全エクスポートシンボルの型確認
  - **実際の使用場面**: TASK-0059 の StrandsAIService が advice.py のシンボルを使用する
- **期待される結果**:
  - `get_advice_prompt` は callable
  - `ADVICE_SYSTEM_PROMPT` は str 型で非空
  - **境界での正確性**: 全シンボルが期待される型であること
- **テストの目的**: 新規モジュールのシンボル整合性確認
  - **堅牢性の確認**: 後続タスクが安全にこのモジュールを使用できること
- 🔵 **青信号**: タスクファイル 5 節、要件定義書 2.3 節

```python
# 【テスト目的】: advice.py の全エクスポートシンボルが正しい型であることを確認
# 【テスト内容】: advice.py から全シンボルを import し、型を検証
# 【期待される動作】: callable と str 型が正しく設定されている
# 🔵 タスクファイル 5 節、要件定義書 2.3 節から確定

def test_advice_exports():
    from services.prompts.advice import (
        get_advice_prompt,
        ADVICE_SYSTEM_PROMPT,
    )

    # 【検証項目】: get_advice_prompt が呼び出し可能であること
    # 🔵 関数エクスポート
    assert callable(get_advice_prompt)

    # 【検証項目】: ADVICE_SYSTEM_PROMPT が非空文字列であること
    # 🔵 定数エクスポート
    assert isinstance(ADVICE_SYSTEM_PROMPT, str)
    assert len(ADVICE_SYSTEM_PROMPT) > 0
```

### TC-023: grading.py - GRADING_SYSTEM_PROMPT に JSON レスポンス形式が指示されている

- **テスト名**: GRADING_SYSTEM_PROMPT が JSON レスポンス形式（grade, reasoning, feedback）を指示すること
  - **境界値の意味**: AI が構造化レスポンスを返すために必要な指示の完全性
  - **境界値での動作保証**: AI レスポンスのパース可能性を保証
- **入力値**: なし（定数値テスト）
  - **境界値選択の根拠**: api-endpoints.md GradeAnswerResponse 仕様
  - **実際の使用場面**: TASK-0057 の grade_answer で AI レスポンスをパースする際
- **期待される結果**:
  - `"grade"` がシステムプロンプトに含まれる
  - `"reasoning"` がシステムプロンプトに含まれる
  - `"feedback"` がシステムプロンプトに含まれる
  - **境界での正確性**: レスポンスフィールド名が正確に指示されること
- **テストの目的**: JSON レスポンス指示の完全性確認
  - **堅牢性の確認**: AI レスポンスが期待どおりのフィールドを含むこと
- 🔵 **青信号**: タスクファイルの GRADING_SYSTEM_PROMPT 実装仕様、api-endpoints.md

```python
# 【テスト目的】: GRADING_SYSTEM_PROMPT に JSON レスポンスフィールド名が含まれることを確認
# 【テスト内容】: システムプロンプトに grade, reasoning, feedback の各フィールドが指示されているか検証
# 【期待される動作】: 3つのフィールド名が全て含まれる
# 🔵 タスクファイルの GRADING_SYSTEM_PROMPT、api-endpoints.md GradeAnswerResponse

def test_grading_system_prompt_json_fields():
    from services.prompts.grading import GRADING_SYSTEM_PROMPT

    # 【検証項目】: "grade" フィールドが指示されていること
    # 🔵 api-endpoints.md の GradeAnswerResponse 仕様
    assert "grade" in GRADING_SYSTEM_PROMPT.lower()

    # 【検証項目】: "reasoning" フィールドが指示されていること
    # 🔵 api-endpoints.md の GradeAnswerResponse 仕様
    assert "reasoning" in GRADING_SYSTEM_PROMPT.lower()

    # 【検証項目】: "feedback" フィールドが指示されていること
    # 🔵 api-endpoints.md の GradeAnswerResponse 仕様
    assert "feedback" in GRADING_SYSTEM_PROMPT.lower()
```

### TC-024: advice.py - ADVICE_SYSTEM_PROMPT に JSON レスポンス形式が指示されている

- **テスト名**: ADVICE_SYSTEM_PROMPT が JSON レスポンス形式（advice_text, weak_areas, recommendations）を指示すること
  - **境界値の意味**: AI が構造化レスポンスを返すために必要な指示の完全性
  - **境界値での動作保証**: AI レスポンスのパース可能性を保証
- **入力値**: なし（定数値テスト）
  - **境界値選択の根拠**: api-endpoints.md LearningAdviceResponse 仕様
  - **実際の使用場面**: TASK-0059 の get_learning_advice で AI レスポンスをパースする際
- **期待される結果**:
  - `"advice_text"` がシステムプロンプトに含まれる
  - `"weak_areas"` がシステムプロンプトに含まれる
  - `"recommendations"` がシステムプロンプトに含まれる
  - **境界での正確性**: レスポンスフィールド名が正確に指示されること
- **テストの目的**: JSON レスポンス指示の完全性確認
  - **堅牢性の確認**: AI レスポンスが期待どおりのフィールドを含むこと
- 🔵 **青信号**: タスクファイルの ADVICE_SYSTEM_PROMPT 実装仕様、api-endpoints.md

```python
# 【テスト目的】: ADVICE_SYSTEM_PROMPT に JSON レスポンスフィールド名が含まれることを確認
# 【テスト内容】: システムプロンプトに advice_text, weak_areas, recommendations が指示されているか検証
# 【期待される動作】: 3つのフィールド名が全て含まれる
# 🔵 タスクファイルの ADVICE_SYSTEM_PROMPT、api-endpoints.md LearningAdviceResponse

def test_advice_system_prompt_json_fields():
    from services.prompts.advice import ADVICE_SYSTEM_PROMPT

    # 【検証項目】: "advice_text" フィールドが指示されていること
    # 🔵 api-endpoints.md の LearningAdviceResponse 仕様
    assert "advice_text" in ADVICE_SYSTEM_PROMPT

    # 【検証項目】: "weak_areas" フィールドが指示されていること
    # 🔵 api-endpoints.md の LearningAdviceResponse 仕様
    assert "weak_areas" in ADVICE_SYSTEM_PROMPT

    # 【検証項目】: "recommendations" フィールドが指示されていること
    # 🔵 api-endpoints.md の LearningAdviceResponse 仕様
    assert "recommendations" in ADVICE_SYSTEM_PROMPT
```

### TC-025: モジュール独立性 - 各モジュール間の相互依存なし

- **テスト名**: generate.py, grading.py, advice.py が互いに import していないこと
  - **境界値の意味**: モジュール間の依存関係の境界（独立 vs 依存）
  - **境界値での動作保証**: 各モジュールが独立して動作できること
- **入力値**: なし（各モジュールの個別 import テスト）
  - **境界値選択の根拠**: 要件定義書 3 節のアーキテクチャ制約「各モジュールは独立して動作」
  - **実際の使用場面**: 個別モジュールの修正・追加時に他モジュールへの影響がないこと
- **期待される結果**:
  - 各モジュールが個別に import 可能
  - **境界での正確性**: 1モジュールだけの import で ImportError が発生しないこと
- **テストの目的**: モジュール独立性の確認
  - **堅牢性の確認**: モジュール分割の設計原則が守られていること
- 🔵 **青信号**: 要件定義書 3 節 アーキテクチャ制約

```python
# 【テスト目的】: 各プロンプトモジュールが独立して import 可能であることを確認
# 【テスト内容】: 各モジュールを個別に import し、エラーなく利用可能であることを検証
# 【期待される動作】: 各モジュールが他モジュールに依存せず動作する
# 🔵 要件定義書 3 節 アーキテクチャ制約から確定

def test_module_independence():
    # 【実際の処理実行】: 各モジュールを個別に import
    # generate.py の独立 import
    from services.prompts.generate import get_card_generation_prompt
    assert callable(get_card_generation_prompt)

    # grading.py の独立 import
    from services.prompts.grading import get_grading_prompt
    assert callable(get_grading_prompt)

    # advice.py の独立 import
    from services.prompts.advice import get_advice_prompt
    assert callable(get_advice_prompt)
```

---

## 4. 開発言語・フレームワーク

- **プログラミング言語**: Python 3.12
  - **言語選択の理由**: 既存プロジェクトが Python 3.12 を使用。AWS Lambda ランタイムとして選定済み
  - **テストに適した機能**: typing.Literal による型定義、dataclass、f-string テンプレート
- **テストフレームワーク**: pytest
  - **フレームワーク選択の理由**: 既存プロジェクトで pytest を使用。`backend/tests/unit/test_bedrock.py` 等の既存テストとの一貫性
  - **テスト実行環境**: `conftest.py` で `sys.path` に `backend/src` を追加。環境変数 `ENVIRONMENT=test` を設定
- 🔵 **青信号**: CLAUDE.md 技術スタック、note.md 技術スタック、既存テストコードから確定

---

## 5. テストファイル構成

### テストファイル 1: `backend/tests/unit/test_generate_prompts.py`

カード生成プロンプト関連テスト（既存互換 + エクスポート確認）:
- TC-001: 日本語カード生成プロンプト
- TC-002: 英語カード生成プロンプト
- TC-003: 全難易度レベル対応
- TC-004: エクスポートシンボルの存在確認

### テストファイル 2: `backend/tests/unit/test_grading_prompts.py`

回答採点プロンプト関連テスト（新規）:
- TC-005: SM-2 グレード定義の存在
- TC-006: システムプロンプトに SM-2 定義含む
- TC-007: 日本語採点プロンプト生成
- TC-008: 英語採点プロンプト生成
- TC-014: language フォールバック
- TC-016: デフォルト language 値
- TC-021: エクスポートシンボルの型確認
- TC-023: JSON レスポンスフィールド指示

### テストファイル 3: `backend/tests/unit/test_advice_prompts.py`

学習アドバイスプロンプト関連テスト（新規）:
- TC-009: システムプロンプトの存在
- TC-010: 辞書形式の統計データ
- TC-011: ReviewSummary dataclass
- TC-013: 弱点分析の指示
- TC-015: language フォールバック
- TC-017: デフォルト language 値
- TC-018: 空の tag_performance
- TC-019: ゼロ値の統計データ
- TC-022: エクスポートシンボルの型確認
- TC-024: JSON レスポンスフィールド指示

### テストファイル 4: `backend/tests/unit/test_prompts_package.py`

パッケージ構造・互換性テスト:
- TC-012: パッケージ経由の import 互換性
- TC-020: 既存 import パス互換性
- TC-025: モジュール独立性

---

## 6. 要件定義との対応関係

### 参照した機能概要
- 要件定義書 1 節「機能の概要」: prompts.py の prompts/ ディレクトリへの分割
- タスクファイル「タスク概要」: 3つの機能別モジュールへの整理

### 参照した入力・出力仕様
- 要件定義書 2.1 節: generate.py の入出力仕様（既存 prompts.py と同一）
- 要件定義書 2.2 節: grading.py の入出力仕様（SM-2 グレード定義含む）
- 要件定義書 2.3 節: advice.py の入出力仕様（ReviewSummary 対応）
- 要件定義書 2.4 節: __init__.py のエクスポートシンボル一覧

### 参照した制約条件
- 要件定義書 3 節 互換性要件: 既存 import パスの後方互換性維持
- 要件定義書 3 節 テスト要件: 既存 260+ テスト保護、新規テスト追加
- 要件定義書 3 節 アーキテクチャ制約: モジュール間の相互依存なし

### 参照した使用例
- 要件定義書 4.1 節: カード生成プロンプト（既存互換）
- 要件定義書 4.2 節: 回答採点プロンプト（新規）
- 要件定義書 4.3 節: 学習アドバイスプロンプト（新規）
- 要件定義書 4.4 節: デフォルト language 値
- 要件定義書 4.5 節: ReviewSummary dataclass 対応
- 要件定義書 4.6 節: 空の tag_performance
- 要件定義書 4.7 節: 未知の language 値フォールバック

### 参照した設計文書
- `docs/design/ai-strands-migration/interfaces.py`: ReviewSummary dataclass 定義
- `docs/design/ai-strands-migration/api-endpoints.md`: GradeAnswerResponse, LearningAdviceResponse 仕様
- `docs/design/ai-strands-migration/design-interview.md`: Q3 (プロンプト管理), Q4 (SRS グレード), Q5 (学習アドバイスデータ)

### 参照した既存コード
- `backend/src/services/prompts.py`: 既存カード生成プロンプト実装 (96行)
- `backend/src/services/ai_service.py`: ReviewSummary dataclass、AIService Protocol
- `backend/tests/unit/test_bedrock.py`: 既存テストの TestPrompts クラス (import パス確認)

---

## 7. 信頼性レベルサマリー

| テストケース | 信頼性 | 根拠 |
|-------------|--------|------|
| TC-001: 日本語カード生成プロンプト | 🔵 | 既存テストから移植 |
| TC-002: 英語カード生成プロンプト | 🔵 | 既存テストから移植 |
| TC-003: 全難易度レベル対応 | 🔵 | 既存テストから移植 |
| TC-004: generate.py エクスポートシンボル | 🔵 | 既存 prompts.py のシンボル一覧 |
| TC-005: SM-2 グレード定義の存在 | 🔵 | REQ-SM-003、api-endpoints.md |
| TC-006: システムプロンプト SM-2 含有 | 🔵 | タスクファイル設計仕様 |
| TC-007: 日本語採点プロンプト生成 | 🔵 | タスクファイル仕様、要件定義書 2.2 節 |
| TC-008: 英語採点プロンプト生成 | 🔵 | タスクファイル仕様 |
| TC-009: advice システムプロンプト | 🔵 | タスクファイル仕様、REQ-SM-004 |
| TC-010: 辞書形式統計データ | 🔵 | タスクファイル仕様、設計ヒアリング Q5 |
| TC-011: ReviewSummary dataclass | 🔵 | interfaces.py ReviewSummary 定義 |
| TC-012: パッケージ import 互換性 | 🔵 | 要件定義書 2.4 節、REQ-SM-402 |
| TC-013: 弱点分析の指示 | 🔵 | タスクファイルのテンプレート内容 |
| TC-014: grading language フォールバック | 🟡 | 要件定義書 4.7 節から推測 |
| TC-015: advice language フォールバック | 🟡 | 要件定義書 4.7 節から推測 |
| TC-016: grading デフォルト language | 🔵 | シグネチャ定義、要件定義書 4.4 節 |
| TC-017: advice デフォルト language | 🔵 | シグネチャ定義 |
| TC-018: 空の tag_performance | 🟡 | 要件定義書 4.6 節から推測 |
| TC-019: ゼロ値の統計データ | 🟡 | エッジケースから推測 |
| TC-020: 既存 import パス互換性 | 🔵 | REQ-SM-402、既存テストコード |
| TC-021: grading エクスポートシンボル | 🔵 | タスクファイル 2 節 |
| TC-022: advice エクスポートシンボル | 🔵 | タスクファイル 5 節 |
| TC-023: grading JSON フィールド指示 | 🔵 | api-endpoints.md GradeAnswerResponse |
| TC-024: advice JSON フィールド指示 | 🔵 | api-endpoints.md LearningAdviceResponse |
| TC-025: モジュール独立性 | 🔵 | 要件定義書 3 節 アーキテクチャ制約 |

### 統計

- 🔵 **青信号**: 21件 (84%)
- 🟡 **黄信号**: 4件 (16%)
- 🔴 **赤信号**: 0件 (0%)

**信頼性指標**: 92

---

## 8. テストケース実装時の共通セットアップ

```python
# backend/tests/conftest.py 設定済み:
# - sys.path に backend/src を追加
# - ENVIRONMENT=test 環境変数を設定
# - テスト用 fixture 定義済み

# 各テストファイルの冒頭:
"""
# 【テスト前準備】: conftest.py が sys.path に backend/src を追加し、
#   services.prompts パッケージが import 可能な状態にする
# 【環境初期化】: ENVIRONMENT=test で Lambda 固有の環境変数が不要
"""
```
