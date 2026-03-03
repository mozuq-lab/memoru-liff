"""カード補足・改善プロンプトモジュール テスト."""


class TestRefinePromptBothInputs:
    """表面・裏面両方ある場合のプロンプト生成テスト."""

    def test_both_inputs_prompt(self):
        """表面・裏面両方ある場合に正しいプロンプトが生成されること."""
        from services.prompts.refine import get_refine_user_prompt

        prompt = get_refine_user_prompt(front="クロージャとは？", back="変数を覚えてる関数")
        assert "クロージャとは？" in prompt
        assert "変数を覚えてる関数" in prompt
        assert "問題文（表面）" in prompt
        assert "解答（裏面）" in prompt
        assert "JSON" in prompt


class TestRefinePromptFrontOnly:
    """表面のみの場合のプロンプト生成テスト."""

    def test_front_only_prompt(self):
        """表面のみの場合に正しいプロンプトが生成されること."""
        from services.prompts.refine import get_refine_user_prompt

        prompt = get_refine_user_prompt(front="クロージャとは？", back="")
        assert "クロージャとは？" in prompt
        assert "refined_back は空文字" in prompt
        assert "JSON" in prompt

    def test_front_only_with_whitespace_back(self):
        """裏面が空白のみの場合、表面のみプロンプトになること."""
        from services.prompts.refine import get_refine_user_prompt

        prompt = get_refine_user_prompt(front="テスト", back="   ")
        assert "refined_back は空文字" in prompt


class TestRefinePromptBackOnly:
    """裏面のみの場合のプロンプト生成テスト."""

    def test_back_only_prompt(self):
        """裏面のみの場合に正しいプロンプトが生成されること."""
        from services.prompts.refine import get_refine_user_prompt

        prompt = get_refine_user_prompt(front="", back="変数を覚えてる関数")
        assert "変数を覚えてる関数" in prompt
        assert "refined_front は空文字" in prompt
        assert "JSON" in prompt

    def test_back_only_with_whitespace_front(self):
        """表面が空白のみの場合、裏面のみプロンプトになること."""
        from services.prompts.refine import get_refine_user_prompt

        prompt = get_refine_user_prompt(front="   ", back="テスト回答")
        assert "refined_front は空文字" in prompt


class TestRefineSystemPrompt:
    """システムプロンプトのテスト."""

    def test_system_prompt_exists(self):
        """REFINE_SYSTEM_PROMPT が定義されていること."""
        from services.prompts.refine import REFINE_SYSTEM_PROMPT

        assert isinstance(REFINE_SYSTEM_PROMPT, str)
        assert len(REFINE_SYSTEM_PROMPT) > 0

    def test_system_prompt_contains_json_instruction(self):
        """システムプロンプトに JSON 出力指示が含まれること."""
        from services.prompts.refine import REFINE_SYSTEM_PROMPT

        assert "JSON" in REFINE_SYSTEM_PROMPT
        assert "refined_front" in REFINE_SYSTEM_PROMPT
        assert "refined_back" in REFINE_SYSTEM_PROMPT


class TestRefinePromptEnglish:
    """language="en" の英語プロンプトテスト."""

    def test_en_both_inputs_prompt(self):
        """英語で両方入力のプロンプトが生成されること."""
        from services.prompts.refine import get_refine_user_prompt

        prompt = get_refine_user_prompt(front="closure", back="a function that remembers variables", language="en")
        assert "closure" in prompt
        assert "a function that remembers variables" in prompt
        assert "JSON" in prompt
        # 英語テンプレートであること（日本語テンプレートのキーワードが含まれない）
        assert "問題文" not in prompt
        assert "解答" not in prompt

    def test_en_front_only_prompt(self):
        """英語で表面のみプロンプトが生成されること."""
        from services.prompts.refine import get_refine_user_prompt

        prompt = get_refine_user_prompt(front="closure", back="", language="en")
        assert "closure" in prompt
        assert "refined_back" in prompt
        assert "JSON" in prompt
        assert "問題文" not in prompt

    def test_en_back_only_prompt(self):
        """英語で裏面のみプロンプトが生成されること."""
        from services.prompts.refine import get_refine_user_prompt

        prompt = get_refine_user_prompt(front="", back="a function that remembers variables", language="en")
        assert "a function that remembers variables" in prompt
        assert "refined_front" in prompt
        assert "JSON" in prompt
        assert "解答" not in prompt

    def test_en_system_prompt(self):
        """英語のシステムプロンプトが返されること."""
        from services.prompts.refine import get_refine_system_prompt

        prompt = get_refine_system_prompt("en")
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "JSON" in prompt
        assert "refined_front" in prompt
        assert "refined_back" in prompt
        # 英語テンプレートであること
        assert "フラッシュカード" not in prompt

    def test_ja_system_prompt_default(self):
        """デフォルト（ja）のシステムプロンプトが日本語であること."""
        from services.prompts.refine import get_refine_system_prompt

        prompt = get_refine_system_prompt()
        assert "フラッシュカード" in prompt
        assert "JSON" in prompt

    def test_ja_backward_compatibility(self):
        """language="ja" で既存と同じ動作であること."""
        from services.prompts.refine import get_refine_user_prompt

        prompt = get_refine_user_prompt(front="クロージャとは？", back="変数を覚えてる関数", language="ja")
        assert "問題文（表面）" in prompt
        assert "解答（裏面）" in prompt


class TestRefineExportsFromPackage:
    """__init__.py 経由の import テスト."""

    def test_refine_exports_from_package(self):
        """パッケージ経由で refine シンボルが import できること."""
        from services.prompts import get_refine_user_prompt, get_refine_system_prompt

        assert callable(get_refine_user_prompt)
        assert callable(get_refine_system_prompt)

    def test_refine_exports_identity(self):
        """パッケージ経由と直接 import で同一オブジェクトであること."""
        from services.prompts import get_refine_user_prompt as from_package
        from services.prompts.refine import get_refine_user_prompt as from_module

        assert from_package is from_module

    def test_refine_system_prompt_export_identity(self):
        """get_refine_system_prompt がパッケージ経由と直接で同一であること."""
        from services.prompts import get_refine_system_prompt as from_package
        from services.prompts.refine import get_refine_system_prompt as from_module

        assert from_package is from_module
