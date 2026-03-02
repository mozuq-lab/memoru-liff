"""カード生成プロンプトモジュール テスト (TC-001 ~ TC-004, TC-020).

generate.py のテストと既存 import パスの後方互換性を確認する。
"""
# 【テスト前準備】: conftest.py が sys.path に backend/src を追加し、
#   services.prompts パッケージが import 可能な状態にする
# 【環境初期化】: ENVIRONMENT=test で Lambda 固有の環境変数が不要


class TestJapanesePromptGeneration:
    """TC-001: 日本語カード生成プロンプト（既存互換）."""

    def test_japanese_prompt_generation(self):
        """日本語カード生成プロンプトが正しく生成されること.

        # 【テスト目的】: generate.py の日本語プロンプト生成が既存 prompts.py と完全互換であることを確認
        # 【テスト内容】: get_card_generation_prompt を日本語パラメータで呼び出し、出力文字列を検証
        # 【期待される動作】: 既存テストと同一のアサーションがすべて通過する
        # 🔵 既存テスト test_bedrock.py::test_japanese_prompt_generation から移植
        """
        # 【テストデータ準備】: 既存テストと同じ入力パラメータを使用
        # 【初期条件設定】: services.prompts.generate モジュールが import 可能であること
        from services.prompts.generate import get_card_generation_prompt

        # 【実際の処理実行】: get_card_generation_prompt を日本語設定で呼び出す
        prompt = get_card_generation_prompt(
            input_text="テスト入力テキスト",
            card_count=5,
            difficulty="medium",
            language="ja",
        )

        # 【結果検証】: 日本語テンプレートのキーフレーズが含まれていること
        # 【期待値確認】: 既存 prompts.py と同じ出力が得られること

        # 【検証項目】: プロンプトが文字列であること
        # 🔵 基本的な型チェック
        assert isinstance(prompt, str)  # 【確認内容】: str 型が返ること

        # 【検証項目】: 日本語テンプレートの専門家フレーズが含まれること
        # 🔵 既存テストと同一
        assert "フラッシュカード作成の専門家" in prompt  # 【確認内容】: 日本語プロンプトテンプレートが正しく使われていること

        # 【検証項目】: カード枚数が正しく埋め込まれること
        # 🔵 既存テストと同一
        assert "5枚作成" in prompt  # 【確認内容】: card_count=5 が "5枚作成" として埋め込まれること

        # 【検証項目】: 入力テキストが正しく埋め込まれること
        # 🔵 既存テストと同一
        assert "テスト入力テキスト" in prompt  # 【確認内容】: input_text がプロンプトに埋め込まれること

        # 【検証項目】: 難易度が正しく埋め込まれること
        # 🔵 既存テストと同一
        assert "medium" in prompt  # 【確認内容】: difficulty がプロンプトに埋め込まれること


class TestEnglishPromptGeneration:
    """TC-002: 英語カード生成プロンプト（既存互換）."""

    def test_english_prompt_generation(self):
        """英語カード生成プロンプトが正しく生成されること.

        # 【テスト目的】: generate.py の英語プロンプト生成が既存 prompts.py と完全互換であることを確認
        # 【テスト内容】: get_card_generation_prompt を英語パラメータで呼び出し、出力文字列を検証
        # 【期待される動作】: 既存テストと同一のアサーションがすべて通過する
        # 🔵 既存テスト test_bedrock.py::test_english_prompt_generation から移植
        """
        from services.prompts.generate import get_card_generation_prompt

        # 【テストデータ準備】: 英語テンプレートを確認するための入力
        prompt = get_card_generation_prompt(
            input_text="Test input text",
            card_count=3,
            difficulty="hard",
            language="en",
        )

        # 【検証項目】: 英語テンプレートの専門家フレーズが含まれること
        # 🔵 既存テストと同一
        assert "expert at creating flashcards" in prompt  # 【確認内容】: 英語テンプレートが使用されていること

        # 【検証項目】: カード枚数が正しく埋め込まれること
        assert "3 flashcards" in prompt  # 【確認内容】: card_count=3 が英語フレーズに埋め込まれること

        # 【検証項目】: 入力テキストが正しく埋め込まれること
        # 🔵 既存テストと同一
        assert "Test input text" in prompt  # 【確認内容】: input_text がプロンプトに埋め込まれること

        # 【検証項目】: 難易度が正しく埋め込まれること
        # 🔵 既存テストと同一
        assert "hard" in prompt  # 【確認内容】: difficulty="hard" がプロンプトに埋め込まれること


class TestDifficultyLevels:
    """TC-003: 全難易度レベル対応（既存互換）."""

    def test_difficulty_levels(self):
        """全難易度レベルがプロンプトに含まれること.

        # 【テスト目的】: 全難易度レベルでプロンプトが正しく生成されることを確認
        # 【テスト内容】: easy/medium/hard の3パターンで get_card_generation_prompt を呼び出す
        # 【期待される動作】: 各難易度名がプロンプト文字列に含まれる
        # 🔵 既存テスト test_bedrock.py::test_difficulty_levels から移植
        """
        from services.prompts.generate import get_card_generation_prompt

        # 【テストデータ準備】: 全難易度パターンの網羅テスト
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
            assert difficulty in prompt  # 【確認内容】: difficulty がプロンプトに反映されること


class TestGenerateExports:
    """TC-004: generate.py エクスポートシンボルの存在確認."""

    def test_generate_exports(self):
        """generate.py のエクスポートシンボルが全て利用可能であること.

        # 【テスト目的】: generate.py のエクスポートシンボルが全て利用可能であることを確認
        # 【テスト内容】: generate.py から各シンボルを import し、型と存在を検証
        # 【期待される動作】: 全シンボルが正しい型で存在する
        # 🔵 既存 prompts.py のシンボル一覧から確定
        """
        from services.prompts.generate import (
            get_card_generation_prompt,
            DIFFICULTY_GUIDELINES,
            DifficultyLevel,
            Language,
        )

        # 【検証項目】: get_card_generation_prompt が呼び出し可能であること
        # 🔵 既存 prompts.py の関数
        assert callable(get_card_generation_prompt)  # 【確認内容】: 関数として利用可能なこと

        # 【検証項目】: DIFFICULTY_GUIDELINES が辞書型であること
        # 🔵 既存 prompts.py の定数
        assert isinstance(DIFFICULTY_GUIDELINES, dict)  # 【確認内容】: dict 型で定義されていること

        # 【検証項目】: 全難易度キーが存在すること
        # 🔵 既存 prompts.py の DIFFICULTY_GUIDELINES と同一
        assert "easy" in DIFFICULTY_GUIDELINES  # 【確認内容】: "easy" キーが存在すること
        assert "medium" in DIFFICULTY_GUIDELINES  # 【確認内容】: "medium" キーが存在すること
        assert "hard" in DIFFICULTY_GUIDELINES  # 【確認内容】: "hard" キーが存在すること


class TestBackwardCompatibleImport:
    """TC-020: __init__.py 経由の既存 import パス互換性."""

    def test_backward_compatible_import(self):
        """既存の from services.prompts import get_card_generation_prompt が動作すること.

        # 【テスト目的】: 既存の import パスが __init__.py 経由で動作することを確認
        # 【テスト内容】: パッケージ経由と直接 import の両方でシンボルを取得し、同一性を検証
        # 【期待される動作】: 両方の import パスが同じオブジェクトを参照する
        # 🔵 要件定義書 3 節 互換性要件、REQ-SM-402 から確定
        """
        # 【実際の処理実行】: 2つの import パスでシンボルを取得
        from services.prompts import get_card_generation_prompt as from_package
        from services.prompts.generate import get_card_generation_prompt as from_module

        # 【検証項目】: 両方の import パスが同じオブジェクトを参照すること
        # 🔵 __init__.py の再エクスポートにより保証
        assert from_package is from_module  # 【確認内容】: 同一オブジェクトが参照されること

        # 【検証項目】: パッケージ経由で生成したプロンプトが正しいこと
        # 🔵 既存互換性の実用テスト
        prompt = from_package(
            input_text="テスト",
            card_count=1,
            difficulty="easy",
            language="ja",
        )
        assert isinstance(prompt, str)  # 【確認内容】: str 型のプロンプトが返ること
        assert len(prompt) > 0  # 【確認内容】: 空でないプロンプトが返ること


class TestRewriteInstructions:
    """TC-030: 清書/推敲モードの指示が含まれることを確認."""

    def test_japanese_prompt_contains_polish_instructions(self):
        """日本語プロンプトに清書・整形指示が含まれること."""
        from services.prompts.generate import get_card_generation_prompt

        prompt = get_card_generation_prompt(
            input_text="テスト入力テキスト",
            card_count=3,
            difficulty="medium",
            language="ja",
        )

        assert "清書・整形" in prompt
        assert "新規情報を創作・追加しないこと" in prompt
        assert "原文の意味を維持" in prompt

    def test_english_prompt_contains_polish_instructions(self):
        """英語プロンプトに清書・整形指示が含まれること."""
        from services.prompts.generate import get_card_generation_prompt

        prompt = get_card_generation_prompt(
            input_text="Test input text",
            card_count=3,
            difficulty="medium",
            language="en",
        )

        assert "polished" in prompt
        assert "Do not add new information" in prompt
        assert "Preserve the original meaning" in prompt

    def test_japanese_prompt_uses_user_input_as_source(self):
        """日本語プロンプトがユーザー入力を素材として扱うこと."""
        from services.prompts.generate import get_card_generation_prompt

        input_text = "光合成は植物が光エネルギーを使って二酸化炭素と水から糖を作るプロセスです。"
        prompt = get_card_generation_prompt(
            input_text=input_text,
            card_count=2,
            difficulty="easy",
            language="ja",
        )

        assert "ユーザーが入力したテキスト" in prompt
        assert input_text in prompt

    def test_english_prompt_uses_user_input_as_source(self):
        """英語プロンプトがユーザー入力を素材として扱うこと."""
        from services.prompts.generate import get_card_generation_prompt

        input_text = "Photosynthesis is the process by which plants use light energy."
        prompt = get_card_generation_prompt(
            input_text=input_text,
            card_count=2,
            difficulty="easy",
            language="en",
        )

        assert "user-provided text" in prompt
        assert input_text in prompt

    def test_short_input_included_in_prompt(self):
        """短い入力テキスト（最小長）がプロンプトに含まれること."""
        from services.prompts.generate import get_card_generation_prompt

        short_input = "ABC12"
        prompt = get_card_generation_prompt(
            input_text=short_input,
            card_count=1,
            difficulty="easy",
            language="ja",
        )

        assert short_input in prompt
        assert "清書・整形" in prompt

    def test_long_input_with_bullets_included_in_prompt(self):
        """箇条書き・改行を含む長い入力がプロンプトに含まれること."""
        from services.prompts.generate import get_card_generation_prompt

        long_input = (
            "SRSとは:\n"
            "- 間隔反復システム\n"
            "- 記憶の定着に効果的\n"
            "- 復習タイミングを自動調整\n" * 10
        )
        prompt = get_card_generation_prompt(
            input_text=long_input,
            card_count=5,
            difficulty="hard",
            language="ja",
        )

        assert long_input in prompt
        assert "清書・整形" in prompt
