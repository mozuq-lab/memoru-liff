# サインアップ許可リスト (signup-allowlist) — アーキテクチャ設計

> v1.1: 設計レビュー（アーキテクチャ・整合性視点 / セキュリティ・Cognito 仕様視点の 2 系統）の
> 指摘を反映。指摘と対応の一覧は [design-review.md](./design-review.md) を参照。

## 背景と目的

現在の prod 構成は以下の 2 経路が無条件に開いており、URL を知った第三者が自由に
アカウントを作成して Bedrock ベースの AI 機能まで利用できる。

1. **メールセルフサインアップ**: `cognito-stack.ts` の `selfSignUpEnabled: true`
2. **LINE ログイン連携**: LINE IdP 経由の初回サインインで federated ユーザーが自動作成される

利用者を「運用者＋招待した知人数名」に限定するため、**Cognito PreSignUp Lambda
トリガー + DynamoDB 許可リスト**でアカウント作成の入口を一元的に遮断する。

### 決定済みの方針（経緯）

- **案2単体で実施**: `selfSignUpEnabled` は `true` のまま維持し、PreSignUp トリガーのみで制御する。
  トリガーは native（メール）/ LINE federation / AdminCreateUser の 3 経路すべてで発火し、
  federated ユーザーは Login/Authorize エンドポイント経由でしかサインインできないため、
  これ一枚で全入口を塞げる（CSV インポート等の残余経路は AWS 資格情報が必要）。
  トリガー Lambda がエラーになった場合もサインアップは失敗し（フェイルクローズ）、
  **拒否された試行は UNCONFIRMED ユーザーとしても残らない**（PreSignUp はユーザー作成完了の
  直前に起動するため）。
- **LINE は承認待ちフロー**: LINE IdP のスコープは `openid, profile` のみでメールアドレスを取得
  しない。また LINE Login の `sub` は本人がサインインを試行するまで知り得ないため、事前登録は
  不可能。→ 未知の LINE ユーザーは**拒否しつつ `pending` として記録**し、運用者が承認後に
  再ログインしてもらう。
- **管理は DynamoDB 直接操作 + Makefile ラッパー**: 利用者数名の規模で管理 API / 管理 UI は
  過剰。既存の `make scan-users` 等と同じ流儀で `make allowlist-*` ターゲットを用意する。
  操作者はスイッチロールで権限を取得する（`AWS_PROFILE` 前提）。

### スコープ外

- **Keycloak 経由の登録**: prod の authority を Keycloak にする場合、本トリガーの管轄外。
  Keycloak realm の `registrationAllowed` が無効であることを別途確認する（既定は無効）。
- **Hosted UI の改修**: 招待コード入力欄などは追加しない（Managed Login では不可能）。
- **既存ユーザー**: PreSignUp はサインアップ時のみ発火するため、既存アカウント・既存トークン
  には影響しない（デプロイ手順に既存ユーザーの棚卸しステップを含める）。
- **ローカル開発**: ローカルは Keycloak 認証（事前作成のテストユーザー）のため対象外。
  トリガー・テーブルともローカル環境には追加しない。

## 全体構成

```
[メールでサインアップ]──┐                        [PreSignupFunction (SAM/Lambda)]
                        │  PreSignUp_SignUp        │ identifier を正規化して GetItem
[LINE でサインイン]─────┼─→ [Cognito UserPool] ──→│  approved   → 許可
   (初回 = signup)      │  PreSignUp_             │  それ以外:
                        │  ExternalProvider        │   native → 拒否（記録しない）
[AdminCreateUser]───────┘  PreSignUp_             │   LINE   → pending 記録 + 拒否
                           AdminCreateUser         │  AdminCreateUser → 常に許可
                           （常に許可）             ▼
                                        [SignupAllowlistTable (DynamoDB)]
                                          ↑ make allowlist-add / approve / list / remove
                                          （スイッチロールで運用者が操作）
```

- **Lambda 本体と Invoke 許可は SAM（backend）が所有**し、CDK CognitoStack は ARN を
  受け取ってトリガーとして配線するだけとする。理由:
  - Python コードを `backend/src` に置くことで既存の pytest / ruff / mypy / カバレッジ基準に乗る
  - デプロイ順序は、既存の `MEMORU_PROD_API_ENDPOINT`（LiffHosting の CSP 配線）と同じ
    二段階パターンで循環しない（詳細は「デプロイ手順」参照）

## コンポーネント設計

### 1. SignupAllowlistTable (DynamoDB / template.yaml)

| 属性 | 型 | 説明 |
|---|---|---|
| `identifier` (PK) | S | 下記の正規化規則による識別子 |
| `status` | S | `approved` \| `pending` |
| `note` | S | 誰なのかの運用メモ（`allowlist-add` / `approve` で付与） |
| `display_name` | S | pending 記録時に LINE の `name` 属性から転記（**参考情報**。長さ制限 + 制御文字除去の上で保存） |
| `created_at` / `updated_at` | S | ISO 8601 UTC |
| `ttl` | N | **pending のみ** 記録から 30 日で自動削除。approved には付けない |

- `TableName: !Sub memoru-signup-allowlist-${Environment}`
- 既存テーブルと同一方針: `PAY_PER_REQUEST` / `DeletionPolicy: Retain` /
  `UpdateReplacePolicy: Retain` / PITR / SSE(KMS) / `DeletionProtectionEnabled: !If [IsProd, ...]`
- `TimeToLiveSpecification: { AttributeName: ttl, Enabled: true }`

**identifier 正規化規則**

| 経路 | identifier | 正規化 |
|---|---|---|
| メール | `email#<address>` | `userAttributes.email` を trim + 小文字化 |
| LINE | `idp#<userName>` | PreSignUp イベントの `userName`（`LINE_<sub>` 形式）を小文字化 |

- LINE の identifier は**常にイベントの `userName` 由来**とし、人間は手入力しない
  （承認時は `allowlist-list` の出力からコピーする）。書き込みと照合が同じソースから
  導出されるため、大文字小文字（`signInCaseSensitive: false`）や形式の揺れが原理的に発生しない。
- メールのプラスアドレシング（`user+tag@`）や Unicode 正規化は扱わない（非目標）。
  招待した本人が登録したアドレスをそのまま許可リストに載せる運用でカバーする。

### 2. PreSignupFunction (Lambda / template.yaml)

- `FunctionName: !Sub memoru-presignup-${Environment}` / Tags（Environment / Application）は
  既存 Lambda と同一規約
- `CodeUri: src/` / `Handler: auth.pre_signup.handler`（既存の全関数と同じ src 相対ドット区切り。
  実ファイルは `backend/src/auth/pre_signup.py`、エントリ関数名は既存に合わせ `handler`。
  判定ロジックは `src/services/allowlist_service.py` に分離）
- Runtime: python3.12 / VPC 外
- **Timeout: 5 秒**。Cognito はトリガー応答を最大 5 秒しか待たず（変更不可）、無応答なら再試行して
  計 3 回で失敗させる仕様のため、10 秒等の設定は無意味。boto3 クライアントは botocore `Config` で
  connect/read timeout 各 1 秒程度・リトライ最大 1 回に絞り、DynamoDB 劣化時も 5 秒以内に
  応答（例外送出）が完了するようにする。Cognito 側リトライで pending 書き込みが再実行されても
  ConditionExpression により冪等。
- **`ReservedConcurrentExecutions: 10`**: SignUp フラッド（Cognito の UserCreation クォータは
  50 RPS）が同一アカウントの共有同時実行プールを食い潰して本体 API Lambda をスロットリング
  させないための隔離。本関数自身がスロットリングされてもフェイルクローズなので副作用はない。
- 専用 LogGroup: `RetentionInDays: !If [IsProd, 90, 14]`（既存規約と同一）
- 環境変数: `ALLOWLIST_TABLE`（テーブル名）
- IAM: 対象テーブルへの `dynamodb:GetItem` / `dynamodb:PutItem` のみ（最小権限）
- 許可判定（`get_status` の `GetItem`）は `ConsistentRead=True`（強整合性読み取り）を指定する。
  GetItem は既定では結果整合性のため、指定しない場合 `allowlist-remove` 直後に古い approved
  が返り、削除済み識別子の登録を許可しうる（アクセス制御判定のため強整合性が必要）。
- ログ: 構造化ログで `triggerSource` / 判定結果（allowed / rejected / pending_recorded）を必ず
  出力する。**許可リスト変更操作（データプレーン）は CloudTrail に残らないため、判定側の
  このログが実質唯一の証跡**となる。

**処理フロー（擬似コード）**

```python
def handler(event, context):
    source = event["triggerSource"]
    if source == "PreSignUp_AdminCreateUser":
        return event  # 管理者による作成は承認済みとみなす
    if source == "PreSignUp_SignUp":
        identifier = "email#" + normalize(event["request"]["userAttributes"]["email"])
        if get_status(identifier) == "approved":
            return event
        raise Exception(REJECT_MESSAGE)  # 記録しない（probe によるテーブル汚染防止）
    if source == "PreSignUp_ExternalProvider":
        identifier = "idp#" + event["userName"].lower()
        if get_status(identifier) == "approved":
            return event
        record_pending(identifier, display_name=sanitize(...), ttl=now + 30d)
        #  ↑ ConditionExpression: attribute_not_exists(identifier)
        #    既存レコード（approved / 既存 pending）を上書きしない。条件失敗は握りつぶす
        #    （Cognito のトリガー再試行に対しても冪等）
        raise Exception(REJECT_MESSAGE)
    raise Exception(REJECT_MESSAGE)  # 未知の triggerSource はフェイルクローズ
```

- `autoConfirmUser` / `autoVerifyEmail` は操作しない（既定の確認・検証フローを維持）。
- 例外はそのまま送出する。DynamoDB 障害時もサインアップが失敗する（フェイルクローズ）。
- **キルスイッチは設けない**: `RATE_LIMIT_ENABLED` のような無効化用環境変数は追加しない
  （セキュリティ制御のフェイルオープン化は事故のもと）。緊急時はコンソールで UserPool の
  トリガーを一時的に外す（CDK とのドリフトになるため、復旧後に `cdk deploy` で再配線し、
  `make verify-presignup` で配線を確認する）。

**拒否メッセージの届き方（経路により異なる）**

- 文言は全経路共通の一般文言:
  `現在、新規登録は招待制です。利用を希望する場合は管理者に連絡してください。`
- **native（メール）経路**: Hosted UI のサインアップフォームにインライン表示される。
  Cognito が `PreSignUp failed with error <メッセージ>.` と前置する既知の表示になるため
  文言は簡潔に保つ（この前置形式は保証された仕様ではなく、依存するロジックを組んではならない）。
- **LINE（federated）経路**: Hosted UI には表示されず、コールバック URL への
  `?error=...&error_description=...` リダイレクトで返る。現行 `CallbackPage.tsx` はこれを
  catch して「認証に失敗しました」を表示するため、**招待制の案内文言は LINE ユーザーには
  届かない**。承認待ちフローは「招待時に運用者が本人へ手順を事前説明する」ことで成立させる
  （数名規模の招待制なので受容）。フロントで `error_description` を安全に表示する改修は
  任意タスクとする（タスク #7）。

**Lambda Permission / Parameter（template.yaml）**

```yaml
Parameters:
  CognitoUserPoolArn:
    Type: String
    Default: ""
Rules:
  ProdRequiresCognitoUserPoolArn:   # 既存 ProdRequiresLiffOrigin / ProdRequiresUseStrands と同型
    RuleCondition: !Equals [!Ref Environment, prod]
    Assertions:
      - Assert: !Not [!Equals [!Ref CognitoUserPoolArn, ""]]
Conditions:
  HasCognitoUserPoolArn: !Not [!Equals [!Ref CognitoUserPoolArn, ""]]
Resources:
  PreSignupInvokePermission:
    Type: AWS::Lambda::Permission
    Condition: HasCognitoUserPoolArn
    Properties:
      FunctionName: !Ref PreSignupFunction
      Action: lambda:InvokeFunction
      Principal: cognito-idp.amazonaws.com
      SourceArn: !Ref CognitoUserPoolArn
Outputs:
  PreSignupFunctionArn:
    Value: !GetAtt PreSignupFunction.Arn
```

- `SourceArn` を UserPool に限定し confused deputy を防ぐ。Invoke 許可は **SAM 側で一元管理**する
  （CDK 側では作らない。後述）。
- **prod では `CognitoUserPoolArn` を必須**とする（Rules で fail-fast）。dev/staging は任意。
  SAM prod デプロイ時点で UserPool は必ず存在する（新規構築時も CDK Cognito が先）ため
  順序上の支障はない。
- **パラメータ注入は 2 経路とも対応する**:
  - `backend/Makefile` の `build_param_overrides`: `COGNITO_USER_POOL_ARN`（prod は既存
    LIFF_ORIGIN と同型の fail-fast を追加）
  - `.github/workflows/deploy.yml` の OVERRIDES 組み立て（**Makefile とは独立実装**のため
    こちらにも追加必須）: GitHub Environment Variables に `COGNITO_USER_POOL_ARN` を登録
  - `sam deploy` は未指定パラメータに UsePreviousValue を使うため、一度設定すれば以後の
    デプロイでは省略しても維持される（初回デプロイ経路だけは必ず供給すること）

### 3. CDK 配線 (CognitoStack / app.ts / prod-config.ts)

```typescript
// cognito-stack.ts
export interface CognitoStackProps extends cdk.StackProps {
  // ...既存...
  /** PreSignUp トリガー Lambda の ARN（SAM backend が所有）。未指定なら配線しない */
  preSignUpLambdaArn?: string;
}

// constructor 内
if (props.preSignUpLambdaArn) {
  this.userPool.addTrigger(
    cognito.UserPoolOperation.PRE_SIGN_UP,
    lambda.Function.fromFunctionAttributes(this, 'PreSignupFn', {
      functionArn: props.preSignUpLambdaArn,
      // Invoke 許可は SAM 側 (PreSignupInvokePermission) で一元管理する。
      // skipPermissions で CDK 側の addPermission を恒久的に no-op 化し、
      // 将来スタックに env（実アカウント）を指定した場合に Permission が
      // 二重生成される挙動変化と、env 未指定時の UnclearLambdaEnvironment
      // 警告の両方を回避する。
      sameEnvironment: false,
      skipPermissions: true,
    }),
  );
}
```

- **dev** (`app.ts`): `MEMORU_DEV_PRESIGNUP_LAMBDA_ARN`（任意。未設定ならトリガーなし＝現状維持）。
- **prod** (`prod-config.ts`): `MEMORU_PROD_PRESIGNUP_LAMBDA_ARN` を**必須**とする。
  - 既存の `REQUIRED_VARS`（VarSpec テーブル駆動）には収まらないため、ループ外の個別処理として
    実装する: **センチネル判定を先に行い**、それ以外は Lambda ARN 形式
    （`arn:aws:lambda:ap-northeast-1:...`）を検証。プレースホルダ検出は既存ガードと同一ルール。
  - **初回ブートストラップ専用**に、明示センチネル `BOOTSTRAP-NO-TRIGGER` のみ許容し、
    警告を出力してトリガーなしで synth する（SAM backend より先に Cognito を作る必要が
    あるための逃げ道。値が明示的・greppable であることで無自覚なフェイルオープンを防ぐ。
    既存 `PLACEHOLDER_PATTERNS` に一致しないことは確認済み）。

### 4. 運用 CLI（backend/Makefile）

```bash
make allowlist-add     ENV=prod ID=friend@example.com NOTE="大学の友人"  # 即 approved で登録
make allowlist-list    ENV=prod                                          # 全件表示（数件想定なので scan）
make allowlist-approve ENV=prod ID='idp#line_u1234...' NOTE="..."        # pending → approved（ttl 削除）
make allowlist-remove  ENV=prod ID=friend@example.com                    # 削除（以後の新規登録を拒否）
make verify-presignup  ENV=prod COGNITO_USER_POOL_ARN=arn:aws:cognito-idp:...  # トリガー配線の検証（後述。COGNITO_USER_POOL_ARN 必須）
```

- 実体は `aws dynamodb put-item / scan / update-item / delete-item` の薄いラッパー。
  テーブル名 `memoru-signup-allowlist-$ENV` を組み立て、メールは小文字化して `email#` を付与、
  `idp#` 始まりはそのまま使う。ID/NOTE は Make のテキスト展開（`$(ID)` 等）を経由させず、
  シェル環境変数として渡した上で `"$$ID"` のようにシェル側で参照する（値中のダブルクォート
  消失や `$(...)` のコマンド置換実行を防止）。ただし単純な `export ENV ID NOTE
  COGNITO_USER_POOL_ARN` では不十分で、コマンドライン変数（`make VAR=...`）は再帰展開のため
  export 時に値中の `$` が Make 変数参照として消費されてしまう（`NOTE='cost $5'` → `cost `。
  `$` は email local-part として正当な文字であり正しさの問題）。そのため `$(value VAR)` で
  未展開の生値を取り出し、即時変数 `ALLOWLIST_RAW_*` に固定してから export し、レシピは
  `"$$ALLOWLIST_RAW_ID"` 等を参照する。
- `allowlist-add` は `ConditionExpression: attribute_not_exists(identifier)` で誤上書きを防止
  （既存があればエラー表示。pending からの昇格は `allowlist-approve` を使う）。
- `allowlist-approve` は `ConditionExpression: attribute_exists(identifier) AND #s = :pending` を
  付け、条件失敗時は「該当する pending がありません」とエラー表示する
  （UpdateItem は対象キーが無いと**新規アイテムを作る**ため、ID コピーミスによる
  幽霊 approved レコードの無言生成を防ぐ）。
- `verify-presignup` は `aws cognito-idp describe-user-pool` の `UserPool.LambdaConfig.PreSignUp`
  が期待する Lambda ARN と一致するかを検証する（トリガー未配線・ドリフトの検知手段）。
- 認証はスイッチロール済みプロファイル前提（`AWS_PROFILE=xxx make allowlist-...`）。
  リージョンは既存の `AWS_REGION ?= ap-northeast-1` に従う。エンドポイント指定なし（実 AWS）。
- 運用 IAM には許可リストテーブル 1 本に限定した
  `GetItem/PutItem/UpdateItem/DeleteItem/Scan` + `cognito-idp:DescribeUserPool` があれば足りる。

## デプロイ手順（prod）

既存 prod（UserPool 稼働済み）前提。既存の二段階パターン（`MEMORU_PROD_API_ENDPOINT` と同型）:

0. **（新規構築時のみ）** `MEMORU_PROD_PRESIGNUP_LAMBDA_ARN=BOOTSTRAP-NO-TRIGGER` で
   CDK Cognito を先行デプロイ（この時点ではトリガーなし）
1. **SAM backend デプロイ**: `COGNITO_USER_POOL_ARN` を export して `make deploy-prod`
   → テーブル・PreSignupFunction・Invoke Permission が作成される
   （UserPool ARN は Cognito スタックの `UserPoolArn` Output から取得。CI 経由の場合は
   GitHub Environment Variables に登録しておく）
2. PreSignupFunction の ARN を Stack Output `PreSignupFunctionArn` から取得
3. `export MEMORU_PROD_PRESIGNUP_LAMBDA_ARN=<ARN>` して `npx cdk deploy MemoruCognitoProd -c stage=prod`
4. **自分（運用者）を先に登録**: `make allowlist-add ENV=prod ID=<自分のメール>`
5. **配線検証（必須）**: `make verify-presignup ENV=prod COGNITO_USER_POOL_ARN=<手順1で使った UserPool ARN>`
   で `LambdaConfig.PreSignUp` が手順 2 の ARN と一致することを確認
   （`COGNITO_USER_POOL_ARN` は必須。単独実行では省略できない）
6. **負テスト（必須）**: 未登録メールでサインアップが拒否されること / 登録済みメールで成功する
   こと / 未承認 LINE で拒否され pending が記録されることを確認
7. **既存ユーザーの棚卸し**: 手順 3 完了までサインアップは開いたままだったため、
   `make scan-users` 等で既存アカウントの作成日時・sub を確認し、心当たりのないアカウントは
   `AdminDisableUser` / `AdminDeleteUser` で排除する

> 手順 0〜3 の間はフェイルオープン（サインアップが従来どおり開いている）。作業は間隔を
> あけずに実施し、手順 5〜7 の検証・棚卸しを必ず完了させること。

## 運用フロー

- **メールの知人を招待**: `allowlist-add` で登録 → 本人にサインアップしてもらう。
  **招待から本人の登録までの間隔を短くする**（後述の先回り登録リスクの窓を狭める）。
  本人から「既にアカウントが存在する」エラーの報告があったら先回り登録を疑い、該当メールの
  UNCONFIRMED ユーザーの作成日時を確認して `AdminDeleteUser` 後に再登録してもらう。
- **LINE の知人を招待**: 招待時に「一度ログインを試す → 拒否される → 運用者が承認 →
  再ログイン」という流れを**事前に説明**する（拒否理由はフロント画面に表示されないため）。
  本人の試行後、`allowlist-list` で pending を確認。**`display_name` は本人が自由に設定できる
  攻撃者制御値なので、承認判断の根拠にしない**。必ずアウトオブバンド（LINE 等）で本人に
  ログイン試行時刻を確認し、pending の `created_at` と突合してから `allowlist-approve` する。
- **除名**: `allowlist-remove` は**新規登録を防ぐだけ**で既存アカウントは消えない。
  既存ユーザーを排除する場合は Cognito 側で `AdminDisableUser` / `AdminDeleteUser` を併用する。
- **UserPool を置換（再作成）した場合**: SAM 側 Permission の `SourceArn` が旧 ARN のまま残り
  サインアップが全停止する。`COGNITO_USER_POOL_ARN` を更新して SAM を再デプロイすること。

## セキュリティ・運用上の考慮

| 論点 | 判断 |
|---|---|
| フェイルクローズ | Lambda 例外・未知 triggerSource・DynamoDB 障害・Lambda スロットリングはすべてサインアップ失敗に倒れる。拒否された試行は UNCONFIRMED ユーザーとしても残らない |
| pending の書き込み上限 | ユニーク LINE sub につき 1 アイテム（Condition で重複書き込みなし。Cognito のトリガー再試行にも冪等）+ TTL 30 日で有界。LINE アカウント作成には電話番号が必要で大量生成コストが高い。呼び出しレートは Cognito UserCreation クォータ（50 RPS）で有界 |
| native メール試行の扱い | **記録しない**。メールアドレスは事前に分かるため pending 不要で、記録すると probe でテーブルを汚染される |
| 情報漏えい / 先回り登録 | 拒否メッセージ自体は存在有無を漏らさない一般文言。ただし **SignUp の成功 / `UsernameExistsException` 自体が許可リスト・アカウント存在のオラクルになる**（`preventUserExistenceErrors` はサインイン系 API のみ対象で、サインアップは保護しない）。帰結として「許可済み・未登録メール」を推測した攻撃者による先回り登録（squat / pre-hijacking）が理論上可能。個人運用・招待メールの推測困難性・招待〜登録の短い時間窓から**残余リスクとして受容**し、運用フローの検知・回復手順（UNCONFIRmed 確認 → AdminDeleteUser）でカバーする |
| 本人によるメール変更 | **現行構成では不可能**（クライアントに `aws.cognito.signin.user.admin` スコープがなく、`userSrp/custom` フロー無効で当該スコープ付きトークンの取得経路もない）ことを不変条件とする。**この前提を変える変更（スコープ追加・authFlows 有効化・AdminUpdateUserAttributes を使う API の追加）を行う場合は、`UserAttributeUpdateSettings` の導入と許可リスト整合の再設計を必須とする** |
| display_name の信頼性 | 攻撃者制御値。保存時に長さ制限 + 制御文字除去。承認判断はアウトオブバンドの本人確認 + created_at 突合で行う |
| 監査 | **許可リスト変更（DynamoDB データプレーン操作）の証跡は残らない**（データイベントは有効化しない。単独運用者のため受容）。判定側の証跡として PreSignupFunction の構造化ログ（triggerSource・判定結果）を CloudWatch Logs に残す |
| 検知 | `make verify-presignup` でトリガー配線を確認可能にする。任意で PreSignupFunction の Errors / Throttles / Invocations 急増の CloudWatch アラームを追加（probe 検知を兼ねる。既存アラーム群への追加は任意タスク） |
| 同時実行の隔離 | `ReservedConcurrentExecutions: 10` で SignUp フラッドによる共有同時実行プールの枯渇（本体 API への波及）を防ぐ |
| 将来の強化 | 入口自体も閉じたくなったら `selfSignUpEnabled: false` へ変更（1 行 + 再デプロイ。UserPool 置換なし）。本設計とは独立に追加可能 |

## テスト方針

- **backend (pytest + moto)** — カバレッジ 80% 目標に含める:
  - approved メール → 許可 / 未登録メール → 拒否・**テーブルに書き込みなし**
  - approved LINE → 許可 / 未登録 LINE → pending 書き込み + 拒否
  - 既存 pending の LINE が再試行 → 上書きなし（Condition 失敗を握りつぶし）+ 拒否
  - AdminCreateUser → 無条件許可 / 未知 triggerSource → 拒否
  - DynamoDB 例外 → 送出（フェイルクローズ）
  - メール正規化（大文字・前後空白）/ display_name のサニタイズ（長さ・制御文字）
- **backend (template レベル pytest)** — 既存 `test_template_params.py` 等の慣行に倣い
  `tests/test_template_presignup.py` を追加: `CognitoUserPoolArn` Parameter（既定値 ""）/
  `ProdRequiresCognitoUserPoolArn` Rule / `HasCognitoUserPoolArn` Condition /
  Permission の Principal・SourceArn / テーブル定義・TTL / ReservedConcurrentExecutions
- **infrastructure/cdk (Jest)**:
  - `preSignUpLambdaArn` 指定時に `LambdaConfig.PreSignUp` が設定される / 未指定時はなし
    （optional prop のため既存 snapshot は不変）
  - prod-config: 未設定・プレースホルダ・不正 ARN の拒否、`BOOTSTRAP-NO-TRIGGER` の許容
- **template**: `sam validate --lint` / `cdk synth --all`（既存 CI job でカバー）

## タスク分割（実装順）

| # | タスク | 内容 |
|---|---|---|
| 1 | SAM リソース | テーブル / PreSignupFunction（Timeout 5s・Reserved 10・LogGroup）/ Permission / Parameter / Rules / Output |
| 2 | backend 実装 | `src/auth/pre_signup.py` / `src/services/allowlist_service.py` + pytest（単体 + template テスト） |
| 3 | CDK 配線 | CognitoStack props（fromFunctionAttributes + skipPermissions）/ app.ts / prod-config ガード + Jest |
| 4 | Makefile / CI | `allowlist-add / list / approve / remove / verify-presignup` + `COGNITO_USER_POOL_ARN` 注入（**Makefile と deploy.yml の両方**。prod fail-fast 含む） |
| 5 | ドキュメント | deployment-guide-prod（2 章にセンチネル・3 章後に Cognito 再デプロイの往復を既存 API_ENDPOINT 注記と同型で追記。Variables 一覧に `COGNITO_USER_POOL_ARN` 追加）/ README（環境変数・運用手順） |
| 6 | （任意）監視 | PreSignupFunction の Errors / Throttles / Invocations アラームを既存アラーム群に追加 |
| 7 | （任意）フロント | `CallbackPage.tsx` で `error_description` を安全に表示（文言の前置形式には依存しない） |
