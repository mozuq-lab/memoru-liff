"""Unit tests for UpdateCardRequest interval validation.

【テスト目的】: UpdateCardRequest の interval バリデーションをテスト
【テスト内容】: Pydantic v2 の ge=1, le=365 制約が正しく動作することを検証
【期待される動作】: 範囲外の値で ValidationError、範囲内の値で正常生成
🔵 要件定義 REQ-101, REQ-102, 受け入れ基準 TC-101-01〜TC-102-B01 より
"""

import pytest
from pydantic import ValidationError

from models.card import UpdateCardRequest


class TestUpdateCardRequestInterval:
    """Tests for UpdateCardRequest interval validation.

    【テスト目的】: UpdateCardRequest の interval フィールドが ge=1, le=365 制約を
    正しく適用することを確認する。
    🔵 要件定義 REQ-101, REQ-102 より
    """

    # =========================================================================
    # 正常系テストケース（境界値）
    # =========================================================================

    def test_interval_1_is_valid(self):
        """TC-B01: interval=1（最小値）でバリデーションが通る。

        【テスト目的】: ge=1 制約の下限値 1 が正常に受け付けられることを確認
        【テスト内容】: UpdateCardRequest に interval=1 を渡してバリデーションを実行
        【期待される動作】: ValidationError が発生せず、interval=1 のオブジェクトが生成される
        🔵 信頼性レベル: 要件定義 REQ-101, EDGE-101, TC-101-B01 より
        """
        # 【テストデータ準備】: ge=1 の下限境界値 1 を使用する
        # 【初期条件設定】: interval=1 は「翌日復習」を意味する最小値
        request = UpdateCardRequest(interval=1)

        # 【結果検証】: interval が 1 として設定されることを確認
        assert request.interval == 1  # 【確認内容】: 下限境界値 1 が正常に受け付けられること 🔵

    def test_interval_365_is_valid(self):
        """TC-B02: interval=365（最大値）でバリデーションが通る。

        【テスト目的】: le=365 制約の上限値 365 が正常に受け付けられることを確認
        【テスト内容】: UpdateCardRequest に interval=365 を渡してバリデーションを実行
        【期待される動作】: ValidationError が発生せず、interval=365 のオブジェクトが生成される
        🔵 信頼性レベル: 要件定義 REQ-102, EDGE-102, TC-102-B01 より
        """
        # 【テストデータ準備】: le=365 の上限境界値 365 を使用する
        # 【初期条件設定】: interval=365 は「1年後復習」を意味する最大値
        request = UpdateCardRequest(interval=365)

        # 【結果検証】: interval が 365 として設定されることを確認
        assert request.interval == 365  # 【確認内容】: 上限境界値 365 が正常に受け付けられること 🔵

    def test_interval_7_is_valid(self):
        """TC-N01(モデル層): interval=7 で正常にオブジェクトが生成される。

        【テスト目的】: 典型的な使用値 7 が正常に受け付けられることを確認
        【テスト内容】: UpdateCardRequest に interval=7 を渡してバリデーションを実行
        【期待される動作】: ValidationError が発生せず、interval=7 のオブジェクトが生成される
        🔵 信頼性レベル: 要件定義 REQ-101, REQ-102, TC-003-01 より
        """
        # 【テストデータ準備】: プリセットボタン「7日」の典型的な使用値
        request = UpdateCardRequest(interval=7)

        # 【結果検証】: interval が 7 として設定されることを確認
        assert request.interval == 7  # 【確認内容】: 典型的な値 7 が正常に受け付けられること 🔵

    def test_interval_none_is_valid(self):
        """TC-B04: interval=None（未指定）でバリデーションが通る。

        【テスト目的】: Optional フィールドとして None が正常に受け付けられることを確認
        【テスト内容】: UpdateCardRequest に interval を指定せず（None）にしてバリデーション実行
        【期待される動作】: ValidationError が発生せず、interval=None のオブジェクトが生成される
        🔵 信頼性レベル: 要件定義 REQ-401, REQ-402 より
        """
        # 【テストデータ準備】: interval 未指定のリクエスト（既存動作と同じ）
        # 【初期条件設定】: interval なしで front のみを更新するシナリオ
        request = UpdateCardRequest(front="新しい問題文")

        # 【結果検証】: interval が None であることを確認
        assert request.interval is None  # 【確認内容】: interval 未指定時は None が設定されること 🔵
        assert request.front == "新しい問題文"  # 【確認内容】: 他のフィールドは正常に設定されること 🔵

    def test_interval_only_none_explicit(self):
        """TC-B04(明示的None): interval=None を明示的に指定してバリデーションが通る。

        【テスト目的】: interval=None の明示的指定が Optional フィールドとして受け付けられることを確認
        【テスト内容】: UpdateCardRequest に interval=None を明示的に指定してバリデーション実行
        【期待される動作】: ValidationError が発生せず、interval=None のオブジェクトが生成される
        🔵 信頼性レベル: 要件定義 REQ-401, REQ-402 より
        """
        # 【テストデータ準備】: interval=None を明示的に指定
        request = UpdateCardRequest(interval=None)

        # 【結果検証】: interval が None であることを確認
        assert request.interval is None  # 【確認内容】: None が正常に受け付けられること 🔵

    # =========================================================================
    # 異常系テストケース（バリデーションエラー）
    # =========================================================================

    def test_interval_0_raises_validation_error(self):
        """TC-E01: interval=0 で ValidationError が発生する。

        【テスト目的】: ge=1 制約に違反する値 0 が拒否されることを確認
        【テスト内容】: UpdateCardRequest に interval=0 を渡してバリデーションを実行
        【期待される動作】: pydantic.ValidationError が発生する
        🔵 信頼性レベル: 要件定義 REQ-101, TC-101-01 より
        """
        # 【テストデータ準備】: ge=1 制約に違反する値 0
        # 【初期条件設定】: 0 は「今日復習」を意味する無効な間隔
        with pytest.raises(ValidationError) as exc_info:
            UpdateCardRequest(interval=0)

        # 【結果検証】: ValidationError が発生し、interval フィールドのエラーが含まれることを確認
        errors = exc_info.value.errors()
        assert any(
            error["loc"] == ("interval",) for error in errors
        )  # 【確認内容】: interval フィールドのバリデーションエラーが発生すること 🔵

    def test_interval_minus_1_raises_validation_error(self):
        """TC-E02: interval=-1 で ValidationError が発生する。

        【テスト目的】: ge=1 制約に違反する負の値 -1 が拒否されることを確認
        【テスト内容】: UpdateCardRequest に interval=-1 を渡してバリデーションを実行
        【期待される動作】: pydantic.ValidationError が発生する
        🔵 信頼性レベル: 要件定義 REQ-101, TC-101-02 より
        """
        # 【テストデータ準備】: ge=1 制約に違反する負の値 -1
        # 【初期条件設定】: 負の復習間隔は論理的に意味がない
        with pytest.raises(ValidationError) as exc_info:
            UpdateCardRequest(interval=-1)

        # 【結果検証】: ValidationError が発生し、interval フィールドのエラーが含まれることを確認
        errors = exc_info.value.errors()
        assert any(
            error["loc"] == ("interval",) for error in errors
        )  # 【確認内容】: interval フィールドのバリデーションエラーが発生すること 🔵

    def test_interval_366_raises_validation_error(self):
        """TC-E03: interval=366 で ValidationError が発生する。

        【テスト目的】: le=365 制約に違反する値 366 が拒否されることを確認
        【テスト内容】: UpdateCardRequest に interval=366 を渡してバリデーションを実行
        【期待される動作】: pydantic.ValidationError が発生する
        🔵 信頼性レベル: 要件定義 REQ-102, TC-102-01 より
        """
        # 【テストデータ準備】: le=365 制約に違反する値 366
        # 【初期条件設定】: 366 は 1 年を超える非実用的な復習間隔
        with pytest.raises(ValidationError) as exc_info:
            UpdateCardRequest(interval=366)

        # 【結果検証】: ValidationError が発生し、interval フィールドのエラーが含まれることを確認
        errors = exc_info.value.errors()
        assert any(
            error["loc"] == ("interval",) for error in errors
        )  # 【確認内容】: interval フィールドのバリデーションエラーが発生すること 🔵

    def test_interval_string_raises_validation_error(self):
        """TC-E04: interval に文字列を指定して ValidationError が発生する。

        【テスト目的】: 整数以外の型（文字列）が拒否されることを確認
        【テスト内容】: UpdateCardRequest に interval="abc" を渡してバリデーションを実行
        【期待される動作】: pydantic.ValidationError が発生する
        🟡 信頼性レベル: Pydantic v2 の int バリデーション動作から妥当な推測
        """
        # 【テストデータ準備】: 整数以外の文字列 "abc"
        # 【初期条件設定】: 文字列の復習間隔は型の不整合
        with pytest.raises(ValidationError) as exc_info:
            UpdateCardRequest(interval="abc")

        # 【結果検証】: ValidationError が発生し、interval フィールドのエラーが含まれることを確認
        errors = exc_info.value.errors()
        assert any(
            error["loc"] == ("interval",) for error in errors
        )  # 【確認内容】: interval フィールドの型バリデーションエラーが発生すること 🟡

    def test_interval_float_with_fraction_raises_validation_error(self):
        """TC-E05: interval に小数（7.5）を指定して ValidationError が発生する。

        【テスト目的】: 整数に変換できない浮動小数点数が拒否されることを確認
        【テスト内容】: UpdateCardRequest に interval=7.5 を渡してバリデーションを実行
        【期待される動作】: pydantic.ValidationError が発生する（7.5 は整数に変換できない）
        🟡 信頼性レベル: Pydantic v2 の int バリデーション動作から妥当な推測
        """
        # 【テストデータ準備】: 整数に変換できない小数 7.5
        # 【初期条件設定】: 7.5 日という復習間隔は意味がない
        with pytest.raises(ValidationError) as exc_info:
            UpdateCardRequest(interval=7.5)

        # 【結果検証】: ValidationError が発生し、interval フィールドのエラーが含まれることを確認
        errors = exc_info.value.errors()
        assert any(
            error["loc"] == ("interval",) for error in errors
        )  # 【確認内容】: interval フィールドの型バリデーションエラーが発生すること 🟡

    # =========================================================================
    # 既存フィールドとの組み合わせ
    # =========================================================================

    def test_interval_with_front_back_is_valid(self):
        """TC-N04(モデル層): interval と front を同時に指定してバリデーションが通る。

        【テスト目的】: interval と既存フィールド（front）の同時指定が正常に受け付けられることを確認
        【テスト内容】: UpdateCardRequest に interval=14 と front="新しい問題文" を同時に指定
        【期待される動作】: ValidationError が発生せず、両フィールドが正しく設定される
        🔵 信頼性レベル: 設計文書 architecture.md 技術的制約セクションより
        """
        # 【テストデータ準備】: interval と front の同時指定
        # 【初期条件設定】: カード内容と復習間隔を同時に修正するユースケース
        request = UpdateCardRequest(front="新しい問題文", interval=14)

        # 【結果検証】: 両フィールドが正しく設定されることを確認
        assert request.front == "新しい問題文"  # 【確認内容】: front が正しく設定されること 🔵
        assert request.interval == 14  # 【確認内容】: interval が正しく設定されること 🔵
