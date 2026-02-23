# TASK-0054: プロンプトモジュールディレクトリ化 - Refactor フェーズ記録

**作成日**: 2026-02-23
**フェーズ**: Refactor（品質改善）
**テスト結果**: 28件 全て通過（既存テスト含む344件全て通過）

---

## 改善概要

Greenフェーズで識別された以下の3つの課題を解決した:

| # | 課題 | 優先度 | 信頼性 |
|---|------|--------|--------|
| 1 | `Language` 型の3ファイル重複定義 | 高 | 🔵 |
| 2 | `_LANGUAGE_INSTRUCTION` 辞書の2ファイル重複定義 | 高 | 🔵 |
| 3 | `advice.py` の型ヒント `Union[dict, object]` の改善 | 中 | 🟡 |

---

## セキュリティレビュー結果

**レビュー対象**: `generate.py`, `grading.py`, `advice.py`

| 観点 | 結果 | 詳細 |
|------|------|------|
| インジェクション防止 | 問題なし 🔵 | 要件定義書 NFR-SM-102 通り、プロンプト層はサニタイズ対象外。呼び出し元（サービス層）の責務 |
| 入力値検証 | 問題なし 🔵 | プロンプトモジュールは純粋な文字列テンプレート層であり、バリデーションは不要 |
| 型の安全性 | 改善済み 🔵 | `Union[dict, object]` → `Union[dict, ReviewSummary]` に改善（`TYPE_CHECKING` で循環 import 回避） |

**結論**: 重大な脆弱性なし ✅

---

## パフォーマンスレビュー結果

**レビュー対象**: 全プロンプト生成関数

| 観点 | 結果 | 詳細 |
|------|------|------|
| 計算量 | 問題なし 🔵 | 全関数が純粋な文字列操作のみ、O(n) 以下 |
| メモリ使用量 | 問題なし 🔵 | モジュール定数は初期化時に一度だけ生成 |
| テスト実行時間 | 高速 🔵 | 28件のテストが 0.03秒で完了（2秒閾値を大幅に下回る） |
| Lambda cold start | 問題なし 🔵 | 新規 `_types.py` モジュール（38行）の追加は影響を無視できるレベル |

**結論**: 重大な性能課題なし ✅

---

## リファクタリング実施内容

### 1. `_types.py` 共通型モジュールの新規作成 🔵

**ファイル**: `backend/src/services/prompts/_types.py` (38行)

**改善内容**: DRY 原則の適用。`Language` 型と言語指示マッピングを一元管理。

```python
from typing import Literal

# 【型定義】: 出力言語の型エイリアス
Language = Literal["ja", "en"]

# 【定数定義】: 言語コードから AI 応答言語指示へのマッピング
LANGUAGE_INSTRUCTION: dict[str, str] = {
    "ja": "Respond in Japanese.",
    "en": "Respond in English.",
}

# 【定数定義】: フォールバック時の言語指示（日本語）
DEFAULT_LANGUAGE_INSTRUCTION = LANGUAGE_INSTRUCTION["ja"]
```

**効果**: 3ファイルの重複 `Language` 型定義と2ファイルの重複 `_LANGUAGE_INSTRUCTION` 辞書定義を統合

### 2. `generate.py` の `Language` 型を共通モジュールから import 🔵

**変更箇所**:
- `from typing import Literal` のみ → `from ._types import Language` を追加
- インラインの `Language = Literal["ja", "en"]` 定義を削除

### 3. `grading.py` の `Language` 型と `_LANGUAGE_INSTRUCTION` を共通モジュールから import 🔵

**変更箇所**:
- `from typing import Literal` → `from ._types import DEFAULT_LANGUAGE_INSTRUCTION, LANGUAGE_INSTRUCTION, Language`
- インラインの `Language = Literal["ja", "en"]` 定義を削除
- `_LANGUAGE_INSTRUCTION = {...}` 辞書定義を削除
- `_LANGUAGE_INSTRUCTION.get(language, "Respond in Japanese.")` → `LANGUAGE_INSTRUCTION.get(language, DEFAULT_LANGUAGE_INSTRUCTION)`

### 4. `advice.py` の型ヒントと共通型の改善 🟡

**変更箇所**:
- `from typing import Literal, Union` → `from typing import TYPE_CHECKING, Union`
- `from ._types import DEFAULT_LANGUAGE_INSTRUCTION, LANGUAGE_INSTRUCTION, Language` を追加
- `TYPE_CHECKING` ブロックで `ReviewSummary` を import（循環 import 回避）
- `get_advice_prompt(review_summary: Union[dict, object], ...)` → `Union[dict, ReviewSummary]` に改善
- インラインの `Language = Literal["ja", "en"]` 定義を削除
- `_LANGUAGE_INSTRUCTION = {...}` 辞書定義を削除

---

## 最終コード

### `_types.py` (38行) - 新規作成

`backend/src/services/prompts/_types.py` を参照

### `generate.py` (125行)

`backend/src/services/prompts/generate.py` を参照

### `grading.py` (87行) - 94行から削減

`backend/src/services/prompts/grading.py` を参照

### `advice.py` (128行) - 124行から微増（型ヒント改善分）

`backend/src/services/prompts/advice.py` を参照

---

## テスト実行結果

### TASK-0054 専用テスト

```
28 passed in 0.03s
```

### 全体テスト（既存テスト保護確認）

```
344 passed in 9.69s
```

既存 260+ テスト + TASK-0053 テスト + 新規 28 テスト = 344 件全て通過

---

## コメント改善内容

- 各ファイルのモジュール docstring に `【改善内容】` セクションを追加
- `_types.py` の各定数に `【再利用性】` と `【調整可能性】` コメントを追加
- `grading.py` と `advice.py` の言語指示取得コードに `【改善内容】` コメントを追加

---

## ファイルサイズ

| ファイル | 行数 | 制限 |
|---------|------|------|
| `__init__.py` | 51行 | 500行以内 ✅ |
| `_types.py` | 38行 | 500行以内 ✅ |
| `generate.py` | 125行 | 500行以内 ✅ |
| `grading.py` | 87行 | 500行以内 ✅ |
| `advice.py` | 128行 | 500行以内 ✅ |
| **合計** | **429行** | - |

---

## 品質評価

- テスト成功: 28/28 (100%) ✅
- セキュリティ: 重大な脆弱性なし ✅
- パフォーマンス: 重大な性能課題なし ✅
- リファクタ品質: DRY 原則適用、型ヒント改善、重複定義排除 ✅
- コード品質: 日本語コメント充実、信頼性レベル表示 ✅
- ファイルサイズ: 全ファイル500行以内 ✅

**品質判定**: ✅ 高品質
