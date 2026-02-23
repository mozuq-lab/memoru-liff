# TASK-0054: プロンプトモジュールディレクトリ化 - TDD 要件定義書

**タスクID**: TASK-0054
**機能名**: プロンプトモジュールディレクトリ化
**要件名**: ai-strands-migration
**タスクタイプ**: TDD (Red -> Green -> Refactor)
**作成日**: 2026-02-23

---

## 1. 機能の概要

### 何をする機能か 🔵

既存の `backend/src/services/prompts.py`（カード生成プロンプト専用の単一ファイル）を `backend/src/services/prompts/` ディレクトリに分割し、以下の3つの機能別モジュールに整理する:

1. **generate.py** - カード生成プロンプト（既存 `prompts.py` からの移行）
2. **grading.py** - 回答採点プロンプト（新規作成、SM-2 グレード定義含む）
3. **advice.py** - 学習アドバイスプロンプト（新規作成）

### どのような問題を解決するか 🔵

- 現行の `prompts.py` はカード生成専用で、回答採点・学習アドバイスの新 AI 機能に対応できない
- 単一ファイルにすべてのプロンプトを集約すると、メンテナンス性が低下する
- Strands Agents SDK 統合において、各機能のシステムプロンプトを独立して管理できる構造が必要

**参照したEARS要件**: REQ-SM-001, REQ-SM-003, REQ-SM-004
**参照した設計文書**: architecture.md プロンプト管理セクション

### 想定されるユーザー 🔵

- 開発者（プロンプトの追加・修正を行う）
- 後続タスク（TASK-0057: grade_answer 実装、TASK-0059: get_learning_advice 実装）がプロンプトモジュールに依存

### システム内での位置づけ 🔵

- Phase 1（基盤構築）の一部として、TASK-0053（AIService Protocol）の後に実施
- TASK-0057（StrandsAIService カード生成）、TASK-0059（回答採点）、TASK-0061（学習アドバイス）の基盤

**参照した設計文書**: architecture.md コンポーネント構成図、design-interview.md Q3

---

## 2. 入力・出力の仕様

### 2.1 generate.py（既存移行） 🔵

**信頼性**: 🔵 *既存 `prompts.py` の実装をそのまま移行*

#### 入力

| パラメータ | 型 | 制約 | 説明 |
|-----------|------|------|------|
| `input_text` | `str` | 10-2000文字 | カード生成元テキスト |
| `card_count` | `int` | 1-10 | 生成カード数 |
| `difficulty` | `DifficultyLevel` | "easy"/"medium"/"hard" | 難易度 |
| `language` | `Language` | "ja"/"en" | 出力言語 |

#### 出力

| 項目 | 型 | 説明 |
|------|------|------|
| 戻り値 | `str` | フォーマット済みプロンプト文字列 |

#### エクスポートシンボル

- `get_card_generation_prompt` 関数
- `DIFFICULTY_GUIDELINES` 辞書
- `DifficultyLevel` 型エイリアス
- `Language` 型エイリアス

**参照した設計文書**: 既存 `backend/src/services/prompts.py`

### 2.2 grading.py（新規作成） 🔵

**信頼性**: 🔵 *REQ-SM-003、設計ヒアリング Q4 より*

#### 入力

| パラメータ | 型 | 制約 | 説明 |
|-----------|------|------|------|
| `card_front` | `str` | 非空文字列 | カード表面（問題文） |
| `card_back` | `str` | 非空文字列 | カード裏面（正解） |
| `user_answer` | `str` | 非空文字列 | ユーザーの回答 |
| `language` | `Language` | "ja"/"en" | 出力言語（デフォルト: "ja"） |

#### 出力

| 項目 | 型 | 説明 |
|------|------|------|
| 戻り値 | `str` | SM-2 グレード定義を含む採点プロンプト文字列 |

#### エクスポートシンボル

- `get_grading_prompt` 関数
- `GRADING_SYSTEM_PROMPT` 文字列定数
- `SM2_GRADE_DEFINITIONS` 文字列定数

#### SM-2 グレード定義 🔵

プロンプト内に以下のグレード定義を埋め込む:

| グレード | 意味 | AI 判定基準 |
|---------|------|------------|
| 5 | Perfect response | 完璧な回答 |
| 4 | Correct with some hesitation | 正解、軽微な不備あり |
| 3 | Correct with serious difficulty | 正解だが大きな困難あり |
| 2 | Incorrect; correct answer seemed easy | 不正解だが正解を聞けば容易に思い出す |
| 1 | Incorrect; correct answer remembered | 不正解だが関連する知識あり |
| 0 | Complete blackout | 回答なし、または完全に無関係 |

#### 期待される AI レスポンス形式 🔵

```json
{
  "grade": 0-5,
  "reasoning": "<brief explanation in target language>",
  "feedback": "<constructive feedback for the student>"
}
```

**参照したEARS要件**: REQ-SM-003
**参照した設計文書**: api-endpoints.md SRS グレード定義表、design-interview.md Q4

### 2.3 advice.py（新規作成） 🔵

**信頼性**: 🔵 *REQ-SM-004、設計ヒアリング Q5 より*

#### 入力

| パラメータ | 型 | 制約 | 説明 |
|-----------|------|------|------|
| `review_summary` | `dict` or `ReviewSummary` | 必須フィールドあり | 復習統計サマリー |
| `language` | `Language` | "ja"/"en" | 出力言語（デフォルト: "ja"） |

#### review_summary の必須フィールド 🔵

| フィールド | 型 | 説明 |
|-----------|------|------|
| `total_reviews` | `int` | 総復習回数 |
| `average_grade` | `float` | 平均グレード (0.0-5.0) |
| `total_cards` | `int` | 総カード数 |
| `cards_due_today` | `int` | 本日期限カード数 |
| `streak_days` | `int` | 連続学習日数 |
| `tag_performance` | `dict[str, float]` | タグ別正答率 |

#### 出力

| 項目 | 型 | 説明 |
|------|------|------|
| 戻り値 | `str` | 統計データ埋め込み済み学習アドバイスプロンプト文字列 |

#### エクスポートシンボル

- `get_advice_prompt` 関数
- `ADVICE_SYSTEM_PROMPT` 文字列定数

#### 期待される AI レスポンス形式 🔵

```json
{
  "advice_text": "<main personalized advice>",
  "weak_areas": ["<area1>", "<area2>"],
  "recommendations": ["<strategy1>", "<strategy2>"]
}
```

**参照したEARS要件**: REQ-SM-004
**参照した設計文書**: interfaces.py ReviewSummary、design-interview.md Q5

### 2.4 __init__.py（共通エクスポート） 🔵

**信頼性**: 🔵 *モジュール整理の標準手法*

以下のシンボルを再エクスポートし、`from services.prompts import ...` の形式で利用可能にする:

```python
# generate.py から
get_card_generation_prompt, DIFFICULTY_GUIDELINES, DifficultyLevel, Language

# grading.py から
get_grading_prompt, GRADING_SYSTEM_PROMPT, SM2_GRADE_DEFINITIONS

# advice.py から
get_advice_prompt, ADVICE_SYSTEM_PROMPT
```

---

## 3. 制約条件

### パフォーマンス要件 🔵

- プロンプト生成関数は純粋な文字列操作であり、パフォーマンス制約なし
- Lambda cold start への影響は無視できるレベル

**参照したEARS要件**: NFR-SM-001

### 互換性要件 🔵

- 既存の `from services.prompts import get_card_generation_prompt` の import パスが `__init__.py` 経由で引き続き動作すること
- `get_card_generation_prompt()` 関数のシグネチャと戻り値が変更されないこと
- 既存のテスト `test_bedrock.py` が修正なしで（もしくは import パス変更のみで）通過すること

**参照したEARS要件**: REQ-SM-402, REQ-SM-405
**参照した設計文書**: architecture.md 互換性制約

### テスト要件 🔵

- 既存 260+ テストが全て通過すること
- テストカバレッジ 80% 以上を維持すること
- 新規テストファイル:
  - `backend/tests/unit/test_grading_prompts.py`
  - `backend/tests/unit/test_advice_prompts.py`

**参照したEARS要件**: REQ-SM-404, REQ-SM-405

### アーキテクチャ制約 🔵

- Python 3.12 ランタイム
- `typing.Literal` による型定義
- 各モジュールは独立して動作（モジュール間の相互依存なし）
- `grading.py` と `advice.py` は `ai_service.py` の型定義を直接参照しない（プロンプトモジュールは純粋なテンプレート層）

**参照した設計文書**: architecture.md アーキテクチャパターン、CLAUDE.md 技術スタック

### セキュリティ要件 🟡

- プロンプトテンプレートにユーザー入力を埋め込む際のインジェクション防止は、プロンプト関数の呼び出し元（サービス層）の責務
- プロンプトモジュール自体はサニタイズを行わない

**参照したEARS要件**: NFR-SM-102

---

## 4. 想定される使用例

### 4.1 基本パターン: カード生成プロンプト（既存互換） 🔵

```python
from services.prompts import get_card_generation_prompt

prompt = get_card_generation_prompt(
    input_text="光合成は植物が太陽光エネルギーを...",
    card_count=5,
    difficulty="medium",
    language="ja"
)
# prompt: フォーマット済みのカード生成プロンプト文字列
```

**参照したEARS要件**: REQ-SM-002

### 4.2 基本パターン: 回答採点プロンプト（新規） 🔵

```python
from services.prompts.grading import get_grading_prompt, GRADING_SYSTEM_PROMPT

system_prompt = GRADING_SYSTEM_PROMPT  # Strands Agent のシステムプロンプトに設定

user_prompt = get_grading_prompt(
    card_front="日本の首都は？",
    card_back="東京",
    user_answer="東京です",
    language="ja"
)
# user_prompt: 問題・正解・回答を含むプロンプト文字列
```

**参照したEARS要件**: REQ-SM-003
**参照した設計文書**: dataflow.md 機能2 回答採点フロー

### 4.3 基本パターン: 学習アドバイスプロンプト（新規） 🔵

```python
from services.prompts.advice import get_advice_prompt, ADVICE_SYSTEM_PROMPT

review_stats = {
    "total_reviews": 100,
    "average_grade": 3.5,
    "total_cards": 50,
    "cards_due_today": 10,
    "streak_days": 7,
    "tag_performance": {"noun": 3.8, "verb": 3.2}
}

system_prompt = ADVICE_SYSTEM_PROMPT
user_prompt = get_advice_prompt(review_stats, language="ja")
```

**参照したEARS要件**: REQ-SM-004
**参照した設計文書**: dataflow.md 機能3 学習アドバイスフロー

### 4.4 エッジケース: デフォルト値 🔵

```python
# language パラメータ未指定時のデフォルト（"ja"）
prompt = get_grading_prompt(
    card_front="Q",
    card_back="A",
    user_answer="A"
)
# デフォルトで日本語の採点プロンプトが生成される
```

### 4.5 エッジケース: ReviewSummary dataclass 対応 🔵

```python
from services.ai_service import ReviewSummary

summary = ReviewSummary(
    total_reviews=100,
    average_grade=3.5,
    total_cards=50,
    cards_due_today=10,
    streak_days=7,
    tag_performance={"noun": 3.8},
    recent_review_dates=["2026-02-20"]
)

# dict でも ReviewSummary でも動作する
prompt = get_advice_prompt(summary, language="en")
```

**参照した設計文書**: interfaces.py ReviewSummary

### 4.6 エッジケース: 空の tag_performance 🟡

```python
stats = {
    "total_reviews": 0,
    "average_grade": 0.0,
    "total_cards": 0,
    "cards_due_today": 0,
    "streak_days": 0,
    "tag_performance": {}  # 空の辞書
}
prompt = get_advice_prompt(stats)
# tag_performance が空でも正常にプロンプトが生成される
```

### 4.7 エッジケース: 未知の language 値 🟡

```python
# language に未知の値が渡された場合、日本語にフォールバック
prompt = get_grading_prompt(
    card_front="Q",
    card_back="A",
    user_answer="A",
    language="fr"  # サポート外
)
# "Respond in Japanese." にフォールバック
```

---

## 5. EARS要件・設計文書との対応関係

### 参照したユーザストーリー

- ストーリー 1.1: カード生成機能の Strands Agents 移行
- ストーリー 2.1: AI による回答採点
- ストーリー 3.1: AI による学習アドバイス

### 参照した機能要件

- **REQ-SM-001**: Strands Agents SDK 統合（プロンプト管理の基盤として）
- **REQ-SM-002**: カード生成 generate_cards() インターフェース維持
- **REQ-SM-003**: 回答採点 AI 機能（grading.py の基盤）
- **REQ-SM-004**: 学習アドバイス AI 機能（advice.py の基盤）

### 参照した非機能要件

- **NFR-SM-001**: カード生成レスポンスタイム 30 秒以内
- **NFR-SM-102**: プロンプトインジェクション防止
- **REQ-SM-402**: API レスポンス形式互換性
- **REQ-SM-404**: テストカバレッジ 80% 以上
- **REQ-SM-405**: 既存 260+ テスト保護

### 参照した Edge ケース

- **EDGE-SM-003**: フィーチャーフラグ切替時の安全性（プロンプト層は影響なし）

### 参照した受け入れ基準

- `prompts/` ディレクトリが正しく作成されていること
- `generate.py` に既存プロンプトが完全に移行されていること
- `grading.py` に SM-2 グレード定義 (0-5) 付きプロンプトが含まれていること
- `advice.py` に ReviewSummary 対応のプロンプトが含まれていること
- 全 import パスが更新されていること
- 既存テスト + 新規テストが全て通過すること

### 参照した設計文書

- **アーキテクチャ**: architecture.md - プロンプト管理セクション、コンポーネント構成図
- **データフロー**: dataflow.md - 機能1 (カード生成), 機能2 (回答採点), 機能3 (学習アドバイス)
- **型定義**: interfaces.py - ReviewSummary, GradingResult, LearningAdvice
- **API仕様**: api-endpoints.md - POST /cards/generate, POST /reviews/{card_id}/grade-ai, GET /advice
- **設計ヒアリング**: design-interview.md - Q3 (プロンプト管理), Q4 (SRS グレード変換), Q5 (学習アドバイスデータ参照)

---

## 6. ディレクトリ構造

### 実装対象ファイル 🔵

```
backend/src/services/
├── prompts/                    # 新規ディレクトリ
│   ├── __init__.py             # 共通エクスポート
│   ├── generate.py             # カード生成（既存 prompts.py から移行）
│   ├── grading.py              # 回答採点（新規）
│   └── advice.py               # 学習アドバイス（新規）
├── prompts.py                  # 削除予定（旧ファイル）
└── ...
```

### テストファイル 🔵

```
backend/tests/unit/
├── test_bedrock.py             # 既存テスト（import パス更新が必要な場合あり）
├── test_grading_prompts.py     # 新規テスト
└── test_advice_prompts.py      # 新規テスト
```

### import パス更新対象 🔵

| ファイル | 旧 import | 新 import（推奨） |
|---------|-----------|------------------|
| `backend/tests/unit/test_bedrock.py` | `from services.prompts import get_card_generation_prompt` | `from services.prompts import get_card_generation_prompt` (変更不要 - __init__.py が再エクスポート) |

---

## 7. 信頼性レベルサマリー

| 項目 | 信頼性 | 根拠 |
|------|--------|------|
| ディレクトリ構造 (`prompts/`) | 🔵 | 設計ヒアリング Q3 で確定 |
| `__init__.py` 共通エクスポート | 🔵 | Python パッケージの標準手法 |
| `generate.py` 既存移行 | 🔵 | 既存 `prompts.py` (96行) をそのまま移行 |
| `grading.py` SM-2 定義 | 🔵 | REQ-SM-003, 設計ヒアリング Q4, api-endpoints.md グレード定義表 |
| `grading.py` JSON 出力形式 | 🔵 | api-endpoints.md GradeAnswerResponse 仕様 |
| `advice.py` ReviewSummary 対応 | 🔵 | interfaces.py ReviewSummary, 設計ヒアリング Q5 |
| `advice.py` JSON 出力形式 | 🔵 | api-endpoints.md LearningAdviceResponse 仕様 |
| import パス後方互換性 | 🔵 | `__init__.py` 再エクスポートによる標準手法 |
| 既存テスト保護 | 🔵 | REQ-SM-405, import パス互換維持 |
| セキュリティ（インジェクション防止） | 🟡 | NFR-SM-102 から推測、プロンプト層自体はサニタイズ対象外 |
| 空 tag_performance 処理 | 🟡 | 設計文書に明記なし、妥当な推測 |

### 統計

- 🔵 **青信号**: 9件 (82%)
- 🟡 **黄信号**: 2件 (18%)
- 🔴 **赤信号**: 0件 (0%)

**信頼性指標**: 91 (タスクファイルと一致)
