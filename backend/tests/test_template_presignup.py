"""Tests for the signup-allowlist SAM template resources.

対象: docs/design/signup-allowlist/architecture.md タスク #1 (SAM リソース)。
既存 test_template_params.py の CloudFormationLoader 流儀を踏襲する。
"""

import os

import pytest
import yaml


# CloudFormation 固有タグ (!Ref, !Sub, !If 等) を処理するカスタム YAML ローダー。
# test_template_params.py と同一の実装 (テストファイル間の依存を避けるため複製)。
class CloudFormationLoader(yaml.SafeLoader):
    """CloudFormation/SAM テンプレートを読み込むための YAML ローダー."""

    pass


def _cf_tag_constructor(loader, node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    elif isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node, deep=True)


def _cf_multi_constructor(loader, tag_suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    elif isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node, deep=True)


for tag in [
    "!Ref",
    "!Sub",
    "!If",
    "!Equals",
    "!Not",
    "!And",
    "!Or",
    "!Select",
    "!Split",
    "!Join",
    "!FindInMap",
    "!GetAtt",
    "!Base64",
    "!Condition",
    "!ImportValue",
    "!Transform",
]:
    CloudFormationLoader.add_constructor(tag, _cf_tag_constructor)

CloudFormationLoader.add_multi_constructor("!", _cf_multi_constructor)


@pytest.fixture
def template():
    """SAM テンプレートを読み込む。"""
    template_path = os.path.join(os.path.dirname(__file__), "..", "template.yaml")
    with open(template_path, "r") as f:
        return yaml.load(f, Loader=CloudFormationLoader)


class TestCognitoUserPoolArnParameter:
    def test_parameter_exists_with_string_type(self, template):
        params = template["Parameters"]
        assert "CognitoUserPoolArn" in params
        assert params["CognitoUserPoolArn"]["Type"] == "String"

    def test_default_is_empty_string(self, template):
        assert template["Parameters"]["CognitoUserPoolArn"]["Default"] == ""


class TestProdRequiresCognitoUserPoolArnRule:
    def test_rule_exists(self, template):
        assert "ProdRequiresCognitoUserPoolArn" in template["Rules"]

    def test_rule_condition_targets_prod_environment(self, template):
        rule = template["Rules"]["ProdRequiresCognitoUserPoolArn"]
        assert rule["RuleCondition"] == ["Environment", "prod"]

    def test_rule_asserts_non_empty_cognito_user_pool_arn(self, template):
        rule = template["Rules"]["ProdRequiresCognitoUserPoolArn"]
        assertions = rule["Assertions"]
        assert len(assertions) == 1
        # !Not [!Equals [!Ref CognitoUserPoolArn, ""]] はカスタムローダーで
        # ネストしたシーケンスとして構築される。
        assert assertions[0]["Assert"] == [["CognitoUserPoolArn", ""]]


class TestHasCognitoUserPoolArnCondition:
    def test_condition_exists(self, template):
        assert "HasCognitoUserPoolArn" in template["Conditions"]

    def test_condition_checks_non_empty(self, template):
        condition = template["Conditions"]["HasCognitoUserPoolArn"]
        assert condition == [["CognitoUserPoolArn", ""]]


class TestSignupAllowlistTable:
    def test_table_exists(self, template):
        assert "SignupAllowlistTable" in template["Resources"]

    def test_table_type_is_dynamodb(self, template):
        table = template["Resources"]["SignupAllowlistTable"]
        assert table["Type"] == "AWS::DynamoDB::Table"

    def test_table_name_uses_environment_suffix(self, template):
        table = template["Resources"]["SignupAllowlistTable"]
        assert (
            table["Properties"]["TableName"] == "memoru-signup-allowlist-${Environment}"
        )

    def test_table_billing_mode_is_pay_per_request(self, template):
        table = template["Resources"]["SignupAllowlistTable"]
        assert table["Properties"]["BillingMode"] == "PAY_PER_REQUEST"

    def test_table_partition_key_is_identifier_string(self, template):
        table = template["Resources"]["SignupAllowlistTable"]
        attr_defs = table["Properties"]["AttributeDefinitions"]
        assert {"AttributeName": "identifier", "AttributeType": "S"} in attr_defs

        key_schema = table["Properties"]["KeySchema"]
        assert key_schema == [{"AttributeName": "identifier", "KeyType": "HASH"}]

    def test_table_ttl_enabled_on_ttl_attribute(self, template):
        table = template["Resources"]["SignupAllowlistTable"]
        ttl_spec = table["Properties"]["TimeToLiveSpecification"]
        assert ttl_spec == {"AttributeName": "ttl", "Enabled": True}

    def test_table_retain_policies(self, template):
        table = template["Resources"]["SignupAllowlistTable"]
        assert table["DeletionPolicy"] == "Retain"
        assert table["UpdateReplacePolicy"] == "Retain"

    def test_table_point_in_time_recovery_enabled(self, template):
        table = template["Resources"]["SignupAllowlistTable"]
        pitr = table["Properties"]["PointInTimeRecoverySpecification"]
        assert pitr["PointInTimeRecoveryEnabled"] is True

    def test_table_sse_kms_enabled(self, template):
        table = template["Resources"]["SignupAllowlistTable"]
        sse = table["Properties"]["SSESpecification"]
        assert sse["SSEEnabled"] is True
        assert sse["SSEType"] == "KMS"

    def test_table_deletion_protection_conditional_on_prod(self, template):
        table = template["Resources"]["SignupAllowlistTable"]
        deletion_protection = table["Properties"]["DeletionProtectionEnabled"]
        assert deletion_protection == ["IsProd", True, False]

    def test_table_has_environment_and_application_tags(self, template):
        table = template["Resources"]["SignupAllowlistTable"]
        tag_keys = {tag["Key"] for tag in table["Properties"]["Tags"]}
        assert tag_keys == {"Environment", "Application"}


class TestPreSignupFunction:
    def test_function_exists(self, template):
        assert "PreSignupFunction" in template["Resources"]

    def test_function_type_is_serverless_function(self, template):
        fn = template["Resources"]["PreSignupFunction"]
        assert fn["Type"] == "AWS::Serverless::Function"

    def test_function_name_uses_environment_suffix(self, template):
        fn = template["Resources"]["PreSignupFunction"]
        assert fn["Properties"]["FunctionName"] == "memoru-presignup-${Environment}"

    def test_handler_uses_src_relative_dotted_path(self, template):
        fn = template["Resources"]["PreSignupFunction"]
        assert fn["Properties"]["CodeUri"] == "src/"
        assert fn["Properties"]["Handler"] == "auth.pre_signup.handler"

    def test_timeout_is_5_seconds(self, template):
        """Cognito のトリガー応答制限 (5秒・変更不可) と一致させる。"""
        fn = template["Resources"]["PreSignupFunction"]
        assert fn["Properties"]["Timeout"] == 5

    def test_reserved_concurrent_executions_is_10(self, template):
        fn = template["Resources"]["PreSignupFunction"]
        assert fn["Properties"]["ReservedConcurrentExecutions"] == 10

    def test_no_api_events_attached(self, template):
        """API Gateway ルートを持たない (Cognito からのみ起動される)。"""
        fn = template["Resources"]["PreSignupFunction"]
        assert "Events" not in fn["Properties"]

    def test_allowlist_table_env_var_references_table(self, template):
        fn = template["Resources"]["PreSignupFunction"]
        env_vars = fn["Properties"]["Environment"]["Variables"]
        assert env_vars["ALLOWLIST_TABLE"] == "SignupAllowlistTable"

    def test_policies_grant_only_get_and_put_item_on_allowlist_table(self, template):
        fn = template["Resources"]["PreSignupFunction"]
        policies = fn["Properties"]["Policies"]
        assert len(policies) == 1
        statement = policies[0]["Statement"][0]
        assert statement["Effect"] == "Allow"
        assert set(statement["Action"]) == {"dynamodb:GetItem", "dynamodb:PutItem"}
        assert statement["Resource"] == "SignupAllowlistTable.Arn"

    def test_function_has_environment_and_application_tags(self, template):
        fn = template["Resources"]["PreSignupFunction"]
        tags = fn["Properties"]["Tags"]
        assert tags.get("Environment") == "Environment"
        assert tags.get("Application") == "memoru"


class TestPreSignupFunctionLogGroup:
    def test_log_group_exists(self, template):
        assert "PreSignupFunctionLogGroup" in template["Resources"]

    def test_log_group_targets_presignup_function(self, template):
        log_group = template["Resources"]["PreSignupFunctionLogGroup"]
        assert log_group["Type"] == "AWS::Logs::LogGroup"
        assert (
            log_group["Properties"]["LogGroupName"]
            == "/aws/lambda/${PreSignupFunction}"
        )

    def test_retention_follows_prod_convention(self, template):
        log_group = template["Resources"]["PreSignupFunctionLogGroup"]
        retention = log_group["Properties"]["RetentionInDays"]
        assert retention == ["IsProd", 90, 14]


class TestPreSignupInvokePermission:
    def test_permission_exists(self, template):
        assert "PreSignupInvokePermission" in template["Resources"]

    def test_permission_type_is_lambda_permission(self, template):
        perm = template["Resources"]["PreSignupInvokePermission"]
        assert perm["Type"] == "AWS::Lambda::Permission"

    def test_permission_conditioned_on_has_cognito_user_pool_arn(self, template):
        perm = template["Resources"]["PreSignupInvokePermission"]
        assert perm["Condition"] == "HasCognitoUserPoolArn"

    def test_permission_principal_is_cognito_idp(self, template):
        perm = template["Resources"]["PreSignupInvokePermission"]
        assert perm["Properties"]["Principal"] == "cognito-idp.amazonaws.com"

    def test_permission_source_arn_references_cognito_user_pool_arn_param(
        self, template
    ):
        perm = template["Resources"]["PreSignupInvokePermission"]
        assert perm["Properties"]["SourceArn"] == "CognitoUserPoolArn"

    def test_permission_targets_presignup_function(self, template):
        perm = template["Resources"]["PreSignupInvokePermission"]
        assert perm["Properties"]["FunctionName"] == "PreSignupFunction"

    def test_permission_action_is_invoke_function(self, template):
        perm = template["Resources"]["PreSignupInvokePermission"]
        assert perm["Properties"]["Action"] == "lambda:InvokeFunction"


class TestPreSignupFunctionArnOutput:
    def test_output_exists(self, template):
        assert "PreSignupFunctionArn" in template["Outputs"]

    def test_output_value_references_presignup_function_arn(self, template):
        output = template["Outputs"]["PreSignupFunctionArn"]
        assert output["Value"] == "PreSignupFunction.Arn"
