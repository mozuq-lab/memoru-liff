# TASK-0054: プロンプトモジュールディレクトリ化 - Red フェーズ記録

**作成日**: 2026-02-23
**フェーズ**: Red（失敗するテスト作成）
**テスト結果**: 28件 全て失敗（期待通り）

---

## 作成したテストケース一覧

### テストファイル 1: `backend/tests/unit/test_generate_prompts.py`

| テストID | テストクラス | テスト名 | 信頼性 |
|---------|------------|---------|--------|
| TC-001 | TestJapanesePromptGeneration | test_japanese_prompt_generation | 🔵 |
| TC-002 | TestEnglishPromptGeneration | test_english_prompt_generation | 🔵 |
| TC-003 | TestDifficultyLevels | test_difficulty_levels | 🔵 |
| TC-004 | TestGenerateExports | test_generate_exports | 🔵 |
| TC-020 | TestBackwardCompatibleImport | test_backward_compatible_import | 🔵 |

### テストファイル 2: `backend/tests/unit/test_grading_prompts.py`

| テストID | テストクラス | テスト名 | 信頼性 |
|---------|------------|---------|--------|
| TC-005 | TestSM2GradeDefinitions | test_sm2_grade_definitions_contain_all_grades | 🔵 |
| TC-006 | TestGradingSystemPromptContent | test_grading_system_prompt_content | 🔵 |
| TC-007 | TestGetGradingPromptJapanese | test_get_grading_prompt_japanese | 🔵 |
| TC-008 | TestGetGradingPromptEnglish | test_get_grading_prompt_english | 🔵 |
| TC-014 | TestGradingPromptLanguageFallback | test_grading_prompt_language_fallback | 🟡 |
| TC-016 | TestGradingPromptDefaultLanguage | test_grading_prompt_default_language | 🔵 |
| TC-021 | TestGradingExports | test_grading_exports | 🔵 |
| TC-023 | TestGradingSystemPromptJsonFields | test_grading_system_prompt_json_fields | 🔵 |

### テストファイル 3: `backend/tests/unit/test_advice_prompts.py`

| テストID | テストクラス | テスト名 | 信頼性 |
|---------|------------|---------|--------|
| TC-009 | TestAdviceSystemPromptExists | test_advice_system_prompt_exists | 🔵 |
| TC-010 | TestGetAdvicePromptWithDict | test_get_advice_prompt_with_dict | 🔵 |
| TC-011 | TestGetAdvicePromptWithReviewSummary | test_get_advice_prompt_with_review_summary | 🔵 |
| TC-013 | TestGetAdvicePromptContainsImprovementFocus | test_get_advice_prompt_contains_improvement_focus | 🔵 |
| TC-015 | TestAdvicePromptLanguageFallback | test_advice_prompt_language_fallback | 🟡 |
| TC-017 | TestAdvicePromptDefaultLanguage | test_advice_prompt_default_language | 🔵 |
| TC-018 | TestAdvicePromptEmptyTagPerformance | test_advice_prompt_empty_tag_performance | 🟡 |
| TC-019 | TestAdvicePromptZeroStats | test_advice_prompt_zero_stats | 🟡 |
| TC-022 | TestAdviceExports | test_advice_exports | 🔵 |
| TC-024 | TestAdviceSystemPromptJsonFields | test_advice_system_prompt_json_fields | 🔵 |

### テストファイル 4: `backend/tests/unit/test_prompts_package.py`

| テストID | テストクラス | テスト名 | 信頼性 |
|---------|------------|---------|--------|
| TC-012 | TestPackageImports | test_package_imports | 🔵 |
| TC-025 | TestModuleIndependence | test_module_independence | 🔵 |
| TC-025a | TestModuleIndependence | test_generate_module_standalone | 🔵 |
| TC-025b | TestModuleIndependence | test_grading_module_standalone | 🔵 |
| TC-025c | TestModuleIndependence | test_advice_module_standalone | 🔵 |

**合計**: 28テストケース

---

## 期待される失敗メッセージ

```
ModuleNotFoundError: No module named 'services.prompts.generate'; 'services.prompts' is not a package
```

**失敗の根本原因**:

- `backend/src/services/prompts.py` がファイルとして存在するため、`services.prompts` はモジュール（ファイル）として扱われる
- `services.prompts.generate` のようなサブモジュールアクセスは、`prompts` がパッケージ（ディレクトリ）でなければ不可能
- また `services.prompts.grading`, `services.prompts.advice` も同様に未存在

---

## テスト実行コマンド

```bash
cd backend

# 新規テストファイルのみ実行（全て失敗することを確認）
python -m pytest tests/unit/test_generate_prompts.py tests/unit/test_grading_prompts.py tests/unit/test_advice_prompts.py tests/unit/test_prompts_package.py -v

# 結果: 28 failed
```

---

## Green フェーズで実装すべき内容

### 1. `prompts/` ディレクトリの作成

```bash
mkdir backend/src/services/prompts/
```

### 2. `prompts/__init__.py` の作成

全シンボルを再エクスポートし、`from services.prompts import ...` の既存パスを維持する:

```python
from .generate import get_card_generation_prompt, DIFFICULTY_GUIDELINES, DifficultyLevel, Language
from .grading import get_grading_prompt, GRADING_SYSTEM_PROMPT, SM2_GRADE_DEFINITIONS
from .advice import get_advice_prompt, ADVICE_SYSTEM_PROMPT

__all__ = [
    "get_card_generation_prompt", "DIFFICULTY_GUIDELINES", "DifficultyLevel", "Language",
    "get_grading_prompt", "GRADING_SYSTEM_PROMPT", "SM2_GRADE_DEFINITIONS",
    "get_advice_prompt", "ADVICE_SYSTEM_PROMPT",
]
```

### 3. `prompts/generate.py` の作成

既存 `prompts.py` の内容をそのまま移行する（変更なし）。

### 4. `prompts/grading.py` の作成（新規）

- `SM2_GRADE_DEFINITIONS` 定数: グレード 0-5 の定義テキスト
- `GRADING_SYSTEM_PROMPT` 定数: SM-2 採点指示システムプロンプト（JSON 出力: grade, reasoning, feedback）
- `get_grading_prompt(card_front, card_back, user_answer, language="ja")` 関数

### 5. `prompts/advice.py` の作成（新規）

- `ADVICE_SYSTEM_PROMPT` 定数: 学習アドバイス指示システムプロンプト（JSON 出力: advice_text, weak_areas, recommendations）
- `get_advice_prompt(review_summary, language="ja")` 関数: dict と ReviewSummary dataclass の両方に対応

### 6. 旧 `prompts.py` の削除

```bash
rm backend/src/services/prompts.py
```

### 7. テスト実行

```bash
cd backend
python -m pytest tests/unit/test_generate_prompts.py tests/unit/test_grading_prompts.py tests/unit/test_advice_prompts.py tests/unit/test_prompts_package.py -v
# 全28テストが通過することを確認

make test
# 既存260+テストも全て通過することを確認
```

---

## 信頼性レベルサマリー

| 信頼性 | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 24 | 86% |
| 🟡 黄信号 | 4 | 14% |
| 🔴 赤信号 | 0 | 0% |

**品質判定**: ✅ 高品質
