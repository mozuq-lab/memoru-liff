# TASK-0054: プロンプトモジュールディレクトリ化 - Green フェーズ記録

**作成日**: 2026-02-23
**フェーズ**: Green（テストを通すための最小実装）
**テスト結果**: 28件 全て通過

---

## 実装方針

### 全体方針

- 既存の `backend/src/services/prompts.py`（96行）を `backend/src/services/prompts/` パッケージに移行
- `generate.py`：既存コードをそのまま移行（後方互換性維持）
- `grading.py`：SM-2 グレード定義（0-5）と採点プロンプトを新規作成
- `advice.py`：学習アドバイスプロンプトを新規作成（dict/ReviewSummary 両対応）
- `__init__.py`：全シンボルを再エクスポートし `from services.prompts import ...` 互換性を維持

### 設計判断

1. **Language 型の再定義**: 各モジュールが独立して動作するため、`Language` 型エイリアスを各ファイルで再定義（generate.py, grading.py, advice.py に各々定義）
2. **言語フォールバック**: `.get(language, "Respond in Japanese.")` パターンで未知の言語値を安全に処理
3. **dict/dataclass 両対応**: `isinstance(review_summary, dict)` で分岐し、`getattr` で dataclass 属性を取得

---

## 実装したコード

### `backend/src/services/prompts/__init__.py` (51行)

```python
"""プロンプトパッケージ - 全モジュールの共通エクスポート."""

# generate.py エクスポート
from .generate import (
    get_card_generation_prompt,
    DIFFICULTY_GUIDELINES,
    DifficultyLevel,
    Language,
)

# grading.py エクスポート
from .grading import (
    get_grading_prompt,
    GRADING_SYSTEM_PROMPT,
    SM2_GRADE_DEFINITIONS,
)

# advice.py エクスポート
from .advice import (
    get_advice_prompt,
    ADVICE_SYSTEM_PROMPT,
)

__all__ = [
    "get_card_generation_prompt", "DIFFICULTY_GUIDELINES", "DifficultyLevel", "Language",
    "get_grading_prompt", "GRADING_SYSTEM_PROMPT", "SM2_GRADE_DEFINITIONS",
    "get_advice_prompt", "ADVICE_SYSTEM_PROMPT",
]
```

### `backend/src/services/prompts/generate.py` (122行)

既存 `prompts.py` の完全移行。変更なし。

### `backend/src/services/prompts/grading.py` (94行)

- `SM2_GRADE_DEFINITIONS`: グレード 0-5 の全定義テキスト
- `GRADING_SYSTEM_PROMPT`: SM-2 採点指示（grade, reasoning, feedback の JSON 出力指示含む）
- `get_grading_prompt(card_front, card_back, user_answer, language="ja")`: 採点プロンプト生成

### `backend/src/services/prompts/advice.py` (124行)

- `ADVICE_SYSTEM_PROMPT`: アドバイス指示（advice_text, weak_areas, recommendations の JSON 出力指示含む）
- `get_advice_prompt(review_summary, language="ja")`: dict と ReviewSummary dataclass の両方に対応

---

## テスト実行結果

```
============================= test session starts ==============================
collected 28 items

tests/unit/test_generate_prompts.py::TestJapanesePromptGeneration::test_japanese_prompt_generation PASSED
tests/unit/test_generate_prompts.py::TestEnglishPromptGeneration::test_english_prompt_generation PASSED
tests/unit/test_generate_prompts.py::TestDifficultyLevels::test_difficulty_levels PASSED
tests/unit/test_generate_prompts.py::TestGenerateExports::test_generate_exports PASSED
tests/unit/test_generate_prompts.py::TestBackwardCompatibleImport::test_backward_compatible_import PASSED
tests/unit/test_grading_prompts.py::TestSM2GradeDefinitions::test_sm2_grade_definitions_contain_all_grades PASSED
tests/unit/test_grading_prompts.py::TestGradingSystemPromptContent::test_grading_system_prompt_content PASSED
tests/unit/test_grading_prompts.py::TestGetGradingPromptJapanese::test_get_grading_prompt_japanese PASSED
tests/unit/test_grading_prompts.py::TestGetGradingPromptEnglish::test_get_grading_prompt_english PASSED
tests/unit/test_grading_prompts.py::TestGradingPromptLanguageFallback::test_grading_prompt_language_fallback PASSED
tests/unit/test_grading_prompts.py::TestGradingPromptDefaultLanguage::test_grading_prompt_default_language PASSED
tests/unit/test_grading_prompts.py::TestGradingExports::test_grading_exports PASSED
tests/unit/test_grading_prompts.py::TestGradingSystemPromptJsonFields::test_grading_system_prompt_json_fields PASSED
tests/unit/test_advice_prompts.py::TestAdviceSystemPromptExists::test_advice_system_prompt_exists PASSED
tests/unit/test_advice_prompts.py::TestGetAdvicePromptWithDict::test_get_advice_prompt_with_dict PASSED
tests/unit/test_advice_prompts.py::TestGetAdvicePromptWithReviewSummary::test_get_advice_prompt_with_review_summary PASSED
tests/unit/test_advice_prompts.py::TestGetAdvicePromptContainsImprovementFocus::test_get_advice_prompt_contains_improvement_focus PASSED
tests/unit/test_advice_prompts.py::TestAdvicePromptLanguageFallback::test_advice_prompt_language_fallback PASSED
tests/unit/test_advice_prompts.py::TestAdvicePromptDefaultLanguage::test_advice_prompt_default_language PASSED
tests/unit/test_advice_prompts.py::TestAdvicePromptEmptyTagPerformance::test_advice_prompt_empty_tag_performance PASSED
tests/unit/test_advice_prompts.py::TestAdvicePromptZeroStats::test_advice_prompt_zero_stats PASSED
tests/unit/test_advice_prompts.py::TestAdviceExports::test_advice_exports PASSED
tests/unit/test_advice_prompts.py::TestAdviceSystemPromptJsonFields::test_advice_system_prompt_json_fields PASSED
tests/unit/test_prompts_package.py::TestPackageImports::test_package_imports PASSED
tests/unit/test_prompts_package.py::TestModuleIndependence::test_module_independence PASSED
tests/unit/test_prompts_package.py::TestModuleIndependence::test_generate_module_standalone PASSED
tests/unit/test_prompts_package.py::TestModuleIndependence::test_grading_module_standalone PASSED
tests/unit/test_prompts_package.py::TestModuleIndependence::test_advice_module_standalone PASSED

============================== 28 passed in 0.03s ==============================
```

### 全体テスト確認（既存テスト保護）

```
288 passed in 8.05s
```

既存 260+ テスト + 新規 28 テスト = 288 件全て通過。

---

## 課題・改善点（Refactor フェーズで対応）

1. **Language 型の重複定義**: generate.py, grading.py, advice.py の各ファイルで `Language` 型エイリアスを重複定義している。共通ユーティリティモジュールを作成するか検討
2. **プロンプト文字列の外部化**: 現状はハードコーディング。将来的には設定ファイルや DB 管理も検討可能
3. **型ヒント改善**: `review_summary: Union[dict, object]` を `Union[dict, ReviewSummary]` に改善可能（ただし循環 import に注意）

---

## 品質評価

- テスト成功: 28/28 (100%) ✅
- 実装のシンプルさ: 高（プロンプトテンプレートのみ） ✅
- リファクタリング箇所: 明確（Language 型の重複定義） ✅
- 機能的問題: なし ✅
- ファイルサイズ: 391行合計（800行制限内） ✅
- モック使用: なし（純粋な文字列操作のみ） ✅

**品質判定**: ✅ 高品質
