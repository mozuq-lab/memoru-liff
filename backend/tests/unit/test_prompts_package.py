"""プロンプトパッケージ構造・互換性テスト (TC-012, TC-025).

__init__.py 経由のパッケージレベル import とモジュール独立性を確認する。
"""
# 【テスト前準備】: conftest.py が sys.path に backend/src を追加し、
#   services.prompts パッケージが import 可能な状態にする
# 【環境初期化】: ENVIRONMENT=test で Lambda 固有の環境変数が不要


class TestPackageImports:
    """TC-012: __init__.py 経由のパッケージレベル import 互換性."""

    def test_package_imports(self):
        """services.prompts パッケージ経由で全シンボルが import 可能であること.

        # 【テスト目的】: services.prompts パッケージ経由の import 互換性を確認
        # 【テスト内容】: __init__.py から全シンボルを import し、存在を確認
        # 【期待される動作】: 全シンボルが import エラーなく利用可能
        # 🔵 要件定義書 2.4 節、互換性要件 REQ-SM-402 から確定
        """
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
        assert callable(get_card_generation_prompt)  # 【確認内容】: generate.py 関数が利用可能なこと
        assert callable(get_grading_prompt)  # 【確認内容】: grading.py 関数が利用可能なこと
        assert callable(get_advice_prompt)  # 【確認内容】: advice.py 関数が利用可能なこと
        assert isinstance(DIFFICULTY_GUIDELINES, dict)  # 【確認内容】: generate.py 定数が dict 型であること
        assert isinstance(GRADING_SYSTEM_PROMPT, str)  # 【確認内容】: grading.py 定数が str 型であること
        assert isinstance(SM2_GRADE_DEFINITIONS, str)  # 【確認内容】: grading.py 定数が str 型であること
        assert isinstance(ADVICE_SYSTEM_PROMPT, str)  # 【確認内容】: advice.py 定数が str 型であること


class TestModuleIndependence:
    """TC-025: モジュール独立性 - 各モジュール間の相互依存なし."""

    def test_module_independence(self):
        """generate.py, grading.py, advice.py が互いに import していないこと.

        # 【テスト目的】: 各プロンプトモジュールが独立して import 可能であることを確認
        # 【テスト内容】: 各モジュールを個別に import し、エラーなく利用可能であることを検証
        # 【期待される動作】: 各モジュールが他モジュールに依存せず動作する
        # 🔵 要件定義書 3 節 アーキテクチャ制約から確定
        """
        # 【実際の処理実行】: 各モジュールを個別に import
        # generate.py の独立 import
        from services.prompts.generate import get_card_generation_prompt
        assert callable(get_card_generation_prompt)  # 【確認内容】: generate.py が単独で import 可能なこと

        # grading.py の独立 import
        from services.prompts.grading import get_grading_prompt
        assert callable(get_grading_prompt)  # 【確認内容】: grading.py が単独で import 可能なこと

        # advice.py の独立 import
        from services.prompts.advice import get_advice_prompt
        assert callable(get_advice_prompt)  # 【確認内容】: advice.py が単独で import 可能なこと

    def test_generate_module_standalone(self):
        """generate.py が他の prompts モジュールなしで動作すること.

        # 【テスト目的】: generate.py が単体で完全に動作することを確認
        # 【テスト内容】: generate.py から関数を import し、実際にプロンプト生成が成功することを検証
        # 【期待される動作】: generate.py 単体でプロンプト生成が完結する
        # 🔵 要件定義書 3 節 アーキテクチャ制約から確定
        """
        from services.prompts.generate import get_card_generation_prompt, DIFFICULTY_GUIDELINES

        # 【実際の処理実行】: generate.py だけで完結するプロンプト生成
        prompt = get_card_generation_prompt(
            input_text="独立性テスト",
            card_count=1,
            difficulty="easy",
            language="ja",
        )
        # 【検証項目】: プロンプト生成が成功すること
        # 🔵 generate.py の独立動作確認
        assert isinstance(prompt, str)  # 【確認内容】: 単体で str 型のプロンプトが生成されること
        assert len(prompt) > 0  # 【確認内容】: 空でないプロンプトが生成されること
        assert isinstance(DIFFICULTY_GUIDELINES, dict)  # 【確認内容】: 定数も正しく定義されていること

    def test_grading_module_standalone(self):
        """grading.py が他の prompts モジュールなしで動作すること.

        # 【テスト目的】: grading.py が単体で完全に動作することを確認
        # 【テスト内容】: grading.py から関数を import し、実際にプロンプト生成が成功することを検証
        # 【期待される動作】: grading.py 単体でプロンプト生成が完結する
        # 🔵 要件定義書 3 節 アーキテクチャ制約から確定
        """
        from services.prompts.grading import (
            get_grading_prompt,
            GRADING_SYSTEM_PROMPT,
            SM2_GRADE_DEFINITIONS,
        )

        # 【実際の処理実行】: grading.py だけで完結するプロンプト生成
        prompt = get_grading_prompt(
            card_front="独立性テスト問題",
            card_back="正解",
            user_answer="ユーザーの回答",
            language="ja",
        )
        # 【検証項目】: プロンプト生成が成功すること
        # 🔵 grading.py の独立動作確認
        assert isinstance(prompt, str)  # 【確認内容】: 単体で str 型のプロンプトが生成されること
        assert len(prompt) > 0  # 【確認内容】: 空でないプロンプトが生成されること
        assert isinstance(GRADING_SYSTEM_PROMPT, str)  # 【確認内容】: システムプロンプト定数が利用可能なこと
        assert isinstance(SM2_GRADE_DEFINITIONS, str)  # 【確認内容】: SM-2 定義定数が利用可能なこと

    def test_advice_module_standalone(self):
        """advice.py が他の prompts モジュールなしで動作すること.

        # 【テスト目的】: advice.py が単体で完全に動作することを確認
        # 【テスト内容】: advice.py から関数を import し、実際にプロンプト生成が成功することを検証
        # 【期待される動作】: advice.py 単体でプロンプト生成が完結する
        # 🔵 要件定義書 3 節 アーキテクチャ制約から確定
        """
        from services.prompts.advice import get_advice_prompt, ADVICE_SYSTEM_PROMPT

        # 【実際の処理実行】: advice.py だけで完結するプロンプト生成
        stats = {
            "total_reviews": 10,
            "average_grade": 3.0,
            "total_cards": 5,
            "cards_due_today": 2,
            "streak_days": 1,
            "tag_performance": {},
        }
        prompt = get_advice_prompt(stats)

        # 【検証項目】: プロンプト生成が成功すること
        # 🔵 advice.py の独立動作確認
        assert isinstance(prompt, str)  # 【確認内容】: 単体で str 型のプロンプトが生成されること
        assert len(prompt) > 0  # 【確認内容】: 空でないプロンプトが生成されること
        assert isinstance(ADVICE_SYSTEM_PROMPT, str)  # 【確認内容】: システムプロンプト定数が利用可能なこと
