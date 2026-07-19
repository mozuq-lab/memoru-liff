"""
TC-042: SAM テンプレート API ルート検証テスト

対応要件: REQ-V2-001, REQ-V2-002, REQ-V2-003, REQ-V2-004

テスト方針:
- backend/template.yaml を YAML としてパースし、ApiFunction の HttpApi イベント定義を静的に検証する
- backend/src/api/handler.py のソースコードから @app.<method>() デコレータのパスを正規表現で抽出し、
  SAM テンプレートとの整合性を検証する
- 3レイヤー（SAM / handler / frontend）の API パスが完全一致することを保証する
"""

import os
import re

import pytest
import yaml


TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "template.yaml"
)
HANDLER_PATH = os.path.join(
    os.path.dirname(__file__), "..", "src", "api", "handler.py"
)


# ---------------------------------------------------------------------------
# CloudFormation タグを処理できるカスタム YAML ローダー
# PyYAML の safe_load は !Ref / !Sub 等の CloudFormation 固有タグを
# デフォルトでは扱えないため、独自ローダーで全 ! タグを許容する。
# ---------------------------------------------------------------------------
class CFLoader(yaml.SafeLoader):
    """CloudFormation 固有タグ (!Ref, !Sub, !Equals など) を許容するローダー."""


def _cf_constructor(loader, tag_suffix, node):
    """CloudFormation 固有タグを Python オブジェクトに変換するコンストラクタ."""
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    elif isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)


CFLoader.add_multi_constructor("!", _cf_constructor)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def sam_template():
    """SAM テンプレートを読み込んでパースする fixture."""
    with open(TEMPLATE_PATH, "r") as f:
        return yaml.load(f, Loader=CFLoader)


@pytest.fixture(scope="module")
def api_events(sam_template):
    """ApiFunction の HttpApi イベントのみを抽出する fixture."""
    events = sam_template["Resources"]["ApiFunction"]["Properties"]["Events"]
    return {
        name: event
        for name, event in events.items()
        if event.get("Type") == "HttpApi"
    }


@pytest.fixture(scope="module")
def handler_routes():
    """handler.py から @app.<method>() デコレータのルート定義を抽出する fixture."""
    with open(HANDLER_PATH, "r") as f:
        content = f.read()
    pattern = r'@app\.(get|post|put|delete)\("([^"]+)"\)'
    matches = re.findall(pattern, content)
    return {(method.upper(), path) for method, path in matches}


# ---------------------------------------------------------------------------
# TC-042-08: 品質チェック - YAML 有効性
# ---------------------------------------------------------------------------


def test_template_is_valid_yaml(sam_template):
    """TC-042-08: 品質 - SAM テンプレートが有効な YAML としてパースできる"""
    assert sam_template is not None
    assert "Resources" in sam_template
    assert "ApiFunction" in sam_template["Resources"]


# ---------------------------------------------------------------------------
# TC-042-01: REQ-V2-001 - 設定更新エンドポイント パス検証
# ---------------------------------------------------------------------------


def test_update_user_event_path_is_users_me_settings(api_events):
    """TC-042-01: REQ-V2-001 - 設定更新イベントのパスが PUT /users/me/settings であること"""
    assert "UpdateUser" in api_events, "UpdateUser イベントが SAM テンプレートに存在すること"
    event = api_events["UpdateUser"]
    assert event["Properties"]["Path"] == "/users/me/settings", (
        f"UpdateUser のパスが '/users/me/settings' であること。"
        f" 実際: '{event['Properties']['Path']}'"
    )
    assert event["Properties"]["Method"] == "PUT", (
        f"UpdateUser のメソッドが 'PUT' であること。"
        f" 実際: '{event['Properties']['Method']}'"
    )


# ---------------------------------------------------------------------------
# TC-042-02: REQ-V2-002 - レビュー送信エンドポイント パス検証
# ---------------------------------------------------------------------------


def test_submit_review_event_path_has_card_id_parameter(api_events):
    """TC-042-02: REQ-V2-002 - レビュー送信イベントのパスが POST /reviews/{cardId} であること"""
    assert "SubmitReview" in api_events, "SubmitReview イベントが SAM テンプレートに存在すること"
    event = api_events["SubmitReview"]
    assert event["Properties"]["Path"] == "/reviews/{cardId}", (
        f"SubmitReview のパスが '/reviews/{{cardId}}' であること。"
        f" 実際: '{event['Properties']['Path']}'"
    )
    assert event["Properties"]["Method"] == "POST", (
        f"SubmitReview のメソッドが 'POST' であること。"
        f" 実際: '{event['Properties']['Method']}'"
    )
    assert "{cardId}" in event["Properties"]["Path"], (
        "SubmitReview のパスに '{cardId}' パラメータが含まれること"
    )


# ---------------------------------------------------------------------------
# TC-042-03: REQ-V2-003 - LINE 連携イベント 存在検証
# ---------------------------------------------------------------------------


def test_link_line_event_exists_with_correct_path(api_events):
    """TC-042-03: REQ-V2-003 - LINE 連携イベントが POST /users/link-line で定義されていること"""
    assert "LinkLine" in api_events, (
        "LinkLine イベントが SAM テンプレートに存在すること。"
        " 現在は未定義のため追加が必要。"
    )
    event = api_events["LinkLine"]
    assert event["Type"] == "HttpApi", (
        f"LinkLine の Type が 'HttpApi' であること。実際: '{event['Type']}'"
    )
    assert event["Properties"]["Path"] == "/users/link-line", (
        f"LinkLine のパスが '/users/link-line' であること。"
        f" 実際: '{event['Properties']['Path']}'"
    )
    assert event["Properties"]["Method"] == "POST", (
        f"LinkLine のメソッドが 'POST' であること。"
        f" 実際: '{event['Properties']['Method']}'"
    )


# ---------------------------------------------------------------------------
# TC-042-04: 整合性チェック - 全 HttpApi イベント数
# ---------------------------------------------------------------------------


def test_total_http_api_event_count(api_events):
    """TC-042-04: 整合性 - ApiFunction の HttpApi イベント総数が 30 個

    期待イベント:
    1. GetUser          - GET /users/me
    2. UpdateUser       - PUT /users/me/settings
    3. LinkLine         - POST /users/link-line
    4. UnlinkLine       - POST /users/me/unlink-line
    5. ListCards        - GET /cards
    6. CreateCard       - POST /cards
    7. GetCard          - GET /cards/{cardId}
    8. UpdateCard       - PUT /cards/{cardId}
    9. DeleteCard       - DELETE /cards/{cardId}
    10. GetDueCards     - GET /cards/due
    11. SubmitReview    - POST /reviews/{cardId}
    12. UndoReview      - POST /reviews/{cardId}/undo
    13. GenerateCards   - POST /cards/generate
    14. RefineCard      - POST /cards/refine
    15. ListDecks       - GET /decks
    16. CreateDeck      - POST /decks
    17. UpdateDeck      - PUT /decks/{deckId}
    18. DeleteDeck      - DELETE /decks/{deckId}
    19. GetStats        - GET /stats
    20. GetWeakCards    - GET /stats/weak-cards
    21. GetForecast     - GET /stats/forecast
    22. ListBrowserProfiles  - GET /browser-profiles
    23. CreateBrowserProfile - POST /browser-profiles
    24. DeleteBrowserProfile - DELETE /browser-profiles/{profileId}
    25. CreateTutorSession  - POST /tutor/sessions
    26. SendTutorMessage    - POST /tutor/sessions/{sessionId}/messages
    27. EndTutorSession     - DELETE /tutor/sessions/{sessionId}
    28. ListTutorSessions   - GET /tutor/sessions
    29. GetTutorSession     - GET /tutor/sessions/{sessionId}
    30. GetAiJob            - GET /ai-jobs/{jobId} (ai-async-jobs: ジョブポーリング)

    注: GetReviewStats (GET /reviews/stats) はハンドラ未実装の死にルートだったため
    Medium-3 対応で削除済み（フロントは GetStats (/stats) を使用）。
    """
    assert len(api_events) == 30, (
        f"期待: 30 イベント、実際: {len(api_events)} イベント\n"
        f"現在のイベント: {list(api_events.keys())}"
    )


# ---------------------------------------------------------------------------
# TC-042-05: 制約チェック - 全イベントが ApiId を参照
# ---------------------------------------------------------------------------


def test_all_events_reference_http_api(api_events):
    """TC-042-05: 制約 - 全 HttpApi イベントが ApiId を参照していること

    注: PyYAML では !Ref は文字列でなくカスタムタグとして扱われるため、
        ApiId キーの存在のみを検証する。
    """
    for name, event in api_events.items():
        props = event["Properties"]
        assert "ApiId" in props, (
            f"イベント '{name}' に ApiId が設定されていません"
        )


# ---------------------------------------------------------------------------
# TC-042-06: REQ-V2-004 - SAM パスと handler ルート定義の一致
# ---------------------------------------------------------------------------


def test_sam_paths_match_handler_routes(api_events, handler_routes):
    """TC-042-06: 整合性 - SAM テンプレートの全パスが handler.py のルート定義と対応

    検証方向: handler.py で定義された全ルートが SAM テンプレートにも定義されていること
    (handler → SAM の片方向チェック)

    正規化ルール:
    - SAM テンプレート: {paramName} 形式 (例: {cardId})
    - handler.py: <param_name> 形式 (例: <card_id>)
    - SAM の {camelCase} を <snake_case> に変換して比較
    """

    def normalize_sam_path(path: str) -> str:
        """SAM の {camelCase} を handler の <snake_case> に変換."""
        def camel_to_snake(match):
            name = match.group(1)
            # camelCase → snake_case 変換
            snake = re.sub(r"([A-Z])", r"_\1", name).lower().lstrip("_")
            return f"<{snake}>"
        return re.sub(r"\{(\w+)\}", camel_to_snake, path)

    sam_routes = set()
    for name, event in api_events.items():
        method = event["Properties"]["Method"].upper()
        path = normalize_sam_path(event["Properties"]["Path"])
        sam_routes.add((method, path))

    # handler.py のルートが全て SAM テンプレートにも定義されていること
    for method, path in handler_routes:
        assert (method, path) in sam_routes, (
            f"handler ルート ({method} {path}) が SAM テンプレートに存在しません。\n"
            f"SAM ルート一覧 (正規化後): {sorted(sam_routes)}"
        )


# ---------------------------------------------------------------------------
# TC-042-07: 整合性チェック - 全エンドポイント パスとメソッドの一括検証
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "event_name, expected_path, expected_method",
    [
        ("GetUser", "/users/me", "GET"),
        ("UpdateUser", "/users/me/settings", "PUT"),
        ("LinkLine", "/users/link-line", "POST"),
        ("UnlinkLine", "/users/me/unlink-line", "POST"),
        ("ListCards", "/cards", "GET"),
        ("CreateCard", "/cards", "POST"),
        ("GetCard", "/cards/{cardId}", "GET"),
        ("UpdateCard", "/cards/{cardId}", "PUT"),
        ("DeleteCard", "/cards/{cardId}", "DELETE"),
        ("GetDueCards", "/cards/due", "GET"),
        ("SubmitReview", "/reviews/{cardId}", "POST"),
        ("UndoReview", "/reviews/{cardId}/undo", "POST"),
        ("GenerateCards", "/cards/generate", "POST"),
        ("ListDecks", "/decks", "GET"),
        ("CreateDeck", "/decks", "POST"),
        ("UpdateDeck", "/decks/{deckId}", "PUT"),
        ("DeleteDeck", "/decks/{deckId}", "DELETE"),
    ],
)
def test_event_path_and_method(api_events, event_name, expected_path, expected_method):
    """TC-042-07: 整合性 - 全 17 エンドポイントのパスとメソッドが期待通りであること"""
    assert event_name in api_events, (
        f"イベント '{event_name}' が SAM テンプレートに存在しません。"
        f" 現在のイベント: {list(api_events.keys())}"
    )
    event = api_events[event_name]
    assert event["Properties"]["Path"] == expected_path, (
        f"{event_name}: 期待パス='{expected_path}', "
        f"実際='{event['Properties']['Path']}'"
    )
    assert event["Properties"]["Method"] == expected_method, (
        f"{event_name}: 期待メソッド='{expected_method}', "
        f"実際='{event['Properties']['Method']}'"
    )


# ---------------------------------------------------------------------------
# TC-042-09: 品質チェック - イベント名の重複なし
# ---------------------------------------------------------------------------


def test_no_duplicate_event_names(sam_template):
    """TC-042-09: 品質 - イベント名の重複がないこと

    YAML で重複キーは後勝ちになるため、イベント数が期待通りの 30 個かで検証する。
    """
    events = sam_template["Resources"]["ApiFunction"]["Properties"]["Events"]
    http_api_events = {
        name: ev for name, ev in events.items()
        if ev.get("Type") == "HttpApi"
    }
    # YAML で重複キーは後勝ちになるため、パース後にイベント数が期待通りかで検証
    assert len(http_api_events) == 30, (
        f"期待: 30 イベント, 実際: {len(http_api_events)} イベント\n"
        f"イベント: {list(http_api_events.keys())}"
    )


# ---------------------------------------------------------------------------
# TC-042-31: EDGE-001-01 - GET /users/me と PUT /users/me/settings の共存
# ---------------------------------------------------------------------------


def test_get_user_and_update_user_coexist(api_events):
    """TC-042-31: EDGE-001-01 - GET /users/me と PUT /users/me/settings が異なるパスで共存すること"""
    # GetUser
    assert api_events["GetUser"]["Properties"]["Path"] == "/users/me"
    assert api_events["GetUser"]["Properties"]["Method"] == "GET"
    # UpdateUser
    assert api_events["UpdateUser"]["Properties"]["Path"] == "/users/me/settings", (
        f"UpdateUser のパスが '/users/me/settings' であること。"
        f" 実際: '{api_events['UpdateUser']['Properties']['Path']}'"
    )
    assert api_events["UpdateUser"]["Properties"]["Method"] == "PUT"
    # パスが異なること
    assert (
        api_events["GetUser"]["Properties"]["Path"]
        != api_events["UpdateUser"]["Properties"]["Path"]
    ), "GetUser と UpdateUser のパスが異なること"


# ---------------------------------------------------------------------------
# TC-042-32: EDGE-002-04 (更新) - 死にルート GetReviewStats の削除と
# POST /reviews/{cardId} の存続
# ---------------------------------------------------------------------------


def test_review_stats_route_removed_and_submit_review_still_exists(api_events):
    """TC-042-32: EDGE-002-04 (更新) - GetReviewStats (GET /reviews/stats) は
    ハンドラ未実装の死にルート（常に 404）だったため Medium-3 対応で削除済み
    （フロントは GetStats (/stats) を使用しており実利用なし）。
    再度追加されていないこと、および SubmitReview (POST /reviews/{cardId}) が
    引き続き存在することを回帰テストとして検証する。
    """
    assert "GetReviewStats" not in api_events, (
        "GetReviewStats はハンドラ未実装の死にルートのため削除済みであること。"
        " 再追加する場合は対応するハンドラも実装すること。"
    )
    # SubmitReview
    assert api_events["SubmitReview"]["Properties"]["Path"] == "/reviews/{cardId}", (
        f"SubmitReview のパスが '/reviews/{{cardId}}' であること。"
        f" 実際: '{api_events['SubmitReview']['Properties']['Path']}'"
    )
    assert api_events["SubmitReview"]["Properties"]["Method"] == "POST"
    # 統計取得は GetStats (/stats) 経由であること
    assert "GetStats" in api_events, "GetStats (/stats) が SAM テンプレートに存在すること"
    assert api_events["GetStats"]["Properties"]["Path"] == "/stats"
    assert api_events["GetStats"]["Properties"]["Method"] == "GET"


# ---------------------------------------------------------------------------
# TC-042-33: EDGE-003-01 - LinkLine と UnlinkLine のパスが異なること
# ---------------------------------------------------------------------------


def test_link_line_and_unlink_line_have_different_paths(api_events):
    """TC-042-33: EDGE-003-01 - LinkLine と UnlinkLine が異なるパスで定義されていること"""
    assert "LinkLine" in api_events, (
        "LinkLine イベントが存在すること（未定義の場合は追加が必要）"
    )
    assert api_events["LinkLine"]["Properties"]["Path"] == "/users/link-line"
    assert api_events["UnlinkLine"]["Properties"]["Path"] == "/users/me/unlink-line"
    assert (
        api_events["LinkLine"]["Properties"]["Path"]
        != api_events["UnlinkLine"]["Properties"]["Path"]
    ), "LinkLine と UnlinkLine のパスが異なること"


# ---------------------------------------------------------------------------
# TC-042-34: 整合性チェック - パスパラメータが {camelCase} 形式
# ---------------------------------------------------------------------------


def test_path_parameters_use_camel_case(api_events):
    """TC-042-34: 整合性 - パスパラメータが {camelCase} 形式で統一されていること"""
    param_pattern = re.compile(r"\{(\w+)\}")
    for name, event in api_events.items():
        path = event["Properties"]["Path"]
        params = param_pattern.findall(path)
        for param in params:
            # camelCase: アンダースコアを含まず、先頭が小文字
            assert "_" not in param, (
                f"イベント '{name}' のパスパラメータ '{{{param}}}' が snake_case です。"
                f" SAM テンプレートでは {{camelCase}} を使用してください。"
            )
            assert param[0].islower(), (
                f"イベント '{name}' のパスパラメータ '{{{param}}}' が大文字で始まっています。"
            )


# ---------------------------------------------------------------------------
# ai-async-jobs: ジョブポーリングルートと非同期基盤リソースの検証
# ---------------------------------------------------------------------------


def test_get_ai_job_route_exists(api_events):
    """ai-async-jobs - GET /ai-jobs/{jobId}（ジョブポーリング）ルートが存在すること"""
    assert "GetAiJob" in api_events, (
        "GetAiJob イベントが SAM テンプレートに存在すること。"
        " フロントのポーリング（submitAndPollAiJob）が 403 になるため必須。"
    )
    event = api_events["GetAiJob"]
    assert event["Properties"]["Path"] == "/ai-jobs/{jobId}", (
        f"GetAiJob のパスが '/ai-jobs/{{jobId}}' であること。"
        f" 実際: '{event['Properties']['Path']}'"
    )
    assert event["Properties"]["Method"].upper() == "GET", (
        f"GetAiJob のメソッドが 'GET' であること。"
        f" 実際: '{event['Properties']['Method']}'"
    )


def test_advice_route_is_post(sam_template):
    """ai-async-jobs - AdviceFunction の /advice ルートが POST であること

    ジョブ作成は非冪等のため GET → POST に変更された（設計 SH-7）。
    """
    advice_events = sam_template["Resources"]["AdviceFunction"]["Properties"]["Events"]
    advice_routes = [
        event["Properties"]
        for event in advice_events.values()
        if event.get("Type") == "HttpApi"
        and event.get("Properties", {}).get("Path") == "/advice"
    ]

    assert advice_routes, "/advice ルートが AdviceFunction に存在しない"
    assert advice_routes[0]["Method"].upper() == "POST", (
        f"/advice のメソッドが 'POST' であること。実際: '{advice_routes[0]['Method']}'"
    )


def test_ai_job_worker_function_defined(sam_template):
    """ai-async-jobs - AiJobWorkerFunction が定義され両キューを消費すること"""
    resources = sam_template["Resources"]

    assert "AiJobWorkerFunction" in resources, (
        "AiJobWorkerFunction が SAM テンプレートに存在すること"
    )
    worker = resources["AiJobWorkerFunction"]
    assert worker["Type"] == "AWS::Serverless::Function"
    assert worker["Properties"]["Handler"] == "jobs.ai_job_worker_handler.handler"

    # interactive / heavy 両キューの SQS イベントソースが張られていること
    sqs_events = [
        event
        for event in worker["Properties"]["Events"].values()
        if event.get("Type") == "SQS"
    ]
    assert len(sqs_events) == 2, (
        f"AiJobWorkerFunction の SQS イベントは 2 個（interactive/heavy）であること。"
        f" 実際: {len(sqs_events)} 個"
    )


def test_ai_job_queues_defined(sam_template):
    """ai-async-jobs - AiJobQueue / AiJobHeavyQueue（+ DLQ）が定義されていること"""
    resources = sam_template["Resources"]

    for queue_name in ("AiJobQueue", "AiJobHeavyQueue", "AiJobDLQ", "AiJobHeavyDLQ"):
        assert queue_name in resources, f"{queue_name} が SAM テンプレートに存在すること"
        assert resources[queue_name]["Type"] == "AWS::SQS::Queue", (
            f"{queue_name} の Type が 'AWS::SQS::Queue' であること"
        )


def test_ai_job_queue_settings_match_design(sam_template):
    """ai-async-jobs - 設計レビュー H-1/H-5 を担保するキュー/ESM 設定値の回帰テスト。

    - VisibilityTimeout 270 = ワーカー Timeout 180 × 1.5
    - interactive: maxReceiveCount 3 / MaximumConcurrency 5
    - heavy: maxReceiveCount 1（3×課金経路の遮断）/ MaximumConcurrency 2
    - 両 ESM とも BatchSize 1（バッチ内タイムアウトの巻き込み防止）
    """
    resources = sam_template["Resources"]

    interactive = resources["AiJobQueue"]["Properties"]
    assert interactive["VisibilityTimeout"] == 270
    assert interactive["RedrivePolicy"]["maxReceiveCount"] == 3

    heavy = resources["AiJobHeavyQueue"]["Properties"]
    assert heavy["VisibilityTimeout"] == 270
    assert heavy["RedrivePolicy"]["maxReceiveCount"] == 1

    worker = resources["AiJobWorkerFunction"]["Properties"]
    assert worker["Timeout"] == 180

    sqs_events = {
        name: event["Properties"]
        for name, event in worker["Events"].items()
        if event.get("Type") == "SQS"
    }
    concurrencies = set()
    for props in sqs_events.values():
        assert props["BatchSize"] == 1
        assert props["FunctionResponseTypes"] == ["ReportBatchItemFailures"]
        concurrencies.add(props["ScalingConfig"]["MaximumConcurrency"])
    assert concurrencies == {5, 2}


def test_ai_jobs_table_defined(sam_template):
    """ai-async-jobs - AiJobsTable（job_id キー + TTL）が定義されていること"""
    resources = sam_template["Resources"]

    assert "AiJobsTable" in resources, "AiJobsTable が SAM テンプレートに存在すること"
    table = resources["AiJobsTable"]
    assert table["Type"] == "AWS::DynamoDB::Table"

    props = table["Properties"]
    key_schema = props["KeySchema"]
    assert key_schema[0]["AttributeName"] == "job_id"
    assert key_schema[0]["KeyType"] == "HASH"

    # 24h TTL で使い捨てるレコードのため TTL が有効であること
    ttl = props["TimeToLiveSpecification"]
    assert ttl["AttributeName"] == "ttl"
    assert ttl["Enabled"] is True
