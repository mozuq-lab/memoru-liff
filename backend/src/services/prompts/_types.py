"""プロンプトモジュール共通型定義.

各プロンプトモジュール (generate.py, grading.py, advice.py) で共通して使用する
型定義と定数を提供する。

# 【機能概要】: プロンプトパッケージ内の共通型・定数を一元管理する
# 【設計方針】: DRY 原則に従い、重複定義を排除して保守性を向上させる
# 【モジュール独立性】: このモジュールは標準ライブラリのみに依存し、
#                     他のプロジェクトモジュールには依存しない
# 🔵 既存実装の重複 Language 型定義を統合（Green フェーズの改善課題 #1, #2）
"""

from typing import Literal


# 【型定義】: 出力言語の型エイリアス
# 【設計方針】: Literal["ja", "en"] で静的型チェックを強制し、
#             ランタイムでのサポート外言語はフォールバックで安全に処理する
# 【再利用性】: generate.py, grading.py, advice.py の全モジュールで共有
# 🔵 既存 generate.py, grading.py, advice.py の各 Language 型定義を統合
Language = Literal["ja", "en"]


# 【定数定義】: 言語コードから AI 応答言語指示へのマッピング
# 【設計方針】: サポート外の言語は .get(language, default) で日本語にフォールバック
#             (要件定義書 4.7 節のフォールバック仕様)
# 【再利用性】: grading.py と advice.py で同一の辞書定義を共有
# 🔵 既存 grading.py と advice.py の重複 _LANGUAGE_INSTRUCTION を統合
# 🟡 デフォルト（フォールバック）を日本語にする仕様は要件定義書 4.7 節から推測
LANGUAGE_INSTRUCTION: dict[str, str] = {
    "ja": "Respond in Japanese.",
    "en": "Respond in English.",
}

# 【定数定義】: フォールバック時の言語指示（日本語）
# 【調整可能性】: デフォルト言語の変更が必要な場合はここを修正する
# 🟡 日本語をデフォルトとする仕様は要件定義書のデフォルト値定義から推測
DEFAULT_LANGUAGE_INSTRUCTION = LANGUAGE_INSTRUCTION["ja"]
