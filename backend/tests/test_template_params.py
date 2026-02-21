"""Tests for SAM template parameters and environment variables.

TASK-0044: LINE ID トークン検証 + httpx 統一
対象テストケース: TC-17, TC-18
"""

import os
import yaml
import pytest


# 【テスト前準備】: CloudFormation 固有タグ (!Ref, !Sub, !If 等) を処理する
# カスタム YAML ローダーを定義する
# SAM テンプレートには CloudFormation 固有のタグが含まれており、
# yaml.safe_load では処理できないため、カスタムコンストラクタを登録する
class CloudFormationLoader(yaml.SafeLoader):
    """CloudFormation/SAM テンプレートを読み込むための YAML ローダー."""
    pass


def _cf_tag_constructor(loader, node):
    """CloudFormation 固有タグ（単一引数）を処理するコンストラクタ."""
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    elif isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node, deep=True)


def _cf_multi_constructor(loader, tag_suffix, node):
    """CloudFormation 固有タグ（マルチ引数）を処理するコンストラクタ."""
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    elif isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node, deep=True)


# CloudFormation 固有タグを登録
for tag in ['!Ref', '!Sub', '!If', '!Equals', '!Not', '!And', '!Or',
            '!Select', '!Split', '!Join', '!FindInMap', '!GetAtt',
            '!Base64', '!Condition', '!ImportValue', '!Transform']:
    CloudFormationLoader.add_constructor(tag, _cf_tag_constructor)

# マルチタグコンストラクタを追加（不明タグに対応）
CloudFormationLoader.add_multi_constructor('!', _cf_multi_constructor)


class TestSAMTemplateLineChannelId:
    """TC-17〜TC-18: SAM テンプレートの LineChannelId パラメータ・環境変数テスト."""

    @pytest.fixture
    def template(self):
        """SAM テンプレートを読み込む.

        【テスト前準備】: template.yaml を解析して辞書として返す
        【環境初期化】: CloudFormation 固有タグに対応したカスタムローダーで YAML を解析する
        """
        template_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "template.yaml",
        )
        with open(template_path, "r") as f:
            return yaml.load(f, Loader=CloudFormationLoader)

    def test_line_channel_id_parameter_exists(self, template):
        """TC-17: SAM テンプレートに LineChannelId パラメータが定義されていることを確認する.

        【テスト目的】: SAM テンプレートの Parameters セクションに LineChannelId が存在することを検証
        【テスト内容】:
            1. template.yaml を読み込む
            2. Parameters セクションに LineChannelId が存在することを確認
            3. Type が String であることを確認
        【期待される動作】: LineChannelId パラメータが正しく定義されている
        🔵 信頼性レベル: 青信号 - note.md 3.6 の SAM テンプレート要件に基づく
        """
        # 【初期条件設定】: テンプレートが読み込まれていることを確認
        assert "Parameters" in template, (
            "template.yaml should have Parameters section"
        )  # 【確認内容】: Parameters セクションが存在する 🔵

        params = template["Parameters"]

        # 【結果検証】: LineChannelId パラメータが存在することを確認
        assert "LineChannelId" in params, (
            "template.yaml should have LineChannelId parameter. "
            "Add it to Parameters section for LINE ID token verification."
        )  # 【確認内容】: LineChannelId パラメータが Parameters セクションに存在する 🔵

        # 【確認内容】: LineChannelId の Type が String であることを確認
        assert params["LineChannelId"]["Type"] == "String", (
            "LineChannelId should be of type String"
        )  # 🔵

    def test_line_channel_id_env_var_in_globals_or_api_function(self, template):
        """TC-18: SAM テンプレートの環境変数に LINE_CHANNEL_ID が設定されていることを確認する.

        【テスト目的】: LINE_CHANNEL_ID 環境変数が Lambda 関数に設定されていることを検証
        【テスト内容】:
            1. template.yaml を読み込む
            2. Globals または ApiFunction の Environment.Variables に LINE_CHANNEL_ID が存在することを確認
        【期待される動作】: LINE_CHANNEL_ID が環境変数として定義されている
        🔵 信頼性レベル: 青信号 - note.md 3.6 の LINE_CHANNEL_ID 環境変数要件に基づく
        """
        # 【初期条件設定】: Globals セクションの環境変数を取得
        globals_env = (
            template.get("Globals", {})
            .get("Function", {})
            .get("Environment", {})
            .get("Variables", {})
        )

        # 【初期条件設定】: ApiFunction の環境変数を取得
        api_function_env = (
            template.get("Resources", {})
            .get("ApiFunction", {})
            .get("Properties", {})
            .get("Environment", {})
            .get("Variables", {})
        )

        # 【実際の処理実行】: LINE_CHANNEL_ID の存在を確認
        has_line_channel_id = (
            "LINE_CHANNEL_ID" in globals_env
            or "LINE_CHANNEL_ID" in api_function_env
        )

        # 【結果検証】: LINE_CHANNEL_ID が設定されていることを確認
        assert has_line_channel_id, (
            "LINE_CHANNEL_ID should be defined in Globals.Function.Environment.Variables "
            "or Resources.ApiFunction.Properties.Environment.Variables. "
            "This is required for LINE ID token verification."
        )  # 【確認内容】: LINE_CHANNEL_ID が Globals または ApiFunction に環境変数として設定されている 🔵
