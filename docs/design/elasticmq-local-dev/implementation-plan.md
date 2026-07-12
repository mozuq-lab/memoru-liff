# ElasticMQ ローカル導入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **保存先の注記:** superpowers:writing-plans の既定パスは `docs/superpowers/plans/` だが、本プロジェクトは CLAUDE.md で `docs/design/{要件名}/` を設計文書の置き場所と定めているため、そちらに合わせて `docs/design/elasticmq-local-dev/implementation-plan.md` に保存する。

**Goal:** ローカル開発環境に ElasticMQ（SQS 互換エミュレータ）を追加し、`URL_GENERATE_QUEUE_URL` / `AI_JOB_QUEUE_URL` / `AI_JOB_HEAVY_QUEUE_URL` への enqueue を本番同様のキュー構成（キュー名・DLQ 振り分け・可視性タイムアウト）でローカル検証できるようにする。**BatchSize はワーカー Lambda の Event Source Mapping 設定であり、`sam local` は SQS ワーカーの起動自体を再現できないため検証対象に含まない**（Codex レビューで指摘を受け、当初案から除外）。

**Architecture:** DynamoDB Local と同じ「docker-compose に専用コンテナを追加し、boto3 クライアントの endpoint_url を環境変数で差し替える」パターンを踏襲する。SQS 用に新しい共通ファクトリ `utils/sqs_client.py`（`DYNAMODB_ENDPOINT_URL`/`AWS_ENDPOINT_URL` を読む `utils/dynamodb_client.py` の SQS 版）を新設し、`webhook/line_actions.py` と `services/ai_job_service.py` の重複した `boto3.client("sqs")` 生成箇所をそこに委譲する。ElasticMQ はデフォルトの `make local-all` / `env.json` には含めないオプトイン機能とし、既存の inline 動作（デフォルトのローカル開発体験）は一切変更しない。

**Tech Stack:** Python 3.12 / boto3（既存依存、追加インストール不要）/ Docker Compose / ElasticMQ (`softwaremill/elasticmq-native` イメージ) / pytest + moto（既存テストは変更しない）。

## Global Constraints

- 対象はローカル開発環境のみ。CDK・本番デプロイ設定は変更しない。`template.yaml` は `SQS_ENDPOINT_URL` の空文字デフォルト宣言のみ実施済み（PR #82、下記「追記（2026-07-12）」参照）。ElasticMQ 本体（docker-compose・Makefile・`env.elasticmq.json`）は「最終スコープ決定」により見送ったまま。
- ElasticMQ はオプトイン。デフォルトの `make local-all` と `backend/env.json` は変更せず、既存の `*_WORKER_MODE=inline` によるローカル動作を壊さない。（※ElasticMQ本体は「最終スコープ決定」により今回は導入しない。以下はTask 3〜5として参考記録のみ残す。）
- 新規 pip 依存を追加しない（`boto3` は既存の requirements に含まれる）。
- キュー名・VisibilityTimeout・maxReceiveCount は `backend/template.yaml` の実キュー定義と完全一致させる:
  - `UrlGenerateQueue`（`memoru-url-generate-${Environment}`）: VisibilityTimeout 180 / maxReceiveCount 3 / DLQ `UrlGenerateWorkerDLQ`（`memoru-url-generate-dlq-${Environment}`）
  - `AiJobQueue`（`memoru-ai-job-${Environment}`）: VisibilityTimeout 270 / maxReceiveCount 3 / DLQ `AiJobDLQ`（`memoru-ai-job-dlq-${Environment}`）
  - `AiJobHeavyQueue`（`memoru-ai-job-heavy-${Environment}`）: VisibilityTimeout 270 / maxReceiveCount 1 / DLQ `AiJobHeavyDLQ`（`memoru-ai-job-heavy-dlq-${Environment}`）
  - ローカルの `Environment` は `dev` 固定なので、キュー名は `memoru-url-generate-dev` 等になる。
  - **BatchSize / MaximumConcurrency はワーカー Lambda の Event Source Mapping 設定であり、SQS キュー属性ではない**。`sam local` は SQS→Lambda トリガー自体を起動できないため ElasticMQ 導入後もこれらは検証できない。`template.yaml` 上の静的な定義確認に留める。
- Docker イメージタグは既存 `backend/docker-compose.yaml` の `dynamodb-admin` / `ollama` サービスに合わせ `latest` を使う（`dynamodb-local` / `keycloak` のみ既にバージョン固定済み。既存の混在方針を踏襲）。初回動作確認後、`latest` のまま運用するか確認済みタグに固定するかはフォローアップ課題とする。
- **既知の制限（README にも明記する）**: `sam local` は SQS → Lambda トリガーを再現できない。この改修で検証できるのは「正しいキューへ正しい形式のメッセージが enqueue されるか、キュー属性（VisibilityTimeout・redrive）が意図通りか」までであり、ワーカー側の実処理の自動実行は含まない。

### 最終スコープ決定（Codex レビュー後の議論を経て縮小）

Codex レビュー後、「このプランの残りの価値は enqueue の形・キュー名の妥当性確認だけであり、それは既存の moto ベースのユニットテスト（`test_webhook_url_dispatch.py`, `test_ai_job_service.py`）で既に確認できている」という指摘があり、以下の通りスコープを縮小した:

- **実施する**: Task 1（`utils/sqs_client.py` の共通ファクトリ）+ 元 Task 2（`line_actions.py` / `ai_job_service.py` の配線）。既存の重複コードを解消し、`SQS_ENDPOINT_URL` で差し替え可能にする DRY 改善として、それ自体に価値があるため実施する。
- **見送る**: 元 Task 1 内の `template.yaml` への `SQS_ENDPOINT_URL` 宣言追加、および Task 3〜5（ElasticMQ の docker-compose 追加・Makefile ターゲット・`env.elasticmq.json`・README/設計 doc 更新）。理由:
  1. SQS→Lambda の実トリガー・BatchSize・DLQ・CloudWatch Alarm は `sam local` では原理的に検証できず（SAM CLI 自体の制約。ElasticMQ を導入しても解消しない）、本当に必要なら実際に `dev` 環境へデプロイして確認するしかない。
  2. enqueue の形式・キュー名の妥当性は、moto ベースの既存ユニットテストで既に確認できている。
  3. 上記2点を踏まえると、ElasticMQ 一式(docker-compose・conf ファイル・Makefile 4ターゲット・env ファイルの二重管理・ドキュメント更新)を維持するコスト(Codex レビューで指摘された node-address の癖、native image の信頼性未検証、`env.elasticmq.json` のドリフトリスクなど)に見合うリターンがない。
  4. `template.yaml` への `SQS_ENDPOINT_URL` 宣言も、実際に読み書きする ElasticMQ 側の仕組みを作らない以上、現時点では使われない先回りの変更になる(YAGNI)。

Task 3〜5 の内容自体は Codex レビュー済みの設計として本ドキュメントに残すが、**チェックボックスとしては実施しない**。将来 SQS→Lambda の実トリガー確認が本当に必要になった場合は、まず「実環境デプロイでの検証」を優先し、それでも足りない場合にこの下の Task 3〜5 を再検討する。

#### 追記（2026-07-12）: `template.yaml` への `SQS_ENDPOINT_URL` 宣言は追加する方針に変更

上記 4. の判断を、PR #82 で以下の理由により部分的に見直した:

- `utils/sqs_client.get_sqs_client()` は既にコード上で `SQS_ENDPOINT_URL` を読んでいる。`template.yaml`（インフラ定義）にこの変数が一切現れないと、ソースコードを読まない限りこの設定項目の存在自体に気づけない。`DYNAMODB_ENDPOINT_URL` / `AWS_ENDPOINT_URL` が（ローカルで実際に機能しているかどうかに関わらず）`template.yaml` に宣言されているのは、まさにこの「インフラ定義から設定項目を発見できる」ことが目的であり、`SQS_ENDPOINT_URL` だけこの慣習から外れる理由はない。
- 実機検証（`sam local start-api` + モック SQS サーバー）により、`sam local` の `--env-vars` は `template.yaml` に**未宣言のキーを上書きできない**ことを確認した（上記「Codex レビュー対応」1. の懸念が実際に再現することを確認）。空文字デフォルトの宣言を追加するだけで `env.json` からの上書きが有効になる。
- ただし、これは ElasticMQ 導入（Task 3〜5）の再開を意味しない。空文字デフォルトの宣言追加のみであり、実際に読み書きする local SQS 互換サービスは依然として存在しない（`SQS_ENDPOINT_URL` を未設定のままなら挙動は一切変わらない）。ElasticMQ 本体の要否は上記 1.〜3. の理由により変わらず見送りとする。

このため File Structure（下表）の `backend/template.yaml` 行は「見送り」から「実施済み」に更新する。

### Codex レビュー対応（このプランは一度 Codex MCP でレビュー済み）

当初案を Codex（gpt-5.2-codex, read-only sandbox）にレビューさせたところ、以下の指摘を受けて反映した:

1. `SQS_ENDPOINT_URL` が `template.yaml` に一切宣言されていないと `sam local --env-vars` 経由で Lambda コンテナに確実に渡るか不明瞭（既存の `DYNAMODB_ENDPOINT_URL`/`AWS_ENDPOINT_URL`/`AI_JOB_QUEUE_URL` 等は必ず `template.yaml` に宣言されている）→ **Task 1 に `template.yaml` への宣言を追加**。
2. BatchSize は ESM 設定でありキュー属性ではないため ElasticMQ では検証不能 → **Goal・Global Constraints の記述を修正**。
3. `rest-stats` を Web UI として扱っていたが、ElasticMQ の公式 Web UI は別イメージ (`softwaremill/elasticmq-ui`) であり `rest-stats` が UI を提供する根拠がない → **`rest-stats` 設定と 9325 ポートを削除**（UI は今回のスコープ外）。
4. `node-address.host` をコンテナ名 `"elasticmq"` に固定すると、返却される QueueUrl がホスト側の `aws sqs` CLI から解決できない → **`host = "*"`（Host ヘッダーを echo するワイルドカード）に変更**。
5. `/dev/tcp` ベースの healthcheck は native image で動く保証がなく、何も `depends_on` していないため実益もない → **healthcheck を削除**。
6. `aws sqs` コマンド例にダミー認証情報・リージョンの明示がない → **`AWS_ACCESS_KEY_ID=local AWS_SECRET_ACCESS_KEY=local` と `--region ap-northeast-1` を追加**。
7. キュー一覧だけでは VisibilityTimeout/RedrivePolicy が反映されたか分からない → **`get-queue-attributes` での確認手順を追加**。
8. `env.elasticmq.json` を `env.json` の丸コピーで作るとドリフトしうる → **同期が必要である旨を明記**（自動化は YAGNI のため見送り、手動運用の注意書きに留める）。

---

## File Structure

| ファイル | 種別 | 責務 |
|---|---|---|
| ファイル | 種別 | 状態 |
|---|---|---|
| `backend/src/utils/sqs_client.py` | 新規 | **実施済み**。SQS クライアント生成の共通ファクトリ（`SQS_ENDPOINT_URL` 差し替え） |
| `backend/tests/unit/test_sqs_client.py` | 新規 | **実施済み**。上記ファクトリの単体テスト |
| `backend/src/webhook/line_actions.py` | 変更 | **実施済み**。`_get_sqs_client()` をファクトリ経由に置き換え |
| `backend/src/services/ai_job_service.py` | 変更 | **実施済み**。同上 |
| `backend/template.yaml` | 変更 | **実施済み**（PR #82）。`Globals.Function.Environment.Variables` に `SQS_ENDPOINT_URL: ""` を宣言。上記「追記（2026-07-12）」参照。ElasticMQ 本体の導入ではない |
| `backend/elasticmq.conf` | — | **見送り**（参考記録のみ、Task 3 参照） |
| `backend/docker-compose.yaml` | — | **見送り**（参考記録のみ、Task 3 参照） |
| `backend/Makefile` | — | **見送り**（参考記録のみ、Task 4 参照） |
| `backend/env.elasticmq.json` | — | **見送り**（参考記録のみ、Task 4 参照） |
| `README.md` | — | **見送り**（参考記録のみ、Task 5 参照） |
| `docs/design/ai-async-jobs/architecture.md` | — | **見送り**（参考記録のみ、Task 5 参照） |

---

### Task 1: SQS クライアントの共通ファクトリを追加する

**Files:**
- Create: `backend/src/utils/sqs_client.py`
- Test: `backend/tests/unit/test_sqs_client.py`

**Interfaces:**
- Produces: `get_sqs_endpoint_url() -> Optional[str]`、`get_sqs_client() -> Any`（boto3 SQS クライアント）。Task 2 がこの2関数をインポートして使う。

**Note:** 元プランにあった `template.yaml` への `SQS_ENDPOINT_URL` 宣言追加は、上記「最終スコープ決定」で一度見送ったが、「追記（2026-07-12）」の通り PR #82 で追加した。

- [ ] **Step 1: 失敗するテストを書く**

`backend/tests/unit/test_sqs_client.py` を新規作成:

```python
"""Unit tests for the shared SQS client factory (utils/sqs_client)."""

from unittest.mock import MagicMock, patch

from utils import sqs_client


class TestGetSqsEndpointUrl:
    def test_returns_none_when_unset(self, monkeypatch):
        monkeypatch.delenv("SQS_ENDPOINT_URL", raising=False)
        assert sqs_client.get_sqs_endpoint_url() is None

    def test_returns_none_when_empty_string(self, monkeypatch):
        monkeypatch.setenv("SQS_ENDPOINT_URL", "")
        assert sqs_client.get_sqs_endpoint_url() is None

    def test_returns_value_when_set(self, monkeypatch):
        monkeypatch.setenv("SQS_ENDPOINT_URL", "http://elasticmq:9324")
        assert sqs_client.get_sqs_endpoint_url() == "http://elasticmq:9324"


class TestGetSqsClient:
    def test_passes_endpoint_url_when_set(self, monkeypatch):
        monkeypatch.setenv("SQS_ENDPOINT_URL", "http://elasticmq:9324")
        with patch.object(sqs_client, "boto3") as mock_boto3:
            mock_boto3.client.return_value = MagicMock()
            sqs_client.get_sqs_client()
            mock_boto3.client.assert_called_once_with(
                "sqs", endpoint_url="http://elasticmq:9324"
            )

    def test_omits_endpoint_url_when_unset(self, monkeypatch):
        monkeypatch.delenv("SQS_ENDPOINT_URL", raising=False)
        with patch.object(sqs_client, "boto3") as mock_boto3:
            mock_boto3.client.return_value = MagicMock()
            sqs_client.get_sqs_client()
            mock_boto3.client.assert_called_once_with("sqs")
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `cd backend && pytest tests/unit/test_sqs_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'utils.sqs_client'`

- [ ] **Step 3: 最小実装を書く**

`backend/src/utils/sqs_client.py` を新規作成:

```python
"""SQS クライアント生成の共通ファクトリ。

各サービスで重複していた boto3 SQS クライアント初期化ロジックを一元化する。
ローカル開発時は SQS_ENDPOINT_URL でエンドポイントを差し替えられる
（DynamoDB の DYNAMODB_ENDPOINT_URL と同じ役割。utils.dynamodb_client 参照）。

NOTE: DynamoDB の get_endpoint_url() と異なり AWS_ENDPOINT_URL へはフォール
バックしない。env.json では AWS_ENDPOINT_URL が DynamoDB Local
(http://dynamodb-local:8000) 用に既に使われており、共有すると SQS 呼び出しが
誤って DynamoDB のエンドポイントへ向いてしまうため、専用の SQS_ENDPOINT_URL
のみを見る。
"""

import os
from typing import Any, Optional

import boto3


def get_sqs_endpoint_url() -> Optional[str]:
    """ローカル開発用の SQS エンドポイント URL を返す（未設定時は None）。"""
    return os.environ.get("SQS_ENDPOINT_URL") or None


def get_sqs_client() -> Any:
    """boto3 SQS クライアントを取得する。"""
    endpoint_url = get_sqs_endpoint_url()
    if endpoint_url:
        return boto3.client("sqs", endpoint_url=endpoint_url)
    return boto3.client("sqs")
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `cd backend && pytest tests/unit/test_sqs_client.py -v`
Expected: PASS（4 tests）

- [ ] **Step 5: Commit**

```bash
git add backend/src/utils/sqs_client.py backend/tests/unit/test_sqs_client.py
git commit -m "feat: SQS クライアント生成の共通ファクトリを追加"
```

---

### Task 2: 既存の SQS 呼び出し箇所を共通ファクトリ経由に置き換える

**Files:**
- Modify: `backend/src/webhook/line_actions.py`（14行目の `import boto3`、54-59行目の `_get_sqs_client()`）
- Modify: `backend/src/services/ai_job_service.py`（18行目の `import boto3`、34-39行目の `_get_sqs_client()`）
- Test（regression のみ、編集不要）: `backend/tests/unit/test_webhook_url_dispatch.py`、`backend/tests/unit/test_ai_job_service.py`

**Interfaces:**
- Consumes: Task 1 が produce した `get_sqs_client() -> Any`（`utils.sqs_client` からインポート）。
- 既存テストは `patch("webhook.line_actions._get_sqs_client", ...)` / `patch.object(svc, "_get_sqs_client", ...)` で `_get_sqs_client` 関数自体をモック化しているため、関数名・シグネチャ（引数なし、戻り値 `Any`）は変更しない。内部実装だけを委譲に変える。

- [ ] **Step 1: 既存テストがすべて通ることを確認する（ベースライン）**

Run: `cd backend && pytest tests/unit/test_webhook_url_dispatch.py tests/unit/test_ai_job_service.py -v`
Expected: PASS（変更前の現状）

- [ ] **Step 2: `line_actions.py` を編集する**

`import boto3`（14行目）を削除し、他の `utils.*` import と並べて追加する:

```python
from utils.sqs_client import get_sqs_client
from utils.url_validator import UrlValidationError, validate_url
```

`_get_sqs_client()`（54-59行目）を編集:

```python
def _get_sqs_client() -> Any:
    """SQS クライアントを遅延生成して返す。"""
    global _sqs_client
    if _sqs_client is None:
        _sqs_client = get_sqs_client()
    return _sqs_client
```

- [ ] **Step 3: `ai_job_service.py` を編集する**

`import boto3`（18行目）を削除し、import 群に追加:

```python
from services.ai_job_errors import classify_ai_job_error
from services.ai_job_executors import HEAVY_JOB_TYPES, execute_job
from services.ai_job_store import AiJobStore
from utils.sqs_client import get_sqs_client
```

`_get_sqs_client()`（34-39行目）を編集:

```python
def _get_sqs_client() -> Any:
    """SQS クライアントを遅延生成して返す。"""
    global _sqs_client
    if _sqs_client is None:
        _sqs_client = get_sqs_client()
    return _sqs_client
```

- [ ] **Step 4: lint とテストを実行して回帰がないことを確認する**

Run: `cd backend && ruff check src/webhook/line_actions.py src/services/ai_job_service.py && pytest tests/unit/test_webhook_url_dispatch.py tests/unit/test_ai_job_service.py tests/unit/test_sqs_client.py -v`
Expected: ruff で `boto3 imported but unused` 等のエラーが出ない。pytest は全 PASS（Step 1 と同じ件数）。

- [ ] **Step 5: Commit**

```bash
git add backend/src/webhook/line_actions.py backend/src/services/ai_job_service.py
git commit -m "refactor: SQS クライアント生成を共通ファクトリ経由に統一"
```

---

### Task 3: ElasticMQ を docker-compose に追加する

> **⚠️ 見送り（未実施）**: 「最終スコープ決定」により、Task 3〜5 は今回実施しない。以下は Codex レビュー済みの設計として参考記録のみ残す。

**Files:**
- Create: `backend/elasticmq.conf`
- Modify: `backend/docker-compose.yaml`

**Interfaces:**
- Produces: `memoru-network` 上でホスト名 `elasticmq`、ポート 9324（SQS API）で待ち受けるコンテナ。Task 4 が Makefile ターゲットからこのサービス名 (`elasticmq`) を参照する。

- [ ] **Step 1: ElasticMQ の設定ファイルを作成する**

`backend/elasticmq.conf` を新規作成:

```hocon
include classpath("application.conf")

# ローカル開発用 SQS エミュレータ (ElasticMQ)。
# node-address.host = "*" は「リクエストの Host ヘッダーをそのまま QueueUrl
# に反映する」ワイルドカード指定（ElasticMQ 公式ドキュメント記載の機能）。
# これにより、同じ ElasticMQ インスタンスに対して
#   - memoru-network 内 (SAM Local の Lambda コンテナ) からは "elasticmq:9324"
#   - ホスト側 (開発者の `aws sqs` CLI) からは "localhost:9324"
# のように、実際にアクセスした host:port で QueueUrl が返る。host を
# "elasticmq" に固定すると後者がホストから解決できなくなるため使わない。
node-address {
  protocol = http
  host = "*"
  port = 9324
  context-path = ""
}

rest-sqs {
  enabled = true
  bind-port = 9324
  bind-hostname = "0.0.0.0"
}

queues {
  # template.yaml の UrlGenerateQueue / UrlGenerateWorkerDLQ
  # (VisibilityTimeout 180 / maxReceiveCount 3) を再現する。
  memoru-url-generate-dlq-dev {}
  memoru-url-generate-dev {
    defaultVisibilityTimeout = 180 seconds
    deadLettersQueue {
      name = "memoru-url-generate-dlq-dev"
      maxReceiveCount = 3
    }
  }

  # AiJobQueue / AiJobDLQ (VisibilityTimeout 270 / maxReceiveCount 3)。
  memoru-ai-job-dlq-dev {}
  memoru-ai-job-dev {
    defaultVisibilityTimeout = 270 seconds
    deadLettersQueue {
      name = "memoru-ai-job-dlq-dev"
      maxReceiveCount = 3
    }
  }

  # AiJobHeavyQueue / AiJobHeavyDLQ (VisibilityTimeout 270 / maxReceiveCount 1)。
  memoru-ai-job-heavy-dlq-dev {}
  memoru-ai-job-heavy-dev {
    defaultVisibilityTimeout = 270 seconds
    deadLettersQueue {
      name = "memoru-ai-job-heavy-dlq-dev"
      maxReceiveCount = 1
    }
  }
}
```

- [ ] **Step 2: `docker-compose.yaml` に `elasticmq` サービスを追加する**

`backend/docker-compose.yaml` の `ollama:` サービスブロックの直後・`networks:` ブロックの直前に追加:

```yaml
  elasticmq:
    image: softwaremill/elasticmq-native:latest
    container_name: memoru-elasticmq
    ports:
      - "9324:9324"
    volumes:
      - ./elasticmq.conf:/opt/elasticmq.conf:ro
    networks:
      - memoru-network
```

Codex レビュー対応: 当初 `healthcheck` に `exec 3<>/dev/tcp/localhost/9324`（dynamodb-local と同じ手法）を入れていたが、(a) `elasticmq-native` は GraalVM ネイティブイメージで `/bin/sh` の挙動が dynamodb-local のベースイメージと異なり `/dev/tcp` が使える保証がない、(b) `elasticmq` を `depends_on: condition: service_healthy` で待ち受ける他サービスが存在せず healthcheck 自体に実益がない、の2点から削除した。

- [ ] **Step 3: コンテナを起動して疎通確認する**

Run: `cd backend && docker compose up -d elasticmq && docker compose logs elasticmq`
Expected: ログに `bound to /0.0.0.0:9324`（または同趣旨の起動完了メッセージ）が出力され、エラー終了していない。

- [ ] **Step 4: キューが定義通り作成されているか確認する**

Run:
```bash
AWS_ACCESS_KEY_ID=local AWS_SECRET_ACCESS_KEY=local aws sqs list-queues \
  --endpoint-url http://localhost:9324 --region ap-northeast-1
```
Expected: 6 キュー（`memoru-url-generate-dev`, `memoru-url-generate-dlq-dev`, `memoru-ai-job-dev`, `memoru-ai-job-dlq-dev`, `memoru-ai-job-heavy-dev`, `memoru-ai-job-heavy-dlq-dev`）の URL が `http://localhost:9324/queue/...` の形式で返る（`node-address.host = "*"` により、ホストからアクセスした host:port がそのまま反映される）。

続けて、VisibilityTimeout と RedrivePolicy が `elasticmq.conf` の定義通り反映されているか確認する（Codex レビュー対応: キュー一覧だけでは属性値までは分からないため追加）:
```bash
AWS_ACCESS_KEY_ID=local AWS_SECRET_ACCESS_KEY=local aws sqs get-queue-attributes \
  --queue-url http://localhost:9324/queue/memoru-ai-job-heavy-dev \
  --attribute-names VisibilityTimeout RedrivePolicy \
  --endpoint-url http://localhost:9324 --region ap-northeast-1
```
Expected: `VisibilityTimeout` が `"270"`、`RedrivePolicy` の JSON 文字列内に `"maxReceiveCount":1` と `memoru-ai-job-heavy-dlq-dev` の ARN が含まれる。

- [ ] **Step 5: Commit**

```bash
git add backend/elasticmq.conf backend/docker-compose.yaml
git commit -m "feat: ElasticMQ を docker-compose に追加"
```

---

### Task 4: Makefile ターゲットとローカル用 env ファイルを追加する

**Files:**
- Modify: `backend/Makefile`
- Create: `backend/env.elasticmq.json`

**Interfaces:**
- Consumes: Task 3 が produce した `elasticmq` サービス（コンテナ名 `memoru-elasticmq`、ネットワーク上のホスト名 `elasticmq`、ポート 9324）。
- Consumes: `backend/env.json` の内容（コピーして拡張する）。

- [ ] **Step 1: `Makefile` の `.PHONY` に新ターゲットを追加する**

1行目付近の `.PHONY:` 行を編集（`local-ollama-native-check` / `local-ollama-native-pull` はホスト
ネイティブ Ollama 対応で追加済みの既存ターゲット。本 Task 実施時は削除しないよう注意）:

```makefile
.PHONY: help install build validate deploy-dev deploy-prod local-db local-keycloak local-ollama local-ollama-pull local-ollama-stop local-ollama-logs local-ollama-native-check local-ollama-native-pull local-mq local-mq-stop local-all local-all-stop local-api local-api-mq mq-list-queues test clean
```

- [ ] **Step 2: `local-mq` / `local-mq-stop` ターゲットを追加する**

`local-ollama-logs:` ターゲットの直後・`local-all:` ターゲットの直前に追加:

```makefile
local-mq: ## Start local ElasticMQ (SQS互換・オプトイン。README「SQSキューをローカルで検証する」参照)
	docker compose up -d elasticmq
	@echo "ElasticMQ (SQS): http://localhost:9324"

local-mq-stop: ## Stop local ElasticMQ
	docker compose stop elasticmq

```

- [ ] **Step 3: `local-api-mq` ターゲットを追加する**

`local-api:` ターゲットの直後に追加:

```makefile
local-api-mq: build ## Start local API with ElasticMQ wired up (enqueue のみ検証。sam local は SQS→Lambda 起動を再現できない)
	sam local start-api --port 8080 --docker-network memoru-network --env-vars env.elasticmq.json
```

- [ ] **Step 4: `mq-list-queues` ターゲットを追加する**

`scan-cards:` ターゲットの直後（ファイル末尾）に追加:

```makefile

mq-list-queues: ## List ElasticMQ queues (local)
	AWS_ACCESS_KEY_ID=local AWS_SECRET_ACCESS_KEY=local aws sqs list-queues \
	  --endpoint-url http://localhost:9324 --region ap-northeast-1
```

- [ ] **Step 5: `env.elasticmq.json` を作成する**

`backend/env.json` の内容をコピーし、以下の4関数ブロックのみ変更した `backend/env.elasticmq.json` を新規作成する（`DuePushJobFunction` は無変更でそのままコピー）:

```json
{
  "ApiFunction": {
    "ENVIRONMENT": "dev",
    "USERS_TABLE": "memoru-users-dev",
    "CARDS_TABLE": "memoru-cards-dev",
    "REVIEWS_TABLE": "memoru-reviews-dev",
    "DECKS_TABLE": "memoru-decks-dev",
    "TUTOR_SESSIONS_TABLE": "memoru-tutor-sessions-dev",
    "OIDC_ISSUER": "http://localhost:8180/realms/memoru",
    "BEDROCK_MODEL_ID": "global.anthropic.claude-haiku-4-5-20251001-v1:0",
    "LOG_LEVEL": "DEBUG",
    "DYNAMODB_ENDPOINT_URL": "http://dynamodb-local:8000",
    "AWS_ENDPOINT_URL": "http://dynamodb-local:8000",
    "USE_STRANDS": "true",
    "AI_AGENT_TIMEOUT_SECONDS": "180",
    "OLLAMA_HOST": "http://host.docker.internal:11434",
    "OLLAMA_MODEL": "qwen3:1.7b",
    "RATE_LIMITS_TABLE": "",
    "AI_JOBS_TABLE": "memoru-ai-jobs-dev",
    "AI_JOB_WORKER_MODE": "async",
    "AI_JOB_QUEUE_URL": "http://elasticmq:9324/queue/memoru-ai-job-dev",
    "AI_JOB_HEAVY_QUEUE_URL": "http://elasticmq:9324/queue/memoru-ai-job-heavy-dev",
    "SQS_ENDPOINT_URL": "http://elasticmq:9324"
  },
  "UrlGenerateFunction": {
    "ENVIRONMENT": "dev",
    "USERS_TABLE": "memoru-users-dev",
    "CARDS_TABLE": "memoru-cards-dev",
    "DECKS_TABLE": "memoru-decks-dev",
    "OIDC_ISSUER": "http://localhost:8180/realms/memoru",
    "BEDROCK_MODEL_ID": "global.anthropic.claude-haiku-4-5-20251001-v1:0",
    "LOG_LEVEL": "DEBUG",
    "DYNAMODB_ENDPOINT_URL": "http://dynamodb-local:8000",
    "AWS_ENDPOINT_URL": "http://dynamodb-local:8000",
    "USE_STRANDS": "true",
    "AI_AGENT_TIMEOUT_SECONDS": "180",
    "OLLAMA_HOST": "http://host.docker.internal:11434",
    "OLLAMA_MODEL": "qwen3:1.7b",
    "RATE_LIMITS_TABLE": "",
    "AI_JOBS_TABLE": "memoru-ai-jobs-dev",
    "AI_JOB_WORKER_MODE": "async",
    "AI_JOB_QUEUE_URL": "http://elasticmq:9324/queue/memoru-ai-job-dev",
    "AI_JOB_HEAVY_QUEUE_URL": "http://elasticmq:9324/queue/memoru-ai-job-heavy-dev",
    "SQS_ENDPOINT_URL": "http://elasticmq:9324"
  },
  "LineWebhookFunction": {
    "ENVIRONMENT": "dev",
    "USERS_TABLE": "memoru-users-dev",
    "CARDS_TABLE": "memoru-cards-dev",
    "REVIEWS_TABLE": "memoru-reviews-dev",
    "DECKS_TABLE": "memoru-decks-dev",
    "LINE_CHANNEL_SECRET_ARN": "local-secret",
    "LOG_LEVEL": "DEBUG",
    "DYNAMODB_ENDPOINT_URL": "http://dynamodb-local:8000",
    "AWS_ENDPOINT_URL": "http://dynamodb-local:8000",
    "USE_STRANDS": "true",
    "AI_AGENT_TIMEOUT_SECONDS": "180",
    "URL_WORKER_MODE": "async",
    "URL_GENERATE_QUEUE_URL": "http://elasticmq:9324/queue/memoru-url-generate-dev",
    "SQS_ENDPOINT_URL": "http://elasticmq:9324",
    "OLLAMA_HOST": "http://host.docker.internal:11434",
    "OLLAMA_MODEL": "qwen3:1.7b"
  },
  "DuePushJobFunction": {
    "ENVIRONMENT": "dev",
    "USERS_TABLE": "memoru-users-dev",
    "CARDS_TABLE": "memoru-cards-dev",
    "DECKS_TABLE": "memoru-decks-dev",
    "LINE_CHANNEL_SECRET_ARN": "local-secret",
    "LOG_LEVEL": "DEBUG",
    "DYNAMODB_ENDPOINT_URL": "http://dynamodb-local:8000",
    "AWS_ENDPOINT_URL": "http://dynamodb-local:8000",
    "USE_STRANDS": "true",
    "AI_AGENT_TIMEOUT_SECONDS": "180",
    "OLLAMA_HOST": "http://host.docker.internal:11434",
    "OLLAMA_MODEL": "qwen3:1.7b"
  },
  "ReviewsGradeAiFunction": {
    "ENVIRONMENT": "dev",
    "USERS_TABLE": "memoru-users-dev",
    "CARDS_TABLE": "memoru-cards-dev",
    "REVIEWS_TABLE": "memoru-reviews-dev",
    "DECKS_TABLE": "memoru-decks-dev",
    "OIDC_ISSUER": "http://localhost:8180/realms/memoru",
    "BEDROCK_MODEL_ID": "global.anthropic.claude-haiku-4-5-20251001-v1:0",
    "LOG_LEVEL": "DEBUG",
    "DYNAMODB_ENDPOINT_URL": "http://dynamodb-local:8000",
    "AWS_ENDPOINT_URL": "http://dynamodb-local:8000",
    "USE_STRANDS": "true",
    "AI_AGENT_TIMEOUT_SECONDS": "180",
    "OLLAMA_HOST": "http://host.docker.internal:11434",
    "OLLAMA_MODEL": "qwen3:1.7b",
    "RATE_LIMITS_TABLE": "",
    "AI_JOBS_TABLE": "memoru-ai-jobs-dev",
    "AI_JOB_WORKER_MODE": "async",
    "AI_JOB_QUEUE_URL": "http://elasticmq:9324/queue/memoru-ai-job-dev",
    "AI_JOB_HEAVY_QUEUE_URL": "http://elasticmq:9324/queue/memoru-ai-job-heavy-dev",
    "SQS_ENDPOINT_URL": "http://elasticmq:9324"
  },
  "AdviceFunction": {
    "ENVIRONMENT": "dev",
    "USERS_TABLE": "memoru-users-dev",
    "CARDS_TABLE": "memoru-cards-dev",
    "REVIEWS_TABLE": "memoru-reviews-dev",
    "DECKS_TABLE": "memoru-decks-dev",
    "OIDC_ISSUER": "http://localhost:8180/realms/memoru",
    "BEDROCK_MODEL_ID": "global.anthropic.claude-haiku-4-5-20251001-v1:0",
    "LOG_LEVEL": "DEBUG",
    "DYNAMODB_ENDPOINT_URL": "http://dynamodb-local:8000",
    "AWS_ENDPOINT_URL": "http://dynamodb-local:8000",
    "USE_STRANDS": "true",
    "AI_AGENT_TIMEOUT_SECONDS": "180",
    "OLLAMA_HOST": "http://host.docker.internal:11434",
    "OLLAMA_MODEL": "qwen3:1.7b",
    "RATE_LIMITS_TABLE": "",
    "AI_JOBS_TABLE": "memoru-ai-jobs-dev",
    "AI_JOB_WORKER_MODE": "async",
    "AI_JOB_QUEUE_URL": "http://elasticmq:9324/queue/memoru-ai-job-dev",
    "AI_JOB_HEAVY_QUEUE_URL": "http://elasticmq:9324/queue/memoru-ai-job-heavy-dev",
    "SQS_ENDPOINT_URL": "http://elasticmq:9324"
  }
}
```

**Codex レビュー対応（ドリフト注意）**: このファイルは `env.json` の丸コピー＋差分なので、`env.json` を編集した際にこのファイルへの反映を忘れるとローカル専用の設定が古くなる（DRY 違反）。自動生成の仕組みを作るのは本改修のスコープに対して過剰（YAGNI）と判断したが、JSON はコメントを書けず、かつ SAM の `--env-vars` パーサーが想定しないトップレベルキー（`_comment` 等）を許容するか未検証のためファイル自体に注記を埋め込むのは避ける。代わりに、`README.md`（Task 5）に「`env.json` を編集したら `env.elasticmq.json` にも同じ変更を手動で反映すること」という一文を明記する。

- [ ] **Step 6: 一連の動作を確認する**

Run:
```bash
cd backend
make local-db
make local-mq
make local-api-mq   # 別ターミナルで
```
その後 LINE Webhook の URL カード生成 postback、または `POST /api/cards/generate-from-url` 等の ai-jobs エンドポイントを叩き、以下で enqueue されたメッセージを確認する:
```bash
make mq-list-queues
AWS_ACCESS_KEY_ID=local AWS_SECRET_ACCESS_KEY=local aws sqs receive-message \
  --queue-url http://localhost:9324/queue/memoru-ai-job-dev \
  --endpoint-url http://localhost:9324 --region ap-northeast-1
```
Expected: 送信したリクエストに対応する `{"job_id": "..."}` または `{"user_id": ..., "url": ..., ...}` のメッセージ本文が返る。

- [ ] **Step 7: Commit**

```bash
git add backend/Makefile backend/env.elasticmq.json
git commit -m "feat: ElasticMQ 連携用の Makefile ターゲットと env ファイルを追加"
```

---

### Task 5: ドキュメントを更新する

**Files:**
- Modify: `README.md`（466-474行目付近、「AI 系エンドポイント・URL カード生成がローカルで同期実行される」節）
- Modify: `docs/design/ai-async-jobs/architecture.md`（§7「ローカル開発（inline モード）」、216行目）

**Interfaces:**
- Consumes: Task 3/4 で確定したコマンド名（`make local-mq`, `make local-api-mq`, `make mq-list-queues`）とファイル名（`env.elasticmq.json`）。

- [ ] **Step 1: README.md の該当段落を置き換える**

`README.md:473` の以下の段落:

```markdown
本番挙動どおりに SQS キューやワーカーの動作をローカルで検証したい場合は、LocalStack を導入して各 `*_QUEUE_URL` を設定し、あわせて対象の `*_WORKER_MODE=inline` を解除します（inline モードは「`*_WORKER_MODE=inline` **または** キュー URL 未設定」で発動するため、URL を設定するだけでは submit ハンドラーが同期実行のままになります）。キュー本数・BatchSize・DLQ・可視性タイムアウトの仕様は [docs/design/ai-async-jobs/architecture.md](docs/design/ai-async-jobs/architecture.md) §2、LocalStack の接続配線（`AWS_ENDPOINT_URL`）は同 §7 を参照。
```

を、以下に置き換える:

```markdown
本番挙動どおり SQS への enqueue を検証したい場合は、ElasticMQ（SQS 互換のローカルエミュレータ）を使います。

```bash
cd backend
make local-mq       # ElasticMQ を起動 (http://localhost:9324)
make local-api-mq   # env.elasticmq.json で SAM Local を起動
```

`env.elasticmq.json` は `env.json` と同じ構成で、対象 4 Lambda の `*_WORKER_MODE` を解除し `*_QUEUE_URL` / `SQS_ENDPOINT_URL` を注入したものです（inline モードは「`*_WORKER_MODE=inline` **または** キュー URL 未設定」で発動するため、両方変更する必要があります）。**`env.json` を編集した場合は `env.elasticmq.json` にも同じ変更を手動で反映してください**（自動同期の仕組みはありません）。

**注意**: `sam local` は SQS → Lambda トリガー（Event Source Mapping）を再現できないため、この構成で検証できるのは「正しいキューへ正しい形式のメッセージが enqueue されるか」「VisibilityTimeout・DLQ redrive 等のキュー属性が意図通りか」までです。BatchSize / MaximumConcurrency はワーカー Lambda 側の ESM 設定であり、ここでは検証できません（`template.yaml` の定義を直接確認してください）。ワーカーの実処理まで確認したい場合は `make mq-list-queues` や下記のようなコマンドでメッセージを直接取り出して内容を確認してください:

```bash
AWS_ACCESS_KEY_ID=local AWS_SECRET_ACCESS_KEY=local aws sqs receive-message \
  --queue-url http://localhost:9324/queue/memoru-ai-job-dev \
  --endpoint-url http://localhost:9324 --region ap-northeast-1
```

キュー本数・DLQ・可視性タイムアウトの仕様は [docs/design/ai-async-jobs/architecture.md](docs/design/ai-async-jobs/architecture.md) §2、ElasticMQ の接続配線（`SQS_ENDPOINT_URL`）は同 §7 を参照。
```

- [ ] **Step 2: docs/design/ai-async-jobs/architecture.md §7 を更新する**

`docs/design/ai-async-jobs/architecture.md:216` の以下の行:

```markdown
- LocalStack 導入時も `AWS_ENDPOINT_URL` の既存配線で SQS/DynamoDB とも解決される。
```

を、以下に置き換える:

```markdown
- ローカルで SQS enqueue を検証する場合は ElasticMQ を使う（`backend/docker-compose.yaml` の `elasticmq` サービス、`backend/elasticmq.conf` でキューを定義）。DynamoDB の `AWS_ENDPOINT_URL` とは別に、SQS 専用の `SQS_ENDPOINT_URL` で解決する（`utils/sqs_client.get_sqs_client()`）。手順は README の「AI 系エンドポイント・URL カード生成がローカルで同期実行される」節を参照。`sam local` は SQS→Lambda トリガーを再現できないため、これは enqueue 側の検証に限られる。
```

- [ ] **Step 3: 記述に矛盾がないか確認する**

`docs/design/local-dev-environment/` 配下（`architecture.md`, `dataflow.md`, `design-interview.md`）と `docs/tasks/local-dev-environment/TASK-0050.md` に残る LocalStack 言及は DynamoDB Local の代替案としての記述であり、今回の SQS/ElasticMQ の変更とは無関係なので変更しない（意図的にスコープ外）。

- [ ] **Step 4: Commit**

```bash
git add README.md docs/design/ai-async-jobs/architecture.md
git commit -m "docs: ElasticMQ 導入に伴うローカル開発ドキュメントの更新"
```

---

## Self-Review

1. **Spec coverage**: SQS クライアントのエンドポイント差し替え（Task 1-2）、ElasticMQ 本体とキュー定義（Task 3）、開発体験（Makefile/env ファイル, Task 4）、ドキュメント整合性（Task 5、旧 LocalStack 記述の是正）を全てカバー。
2. **Placeholder scan**: 全ステップに具体的なコード・コマンド・期待結果を記載済み。「TODO」「後で」等の表現なし。
3. **Type consistency**: `get_sqs_client() -> Any` / `get_sqs_endpoint_url() -> Optional[str]` の名前・シグネチャは Task 1 の実装から Task 2 の import まで一貫。キュー名・ポート番号・環境変数名も Task 3/4 で統一。
4. **Codex レビュー反映確認**: 8件の指摘（`SQS_ENDPOINT_URL` の template.yaml 未宣言/ BatchSize 検証不能 / rest-stats=UI の誤り / node-address.host 固定によるホスト解決不可 / healthcheck の実効性未検証 / 認証情報欠落 / get-queue-attributes 未実施 / env.elasticmq.json のドリフト）を全て Task 1・3・4・5 と Global Constraints に反映済み。

---

**最終決定: 実施するのは Task 1（+配線を含む元Task 2）のみ。** Task 3〜5（ElasticMQ の docker-compose 追加、Makefile、env.elasticmq.json、ドキュメント更新）は見送り、設計記録として本ドキュメントに残すのみとする。Task 1（+配線）はこのセッション内でインライン実行する。
