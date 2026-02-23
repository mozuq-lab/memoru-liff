"""学習アドバイスプロンプトモジュール テスト (TC-009 ~ TC-011, TC-013, TC-015, TC-017 ~ TC-019, TC-022, TC-024).

advice.py のシステムプロンプト・プロンプト生成・エクスポートシンボルを確認する。
"""
# 【テスト前準備】: conftest.py が sys.path に backend/src を追加し、
#   services.prompts パッケージが import 可能な状態にする
# 【環境初期化】: ENVIRONMENT=test で Lambda 固有の環境変数が不要


class TestAdviceSystemPromptExists:
    """TC-009: advice.py システムプロンプトの存在."""

    def test_advice_system_prompt_exists(self):
        """ADVICE_SYSTEM_PROMPT が正しく定義されていること.

        # 【テスト目的】: ADVICE_SYSTEM_PROMPT が存在し、必要な内容を含むことを確認
        # 【テスト内容】: システムプロンプト定数の型と内容を検証
        # 【期待される動作】: 非空文字列で JSON 出力形式指示を含む
        # 🔵 タスクファイルの advice.py 仕様、REQ-SM-004 から確定
        """
        from services.prompts.advice import ADVICE_SYSTEM_PROMPT

        # 【検証項目】: 文字列型で非空であること
        # 🔵 基本チェック
        assert isinstance(ADVICE_SYSTEM_PROMPT, str)  # 【確認内容】: str 型で定義されていること
        assert len(ADVICE_SYSTEM_PROMPT) > 0  # 【確認内容】: 空でないこと

        # 【検証項目】: JSON 出力形式の指示が含まれること
        # 🔵 API レスポンス形式 (api-endpoints.md) に合わせた出力指示
        assert (
            "JSON" in ADVICE_SYSTEM_PROMPT
            or "json" in ADVICE_SYSTEM_PROMPT
            or "{" in ADVICE_SYSTEM_PROMPT
        )  # 【確認内容】: JSON 形式での出力を AI に指示していること


class TestGetAdvicePromptWithDict:
    """TC-010: 辞書形式の統計データでプロンプト生成."""

    def test_get_advice_prompt_with_dict(self):
        """辞書形式の復習統計でプロンプトが正しく生成されること.

        # 【テスト目的】: dict 形式の復習統計データからプロンプトが正しく生成されることを確認
        # 【テスト内容】: get_advice_prompt を dict 形式の統計データで呼び出し、出力を検証
        # 【期待される動作】: 統計値がプロンプト文字列に埋め込まれる
        # 🔵 タスクファイルの advice.py 仕様、設計ヒアリング Q5 から確定
        """
        from services.prompts.advice import get_advice_prompt

        # 【テストデータ準備】: 典型的な学習統計データ（dict 形式）
        review_stats = {
            "total_reviews": 100,
            "average_grade": 3.5,
            "total_cards": 50,
            "cards_due_today": 10,
            "streak_days": 7,
            "tag_performance": {"noun": 3.8, "verb": 3.2},
        }

        # 【実際の処理実行】: dict 形式の統計でプロンプト生成
        prompt = get_advice_prompt(review_stats, language="ja")

        # 【検証項目】: 戻り値が文字列であること
        # 🔵 基本型チェック
        assert isinstance(prompt, str)  # 【確認内容】: str 型が返ること

        # 【検証項目】: total_reviews が埋め込まれること
        # 🔵 統計データの主要指標
        assert "100" in prompt  # 【確認内容】: total_reviews=100 がプロンプトに反映されること

        # 【検証項目】: average_grade が埋め込まれること
        # 🔵 統計データの主要指標
        assert "3.5" in prompt  # 【確認内容】: average_grade=3.5 がプロンプトに反映されること


class TestGetAdvicePromptWithReviewSummary:
    """TC-011: ReviewSummary dataclass でプロンプト生成."""

    def test_get_advice_prompt_with_review_summary(self):
        """ReviewSummary dataclass 形式の統計データでプロンプトが正しく生成されること.

        # 【テスト目的】: ReviewSummary dataclass でプロンプトが正しく生成されることを確認
        # 【テスト内容】: get_advice_prompt を ReviewSummary インスタンスで呼び出し、出力を検証
        # 【期待される動作】: dataclass のフィールド値がプロンプトに反映される
        # 🔵 タスクファイルの advice.py 仕様、interfaces.py ReviewSummary 定義から確定
        """
        from services.prompts.advice import get_advice_prompt
        from services.ai_service import ReviewSummary

        # 【テストデータ準備】: ReviewSummary dataclass を使用
        summary = ReviewSummary(
            total_reviews=100,
            average_grade=3.5,
            total_cards=50,
            cards_due_today=10,
            streak_days=7,
            tag_performance={"noun": 3.8, "verb": 3.2},
            recent_review_dates=["2026-02-20"],
        )

        # 【実際の処理実行】: ReviewSummary で英語プロンプト生成
        prompt = get_advice_prompt(summary, language="en")

        # 【検証項目】: 戻り値が文字列であること
        # 🔵 基本型チェック
        assert isinstance(prompt, str)  # 【確認内容】: str 型が返ること

        # 【検証項目】: total_reviews が埋め込まれること
        # 🔵 dataclass フィールドの値が反映されること
        assert "100" in prompt  # 【確認内容】: ReviewSummary.total_reviews がプロンプトに反映されること

        # 【検証項目】: 英語応答指示が含まれること
        # 🔵 language="en" 時の言語指示
        assert "English" in prompt  # 【確認内容】: 英語での回答指示が含まれること


class TestGetAdvicePromptContainsImprovementFocus:
    """TC-013: プロンプトに弱点分析の指示が含まれる."""

    def test_get_advice_prompt_contains_improvement_focus(self):
        """プロンプトが弱点分野への焦点指示を含むこと.

        # 【テスト目的】: プロンプトが弱点分析の指示を含むことを確認
        # 【テスト内容】: 低い平均グレードの統計でプロンプトを生成し、改善指示キーワードを検証
        # 【期待される動作】: "struggling", "weak", "improve" のいずれかが含まれる
        # 🔵 タスクファイルの advice.py テンプレート内容から確定
        """
        from services.prompts.advice import get_advice_prompt

        # 【テストデータ準備】: 低い平均グレードの統計（成績が悪い学生を想定）
        stats = {
            "total_reviews": 50,
            "average_grade": 2.0,
            "total_cards": 25,
            "cards_due_today": 8,
            "streak_days": 2,
            "tag_performance": {"weak_area": 1.5},
        }

        # 【実際の処理実行】: 低い成績の統計でプロンプト生成
        prompt = get_advice_prompt(stats)

        # 【検証項目】: 改善指示のキーワードが含まれること
        # 🔵 タスクファイルのテンプレートに "struggling" が含まれている
        prompt_lower = prompt.lower()
        assert (
            "struggling" in prompt_lower
            or "weak" in prompt_lower
            or "improve" in prompt_lower
        )  # 【確認内容】: 弱点改善に焦点を当てた指示が含まれること


class TestAdvicePromptLanguageFallback:
    """TC-015: advice.py で未知の language 値フォールバック."""

    def test_advice_prompt_language_fallback(self):
        """advice.py で未知の language 値で日本語にフォールバックすること.

        # 【テスト目的】: advice.py で未知の language 値のフォールバック動作を確認
        # 【テスト内容】: language="de" で get_advice_prompt を呼び出し、フォールバックを検証
        # 【期待される動作】: 日本語フォールバックが適用される
        # 🟡 要件定義書 4.7 節から推測
        """
        from services.prompts.advice import get_advice_prompt

        # 【テストデータ準備】: 最小限の統計データとサポート外の言語コード
        stats = {
            "total_reviews": 10,
            "average_grade": 3.0,
            "total_cards": 5,
            "cards_due_today": 2,
            "streak_days": 1,
            "tag_performance": {},
        }

        # 【実際の処理実行】: サポート外の言語コードでプロンプト生成
        prompt = get_advice_prompt(stats, language="de")  # type: ignore[arg-type]

        # 【検証項目】: エラーなしでプロンプトが生成されること
        # 🟡 ランタイムでの型チェックなし前提の推測
        assert isinstance(prompt, str)  # 【確認内容】: 例外なしで str が返ること

        # 【検証項目】: 日本語フォールバックが適用されること
        # 🟡 タスクファイルの .get() 実装から推測
        assert "Japanese" in prompt  # 【確認内容】: 未知の言語で日本語にフォールバックすること


class TestAdvicePromptDefaultLanguage:
    """TC-017: advice.py デフォルト language 値."""

    def test_advice_prompt_default_language(self):
        """advice.py で language パラメータ省略時にデフォルト "ja" が適用されること.

        # 【テスト目的】: advice.py で language 省略時にデフォルト "ja" が適用されることを確認
        # 【テスト内容】: language なしで get_advice_prompt を呼び出す
        # 【期待される動作】: 日本語指示がプロンプトに含まれる
        # 🔵 タスクファイルのシグネチャ定義から確定
        """
        from services.prompts.advice import get_advice_prompt

        # 【テストデータ準備】: 最小限の統計データ
        stats = {
            "total_reviews": 10,
            "average_grade": 3.0,
            "total_cards": 5,
            "cards_due_today": 2,
            "streak_days": 1,
            "tag_performance": {},
        }

        # 【実際の処理実行】: language パラメータを省略
        prompt = get_advice_prompt(stats)

        # 【検証項目】: 日本語指示が含まれること（デフォルト "ja"）
        # 🔵 シグネチャの language="ja" デフォルト
        assert isinstance(prompt, str)  # 【確認内容】: str 型が返ること
        assert "Japanese" in prompt  # 【確認内容】: デフォルトで日本語指示が含まれること


class TestAdvicePromptEmptyTagPerformance:
    """TC-018: advice.py 空の tag_performance."""

    def test_advice_prompt_empty_tag_performance(self):
        """tag_performance が空辞書でもプロンプトが正常に生成されること.

        # 【テスト目的】: 空の tag_performance でプロンプトが正常に生成されることを確認
        # 【テスト内容】: tag_performance を空辞書にしてプロンプト生成を実行
        # 【期待される動作】: エラーなしでプロンプトが生成される
        # 🟡 要件定義書 4.6 節のエッジケースから推測
        """
        from services.prompts.advice import get_advice_prompt

        # 【テストデータ準備】: 新規ユーザーを想定した最小限データ（タグなし）
        stats = {
            "total_reviews": 0,
            "average_grade": 0.0,
            "total_cards": 0,
            "cards_due_today": 0,
            "streak_days": 0,
            "tag_performance": {},  # 空辞書
        }

        # 【実際の処理実行】: 空の tag_performance でプロンプト生成
        prompt = get_advice_prompt(stats)

        # 【検証項目】: エラーなしで文字列が生成されること
        # 🟡 空データでの堅牢性は設計文書に明記なし
        assert isinstance(prompt, str)  # 【確認内容】: 例外なしで str が返ること
        assert len(prompt) > 0  # 【確認内容】: 空でないプロンプトが返ること


class TestAdvicePromptZeroStats:
    """TC-019: advice.py ゼロ値の統計データ."""

    def test_advice_prompt_zero_stats(self):
        """全ての統計値がゼロでもプロンプトが正常に生成されること.

        # 【テスト目的】: 全ゼロ統計データでプロンプトが正常に生成されることを確認
        # 【テスト内容】: 全数値をゼロに設定してプロンプト生成を実行
        # 【期待される動作】: ゼロ値が正しくフォーマットされ、エラーなしで生成される
        # 🟡 要件定義書のエッジケースとタスクファイルの実装仕様から推測
        """
        from services.prompts.advice import get_advice_prompt

        # 【テストデータ準備】: 全ゼロの統計データ（学習未開始ユーザー）
        stats = {
            "total_reviews": 0,
            "average_grade": 0.0,
            "total_cards": 0,
            "cards_due_today": 0,
            "streak_days": 0,
            "tag_performance": {},
        }

        # 【実際の処理実行】: 全ゼロの統計でプロンプト生成
        prompt = get_advice_prompt(stats)

        # 【検証項目】: プロンプトが生成されること
        # 🟡 ゼロ値での堅牢性
        assert isinstance(prompt, str)  # 【確認内容】: 例外なしで str が返ること

        # 【検証項目】: average_grade が "0.0" としてフォーマットされること
        # 🟡 タスクファイルの :.1f フォーマット仕様から推測
        assert "0.0" in prompt  # 【確認内容】: average_grade=0.0 が "0.0" として埋め込まれること


class TestAdviceExports:
    """TC-022: advice.py エクスポートシンボルの型確認."""

    def test_advice_exports(self):
        """advice.py のエクスポートシンボルが全て正しい型であること.

        # 【テスト目的】: advice.py の全エクスポートシンボルが正しい型であることを確認
        # 【テスト内容】: advice.py から全シンボルを import し、型を検証
        # 【期待される動作】: callable と str 型が正しく設定されている
        # 🔵 タスクファイル 5 節、要件定義書 2.3 節から確定
        """
        from services.prompts.advice import (
            get_advice_prompt,
            ADVICE_SYSTEM_PROMPT,
        )

        # 【検証項目】: get_advice_prompt が呼び出し可能であること
        # 🔵 関数エクスポート
        assert callable(get_advice_prompt)  # 【確認内容】: 関数として利用可能なこと

        # 【検証項目】: ADVICE_SYSTEM_PROMPT が非空文字列であること
        # 🔵 定数エクスポート
        assert isinstance(ADVICE_SYSTEM_PROMPT, str)  # 【確認内容】: str 型で定義されていること
        assert len(ADVICE_SYSTEM_PROMPT) > 0  # 【確認内容】: 空でないこと


class TestAdviceSystemPromptJsonFields:
    """TC-024: ADVICE_SYSTEM_PROMPT に JSON レスポンス形式が指示されている."""

    def test_advice_system_prompt_json_fields(self):
        """ADVICE_SYSTEM_PROMPT が JSON レスポンス形式（advice_text, weak_areas, recommendations）を指示すること.

        # 【テスト目的】: ADVICE_SYSTEM_PROMPT に JSON レスポンスフィールド名が含まれることを確認
        # 【テスト内容】: システムプロンプトに advice_text, weak_areas, recommendations が指示されているか検証
        # 【期待される動作】: 3つのフィールド名が全て含まれる
        # 🔵 タスクファイルの ADVICE_SYSTEM_PROMPT、api-endpoints.md LearningAdviceResponse
        """
        from services.prompts.advice import ADVICE_SYSTEM_PROMPT

        # 【検証項目】: "advice_text" フィールドが指示されていること
        # 🔵 api-endpoints.md の LearningAdviceResponse 仕様
        assert "advice_text" in ADVICE_SYSTEM_PROMPT  # 【確認内容】: advice_text フィールドが指示されていること

        # 【検証項目】: "weak_areas" フィールドが指示されていること
        # 🔵 api-endpoints.md の LearningAdviceResponse 仕様
        assert "weak_areas" in ADVICE_SYSTEM_PROMPT  # 【確認内容】: weak_areas フィールドが指示されていること

        # 【検証項目】: "recommendations" フィールドが指示されていること
        # 🔵 api-endpoints.md の LearningAdviceResponse 仕様
        assert "recommendations" in ADVICE_SYSTEM_PROMPT  # 【確認内容】: recommendations フィールドが指示されていること
