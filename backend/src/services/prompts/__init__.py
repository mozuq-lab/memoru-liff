"""プロンプトパッケージ - 全モジュールの共通エクスポート.

既存の `from services.prompts import ...` の import パスを維持するため、
各サブモジュールのシンボルを再エクスポートする。

# 【機能概要】: prompts パッケージの公開インターフェースを定義する
# 【実装方針】: __all__ で全シンボルを再エクスポートし、後方互換性を維持
# 【テスト対応】: TC-012（パッケージ import）, TC-020（既存 import パス互換性）
# 🔵 要件定義書 2.4 節、互換性要件 REQ-SM-402 から確定
"""

# 【generate.py エクスポート】: カード生成プロンプト関連
# 🔵 既存 services.prompts の後方互換性維持
from .generate import (
    get_card_generation_prompt,
    CARD_GENERATION_SYSTEM_PROMPT,
    DIFFICULTY_GUIDELINES,
    DifficultyLevel,
    Language,
)

# 【grading.py エクスポート】: 回答採点プロンプト関連（新規）
# 🔵 タスクファイルの __init__.py 仕様から確定
from .grading import (
    get_grading_prompt,
    GRADING_SYSTEM_PROMPT,
    SM2_GRADE_DEFINITIONS,
)

# 【advice.py エクスポート】: 学習アドバイスプロンプト関連（新規）
# 🔵 タスクファイルの __init__.py 仕様から確定
from .advice import (
    get_advice_prompt,
    ADVICE_SYSTEM_PROMPT,
)

# 【refine.py エクスポート】: カード補足・改善プロンプト関連
# 🔵 設計文書 architecture.md プロンプト設計より
from .refine import (
    get_refine_user_prompt,
    REFINE_SYSTEM_PROMPT,
)

# 【公開インターフェース】: パッケージが公開する全シンボルのリスト
# 🔵 要件定義書 2.4 節のエクスポートシンボル一覧から確定
__all__ = [
    # generate.py から
    "get_card_generation_prompt",
    "CARD_GENERATION_SYSTEM_PROMPT",
    "DIFFICULTY_GUIDELINES",
    "DifficultyLevel",
    "Language",
    # grading.py から
    "get_grading_prompt",
    "GRADING_SYSTEM_PROMPT",
    "SM2_GRADE_DEFINITIONS",
    # advice.py から
    "get_advice_prompt",
    "ADVICE_SYSTEM_PROMPT",
    # refine.py から
    "get_refine_user_prompt",
    "REFINE_SYSTEM_PROMPT",
]
