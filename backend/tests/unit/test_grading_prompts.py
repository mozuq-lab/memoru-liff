"""回答採点プロンプトモジュール テスト (TC-005 ~ TC-008, TC-014, TC-016, TC-021, TC-023).

grading.py の SM-2 グレード定義・採点プロンプト生成・エクスポートシンボルを確認する。
"""
# 【テスト前準備】: conftest.py が sys.path に backend/src を追加し、
#   services.prompts パッケージが import 可能な状態にする
# 【環境初期化】: ENVIRONMENT=test で Lambda 固有の環境変数が不要


class TestSM2GradeDefinitions:
    """TC-005: SM-2 グレード定義の存在確認."""

    def test_sm2_grade_definitions_contain_all_grades(self):
        """SM-2 グレード定義文字列が全グレード (0-5) を含むこと.

        # 【テスト目的】: SM-2 グレード定義文字列が全グレード (0-5) を含むことを確認
        # 【テスト内容】: SM2_GRADE_DEFINITIONS 定数の内容を検証
        # 【期待される動作】: 0から5までの全グレードが定義テキストに含まれる
        # 🔵 REQ-SM-003、設計ヒアリング Q4 から確定
        """
        from services.prompts.grading import SM2_GRADE_DEFINITIONS

        # 【検証項目】: SM2_GRADE_DEFINITIONS が文字列であること
        # 🔵 タスク定義で文字列定数と明記
        assert isinstance(SM2_GRADE_DEFINITIONS, str)  # 【確認内容】: str 型で定義されていること

        # 【検証項目】: 全グレード番号 (0-5) が含まれること
        # 🔵 api-endpoints.md グレード定義表と一致
        for grade in range(6):
            assert f"{grade}" in SM2_GRADE_DEFINITIONS, f"グレード {grade} が SM2_GRADE_DEFINITIONS に含まれていない"
            # 【確認内容】: グレード 0 から 5 が全て定義テキストに含まれること


class TestGradingSystemPromptContent:
    """TC-006: システムプロンプトに SM-2 定義が含まれる."""

    def test_grading_system_prompt_content(self):
        """GRADING_SYSTEM_PROMPT が SM-2 基準と JSON 出力指示を含むこと.

        # 【テスト目的】: GRADING_SYSTEM_PROMPT が SM-2 基準と JSON 出力指示を含むことを確認
        # 【テスト内容】: システムプロンプト定数の内容を検証
        # 【期待される動作】: SM-2 関連情報と JSON 出力形式指示が含まれる
        # 🔵 タスクファイルの grading.py 設計仕様から確定
        """
        from services.prompts.grading import GRADING_SYSTEM_PROMPT

        # 【検証項目】: 文字列型で非空であること
        # 🔵 基本チェック
        assert isinstance(GRADING_SYSTEM_PROMPT, str)  # 【確認内容】: str 型で定義されていること
        assert len(GRADING_SYSTEM_PROMPT) > 0  # 【確認内容】: 空でないこと

        # 【検証項目】: グレード関連キーワードが含まれること
        # 🔵 SM-2 基準を AI に指示するために必要
        prompt_lower = GRADING_SYSTEM_PROMPT.lower()
        assert "grade" in prompt_lower or "sm-2" in prompt_lower  # 【確認内容】: SM-2 グレード関連の指示があること

        # 【検証項目】: JSON 出力形式の指示が含まれること
        # 🔵 API レスポンス形式 (api-endpoints.md) に合わせた出力指示
        assert (
            "JSON" in GRADING_SYSTEM_PROMPT
            or "json" in GRADING_SYSTEM_PROMPT
            or "{" in GRADING_SYSTEM_PROMPT
        )  # 【確認内容】: JSON 形式での出力を AI に指示していること


class TestGetGradingPromptJapanese:
    """TC-007: 日本語採点プロンプト生成."""

    def test_get_grading_prompt_japanese(self):
        """日本語での回答採点プロンプトが正しく生成されること.

        # 【テスト目的】: 日本語設定で採点プロンプトが正しく生成されることを確認
        # 【テスト内容】: get_grading_prompt を日本語パラメータで呼び出し、出力を検証
        # 【期待される動作】: card_front, card_back, user_answer, 言語指示がプロンプトに含まれる
        # 🔵 タスクファイルの grading.py 仕様と要件定義書 2.2 節から確定
        """
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
        assert isinstance(prompt, str)  # 【確認内容】: str 型が返ること

        # 【検証項目】: 問題文が含まれること
        # 🔵 AI が採点対象を認識するために必要
        assert "日本の首都は？" in prompt  # 【確認内容】: card_front がプロンプトに埋め込まれること

        # 【検証項目】: 正解が含まれること
        # 🔵 AI が正解を参照して採点するために必要
        assert "東京" in prompt  # 【確認内容】: card_back がプロンプトに埋め込まれること

        # 【検証項目】: ユーザー回答が含まれること
        # 🔵 AI が採点対象の回答を認識するために必要
        assert "東京です" in prompt  # 【確認内容】: user_answer がプロンプトに埋め込まれること

        # 【検証項目】: 日本語応答指示が含まれること
        # 🔵 language="ja" 時の言語指示
        assert "Japanese" in prompt or "日本語" in prompt  # 【確認内容】: 日本語での採点結果を指示していること


class TestGetGradingPromptEnglish:
    """TC-008: 英語採点プロンプト生成."""

    def test_get_grading_prompt_english(self):
        """英語での回答採点プロンプトが正しく生成されること.

        # 【テスト目的】: 英語設定で採点プロンプトが正しく生成されることを確認
        # 【テスト内容】: get_grading_prompt を英語パラメータで呼び出し、言語指示を検証
        # 【期待される動作】: "English" 応答指示がプロンプトに含まれる
        # 🔵 タスクファイルの grading.py 仕様から確定
        """
        from services.prompts.grading import get_grading_prompt

        # 【テストデータ準備】: 英語フラッシュカードでの完全正解ケース
        prompt = get_grading_prompt(
            card_front="What is the capital of France?",
            card_back="Paris",
            user_answer="Paris",
            language="en",
        )

        # 【検証項目】: 英語応答指示が含まれること
        # 🔵 language="en" 時の言語指示
        assert "English" in prompt  # 【確認内容】: 英語での採点結果を指示していること

        # 【検証項目】: 入力値が含まれること
        # 🔵 基本的な埋め込み確認
        assert "What is the capital of France?" in prompt  # 【確認内容】: card_front が埋め込まれること
        assert "Paris" in prompt  # 【確認内容】: card_back と user_answer が埋め込まれること


class TestGradingPromptLanguageFallback:
    """TC-014: language フォールバック（未知の言語値）."""

    def test_grading_prompt_language_fallback(self):
        """未知の language 値で日本語にフォールバックすること.

        # 【テスト目的】: 未知の language 値で例外が発生せずフォールバックすることを確認
        # 【テスト内容】: language="fr" で get_grading_prompt を呼び出し、フォールバック動作を検証
        # 【期待される動作】: エラーなしで日本語フォールバックが適用される
        # 🟡 要件定義書 4.7 節、タスクファイルの .get() フォールバック仕様から推測
        """
        from services.prompts.grading import get_grading_prompt

        # 【テストデータ準備】: サポート外の言語コード
        # 【前提条件確認】: Language 型は Literal["ja", "en"] だが、ランタイムでは型強制なし
        prompt = get_grading_prompt(
            card_front="Q",
            card_back="A",
            user_answer="A",
            language="fr",  # type: ignore[arg-type]
        )

        # 【検証項目】: エラーなしでプロンプトが生成されること
        # 🟡 ランタイムでの型チェックなし前提の推測
        assert isinstance(prompt, str)  # 【確認内容】: 例外なしで str が返ること

        # 【検証項目】: 日本語フォールバックが適用されること
        # 🟡 タスクファイルの .get() 実装から推測
        assert "Japanese" in prompt  # 【確認内容】: 未知の言語で日本語にフォールバックすること


class TestGradingPromptDefaultLanguage:
    """TC-016: デフォルト language 値."""

    def test_grading_prompt_default_language(self):
        """language パラメータ省略時にデフォルト "ja" が適用されること.

        # 【テスト目的】: language 省略時にデフォルト値 "ja" が適用されることを確認
        # 【テスト内容】: language パラメータなしで get_grading_prompt を呼び出す
        # 【期待される動作】: 日本語指示がプロンプトに含まれる
        # 🔵 タスクファイルのシグネチャ定義、要件定義書 4.4 節から確定
        """
        from services.prompts.grading import get_grading_prompt

        # 【実際の処理実行】: language パラメータを省略
        prompt = get_grading_prompt(
            card_front="Q",
            card_back="A",
            user_answer="A",
        )

        # 【検証項目】: エラーなしでプロンプトが生成されること
        # 🔵 デフォルト値テスト
        assert isinstance(prompt, str)  # 【確認内容】: str 型が返ること

        # 【検証項目】: 日本語指示が含まれること（デフォルト "ja"）
        # 🔵 シグネチャの language="ja" デフォルト
        assert "Japanese" in prompt  # 【確認内容】: デフォルトで日本語指示が含まれること


class TestGradingExports:
    """TC-021: grading.py エクスポートシンボルの型確認."""

    def test_grading_exports(self):
        """grading.py のエクスポートシンボルが全て正しい型であること.

        # 【テスト目的】: grading.py の全エクスポートシンボルが正しい型であることを確認
        # 【テスト内容】: grading.py から全シンボルを import し、型を検証
        # 【期待される動作】: callable と str 型が正しく設定されている
        # 🔵 タスクファイル 2 節、要件定義書 2.2 節から確定
        """
        from services.prompts.grading import (
            get_grading_prompt,
            GRADING_SYSTEM_PROMPT,
            SM2_GRADE_DEFINITIONS,
        )

        # 【検証項目】: get_grading_prompt が呼び出し可能であること
        # 🔵 関数エクスポート
        assert callable(get_grading_prompt)  # 【確認内容】: 関数として利用可能なこと

        # 【検証項目】: GRADING_SYSTEM_PROMPT が非空文字列であること
        # 🔵 定数エクスポート
        assert isinstance(GRADING_SYSTEM_PROMPT, str)  # 【確認内容】: str 型で定義されていること
        assert len(GRADING_SYSTEM_PROMPT) > 0  # 【確認内容】: 空でないこと

        # 【検証項目】: SM2_GRADE_DEFINITIONS が非空文字列であること
        # 🔵 定数エクスポート
        assert isinstance(SM2_GRADE_DEFINITIONS, str)  # 【確認内容】: str 型で定義されていること
        assert len(SM2_GRADE_DEFINITIONS) > 0  # 【確認内容】: 空でないこと


class TestGradingSystemPromptJsonFields:
    """TC-023: GRADING_SYSTEM_PROMPT に JSON レスポンス形式が指示されている."""

    def test_grading_system_prompt_json_fields(self):
        """GRADING_SYSTEM_PROMPT が JSON レスポンス形式（grade, reasoning, feedback）を指示すること.

        # 【テスト目的】: GRADING_SYSTEM_PROMPT に JSON レスポンスフィールド名が含まれることを確認
        # 【テスト内容】: システムプロンプトに grade, reasoning, feedback の各フィールドが指示されているか検証
        # 【期待される動作】: 3つのフィールド名が全て含まれる
        # 🔵 タスクファイルの GRADING_SYSTEM_PROMPT、api-endpoints.md GradeAnswerResponse
        """
        from services.prompts.grading import GRADING_SYSTEM_PROMPT

        # 【検証項目】: "grade" フィールドが指示されていること
        # 🔵 api-endpoints.md の GradeAnswerResponse 仕様
        assert "grade" in GRADING_SYSTEM_PROMPT.lower()  # 【確認内容】: grade フィールドが指示されていること

        # 【検証項目】: "reasoning" フィールドが指示されていること
        # 🔵 api-endpoints.md の GradeAnswerResponse 仕様
        assert "reasoning" in GRADING_SYSTEM_PROMPT.lower()  # 【確認内容】: reasoning フィールドが指示されていること

        # 【検証項目】: "feedback" フィールドが指示されていること
        # 🔵 api-endpoints.md の GradeAnswerResponse 仕様
        assert "feedback" in GRADING_SYSTEM_PROMPT.lower()  # 【確認内容】: feedback フィールドが指示されていること
