# Memoru LIFF - 本番環境デプロイ手順書（prod）

> 対象: AWS 本番環境（prod）のデプロイ手順と、実環境値の管理方針。
>
> dev 環境の構築手順は [deployment-guide-dev.md](./deployment-guide-dev.md) を参照。
> 本書は dev 手順を一通り理解していることを前提に、**prod 固有の差分（実環境値の外部注入）** を中心に説明する。

## 0. 方針: 実環境値をコミットしない

本リポジトリは **public** のため、prod / dev の実環境値（ドメイン・証明書 ARN・HostedZone ID・LINE Channel ID・Cognito UserPool ID 等）を **Git にコミットしない**。

- これらの値は **GitHub Environments（Variables / Secrets）** と **デプロイ実行者のローカル環境変数** にのみ存在する。
- CDK（`infrastructure/cdk/bin/app.ts`）と SAM（`backend/Makefile` / `deploy.yml`）は、これらの値を **環境変数から外部注入** する。
- 値が不足している / `example.com`・`placeholder` 等のプレースホルダが混入している場合は、**synth / deploy を明確なエラーで中断** する（誤った値での本番デプロイを防止）。

> CDK H-2 / I-1 / I-2 の恒久対応。

---

## 1. 必要な値の一覧

### 1.1 CDK（インフラ）用の値

prod スタック（`MemoruCognitoProd` / `MemoruKeycloakProd` / `MemoruLiffHostingProd`）の synth / deploy に必要。**すべてローカル環境変数として `export`** する（CDK デプロイはユーザーが手動実行するため、GitHub Actions では使用しない）。

| 環境変数 | 説明 | 取得場所 | 種別 |
|----------|------|---------|------|
| `MEMORU_PROD_HOSTED_ZONE_NAME` | ルートドメイン名（例: `memoru.app`） | Route 53 → Hosted zones | 識別子 |
| `MEMORU_PROD_HOSTED_ZONE_ID` | Hosted Zone ID（例: `Z...`） | Route 53 → Hosted zone details | 識別子 |
| `MEMORU_PROD_KEYCLOAK_DOMAIN` | Keycloak の FQDN（例: `keycloak.memoru.app`） | 自分で決定（Route 53 に A レコードが作成される） | 識別子 |
| `MEMORU_PROD_KEYCLOAK_CERT_ARN` | Keycloak ALB 用 ACM 証明書 ARN（**ap-northeast-1**） | ACM（ap-northeast-1） | 識別子 |
| `MEMORU_PROD_LIFF_DOMAIN` | LIFF の FQDN（例: `liff.memoru.app`） | 自分で決定（CloudFront に割り当て） | 識別子 |
| `MEMORU_PROD_LIFF_CERT_ARN` | CloudFront 用 ACM 証明書 ARN（**us-east-1 必須**） | ACM（us-east-1） | 識別子 |
| `MEMORU_PROD_COGNITO_DOMAIN_PREFIX` | Cognito Hosted UI ドメインプレフィックス（グローバル一意） | 自分で決定 | 識別子 |
| `MEMORU_PROD_CALLBACK_URLS` | Cognito コールバック URL（カンマ区切り） | LIFF ドメイン由来（例: `https://liff.memoru.app/callback`） | 識別子 |
| `MEMORU_PROD_LOGOUT_URLS` | Cognito ログアウト URL（カンマ区切り） | LIFF ドメイン由来（例: `https://liff.memoru.app/`） | 識別子 |
| `LINE_LOGIN_CHANNEL_ID` | LINE Login チャネル ID（Cognito LINE IdP 用） | LINE Developers Console → LINE Login チャネル → Basic settings | 識別子 |
| `LINE_LOGIN_CHANNEL_SECRET_NAME` | LINE Login Channel Secret を格納した Secrets Manager の名前 | Secrets Manager（事前登録） | 秘密参照 |
| `MEMORU_PROD_API_ENDPOINT` | バックエンド API のオリジン（例: `https://xxxx.execute-api.ap-northeast-1.amazonaws.com`。パスは含めない）。CloudFront の CSP `connect-src` に許可される | SAM Stack Output（`ApiEndpoint` のオリジン部分） | 識別子 |
| `MEMORU_PROD_PRESIGNUP_LAMBDA_ARN` | サインアップ許可リスト（signup-allowlist）の PreSignUp トリガー Lambda の ARN。Cognito UserPool にトリガーとして配線される | SAM Stack Output（`PreSignupFunctionArn`） | 識別子 |

> **ガードの挙動**:
> - 必須変数が **未設定 / 空文字** → 不足変数名を列挙してエラー。
> - `example.com` / `placeholder` / `your-domain` / `<...>` / ダミー値（`123456789012`・`Z0123456789ABCDEF`）/ `TODO` を含む → プレースホルダとして拒否。
> - 証明書 ARN のリージョンが期待と異なる（Keycloak は `ap-northeast-1`、LIFF は `us-east-1`）→ 拒否。
> - prod は平文の `LINE_LOGIN_CHANNEL_SECRET` を受け付けない（`LINE_LOGIN_CHANNEL_SECRET_NAME` で Secrets Manager 参照を強制）。
> - `MEMORU_PROD_PRESIGNUP_LAMBDA_ARN` は **必須**だが、初回ブートストラップ時（SAM backend をまだデプロイしておらず実 ARN が存在しない）に限り、明示的なセンチネル値 `BOOTSTRAP-NO-TRIGGER` を許容する。この場合は警告を出力した上で PreSignUp トリガーを配線せずに synth/deploy する（既存 `PLACEHOLDER_PATTERNS` には一致しないため、通常のプレースホルダ検出はすり抜けない）。詳細は本書「4. サインアップ許可リストの有効化と検証」を参照。

### 1.2 SAM（バックエンド）用の値

`make deploy-prod`（手動）または `deploy.yml` の `deploy-backend` job（CI）で `--parameter-overrides` として注入する。

| 値 | 説明 | 取得場所 | 設定先 | 必須/任意 |
|----|------|---------|--------|-----------|
| `OIDC_ISSUER` | OIDC Issuer URL（Cognito の場合 `https://cognito-idp.ap-northeast-1.amazonaws.com/<UserPoolId>`、Keycloak の場合 `https://<keycloakDomain>/realms/memoru`） | Cognito Stack Output / Keycloak | GitHub Env Variables / ローカル `export` | **必須** |
| `OIDC_AUDIENCE` | OIDC Audience。Cognito の場合は **UserPool Client ID** | Cognito Stack Output | GitHub Env Variables / ローカル `export` | **必須** |
| `LIFF_ORIGIN` | LIFF フロントの Origin（例: `https://liff.memoru.app`）。CORS `AllowOrigins` に注入する | LIFF ドメイン由来 | GitHub Env Variables / ローカル `export` | **prod は必須**（未設定なら fail-fast。dev/staging は任意） |
| `COGNITO_USER_POOL_ARN` | サインアップ許可リストの PreSignupFunction に対する Invoke 許可（`AWS::Lambda::Permission` の `SourceArn`）に使う Cognito UserPool の ARN | Cognito Stack Output（`UserPoolArn`） | GitHub Env Variables / ローカル `export` | **prod は必須**（未設定なら fail-fast。template.yaml の `Rules`（`ProdRequiresCognitoUserPoolArn`）でも二重にガードされる。dev/staging は任意） |
| `LINE_CHANNEL_ID` | LINE ID トークン検証用 Channel ID | LINE Developers Console | GitHub Env Variables / ローカル `export` | 任意（未設定なら検証無効） |
| `USE_STRANDS` | Strands Agents SDK 有効化。Tutor 機能（SessionManager 経由のマルチターン会話）に必須 | 運用方針で決定 | GitHub Env Variables / ローカル `export` | **prod は `true` が必須**（未設定/`false` なら fail-fast。template.yaml の Rules（`ProdRequiresUseStrands`）でも二重にガード。dev/staging は任意） |
| `TUTOR_SESSION_BACKEND` | チューターセッション履歴バックエンド（`dynamodb` / `agentcore`） | 運用方針で決定 | GitHub Env Variables / ローカル `export` | 任意（既定 `dynamodb`） |
| `AGENTCORE_MEMORY_ID` | AgentCore Memory ID（`TutorSessionBackend=agentcore` 時に必須） | `aws bedrock-agentcore create-memory` | GitHub Env Variables / ローカル `export` | 任意 |
| `BEDROCK_MODEL_ID` | Bedrock モデル ID（`global.` 始まりの推論プロファイル） | 運用方針で決定 | GitHub Env Variables / ローカル `export` | 任意（template 既定値） |

### 1.3 Secrets Manager で管理する値（参考）

以下は環境変数ではなく **AWS Secrets Manager** に直接登録する秘密情報。CDK / SAM は名前（ARN）でのみ参照する。

| シークレット名 | 内容 | 種別 |
|---------------|------|------|
| `memoru-prod-line-credentials` | LINE Messaging API の `channelSecret` / `channelAccessToken`（Webhook・Due Push 用） | 秘密 |
| `LINE_LOGIN_CHANNEL_SECRET_NAME` が指す名前 | LINE Login Channel Secret（Cognito LINE IdP 用） | 秘密 |
| Keycloak admin 認証情報（Keycloak Stack が生成） | Keycloak 管理者パスワード等 | 秘密 |

> GitHub Secrets として登録するのは `AWS_DEPLOY_ROLE_ARN`（OIDC 認証用 IAM ロール）のみ。実値の識別子は GitHub **Variables**、秘密は **Secrets Manager** に置く、という棲み分け。

---

## 2. CDK prod デプロイ手順

CDK のデプロイはユーザーが手動で実行する。

### 2.1 実環境値を環境変数に設定

```bash
export MEMORU_PROD_HOSTED_ZONE_NAME="memoru.app"
export MEMORU_PROD_HOSTED_ZONE_ID="Z0XXXXXXXXXXXXXX"
export MEMORU_PROD_KEYCLOAK_DOMAIN="keycloak.memoru.app"
export MEMORU_PROD_KEYCLOAK_CERT_ARN="arn:aws:acm:ap-northeast-1:<ACCOUNT_ID>:certificate/xxxx"
export MEMORU_PROD_LIFF_DOMAIN="liff.memoru.app"
export MEMORU_PROD_LIFF_CERT_ARN="arn:aws:acm:us-east-1:<ACCOUNT_ID>:certificate/yyyy"
export MEMORU_PROD_COGNITO_DOMAIN_PREFIX="memoru-prod"
export MEMORU_PROD_CALLBACK_URLS="https://liff.memoru.app/callback"
export MEMORU_PROD_LOGOUT_URLS="https://liff.memoru.app/"
export LINE_LOGIN_CHANNEL_ID="1234567890"
export LINE_LOGIN_CHANNEL_SECRET_NAME="memoru-prod-line-channel-secret"
export MEMORU_PROD_API_ENDPOINT="https://xxxx.execute-api.ap-northeast-1.amazonaws.com"
export MEMORU_PROD_PRESIGNUP_LAMBDA_ARN="arn:aws:lambda:ap-northeast-1:<ACCOUNT_ID>:function:memoru-presignup-prod"
```

> `MEMORU_PROD_API_ENDPOINT` は CloudFront の CSP `connect-src` に配線される。未設定・プレースホルダはガードで拒否される。SAM バックエンドを先にデプロイして `ApiEndpoint` Output のオリジン部分を控えておくこと（バックエンドが未デプロイの段階では、後で正しい値を設定して `MemoruLiffHostingProd` を再デプロイする）。

> `MEMORU_PROD_PRESIGNUP_LAMBDA_ARN` も同様に SAM 側リソース（`PreSignupFunction`）の Stack Output に依存する。新規構築時は、まず `MEMORU_PROD_PRESIGNUP_LAMBDA_ARN=BOOTSTRAP-NO-TRIGGER` で `MemoruCognitoProd` を先行デプロイ（PreSignUp トリガー未配線の状態で UserPool を作成）→ SAM backend デプロイ後に Stack Output `PreSignupFunctionArn` の実 ARN を設定して `MemoruCognitoProd` を再デプロイする、という往復が必要。詳細手順は本書「4. サインアップ許可リストの有効化と検証」を参照。

> これらの `export` を `.envrc`（direnv）や 1Password CLI 等で管理し、シェル履歴やファイルに残さない運用を推奨。

### 2.2 synth で検証 → deploy

```bash
cd infrastructure/cdk
npm run build

# 検証（必須変数の不足/プレースホルダがあればここでエラー中断）
npx cdk synth --all -c stage=prod

# デプロイ（推奨順）
npx cdk deploy MemoruCognitoProd     -c stage=prod
npx cdk deploy MemoruKeycloakProd    -c stage=prod
npx cdk deploy MemoruLiffHostingProd -c stage=prod
```

ガードが働くと、不足変数名を列挙したエラーで synth が止まる:

```
Error: prod スタックの生成に必要な環境変数が不足/不正です。
...
[未設定の必須変数]
  - MEMORU_PROD_KEYCLOAK_CERT_ARN
[プレースホルダ値が検出された変数（example.com / placeholder 等は不可）]
  - MEMORU_PROD_LIFF_DOMAIN
```

> `-c stage=prod` を付けない限り prod スタックは生成されない（既定は dev のみ）。CI の `cdk synth --all` は dev のみ対象なので、prod の実値がなくても CI は通る。

---

## 3. SAM prod デプロイ手順

### 3.1 CI（GitHub Actions）でデプロイする場合

1. GitHub リポジトリ → Settings → Environments → `prod` を作成（未作成の場合）。
   - **Deployment branch policy** を `Selected branches` に設定し、`main` のみを許可する。
     これが prod への手動デプロイをブランチ制限する **本来の防御主体**（`deploy.yml` 側にも
     `github.ref != 'refs/heads/main'` を fail させる補助的なガードがあるが、
     ワークフロー定義自体は未マージのブランチ上で改変され得るため、それだけに頼らないこと）。
   - **Required reviewers** を設定し、prod への `workflow_dispatch` 実行前に承認を必須にする
     （誤操作・悪意ある操作の両方に対する追加の防御層）。
2. `prod` Environment の **Variables** に以下を登録:
   - `OIDC_ISSUER`（必須）
   - `OIDC_AUDIENCE`（必須）
   - `LIFF_ORIGIN`（必須。LIFF フロントの Origin。例: `https://liff.memoru.app`）
   - `LINE_CHANNEL_ID`（任意）
   - `USE_STRANDS`（**prod は `true` が必須**。`false`/未設定は `deploy-backend` job が fail-fast し、
     template.yaml の `Rules`（`ProdRequiresUseStrands`）でも二重にガードされる）
   - `COGNITO_USER_POOL_ARN`（**prod は必須**。サインアップ許可リスト（signup-allowlist）の
     PreSignupFunction に対する Invoke 許可（`SourceArn`）に使用。Cognito Stack Output
     `UserPoolArn` から取得。未設定は `deploy-backend` job が fail-fast し、template.yaml の
     `Rules`（`ProdRequiresCognitoUserPoolArn`）でも二重にガードされる）
   - 必要に応じて `TUTOR_SESSION_BACKEND` / `AGENTCORE_MEMORY_ID` / `BEDROCK_MODEL_ID`
   - フロントエンド用: `API_URL` / `LIFF_ID` / `OIDC_AUTHORITY` / `OIDC_CLIENT_ID` / `FRONTEND_BUCKET` / `CLOUDFRONT_DISTRIBUTION_ID`
     （`deploy-frontend` job が非空チェック・URL 形式チェック・プレースホルダ値検出を行い、
     不正な場合は fail-fast してビルド・S3 公開を中断する）
3. `prod` Environment の **Secrets** に `AWS_DEPLOY_ROLE_ARN` を登録。
4. Actions → **Deploy to AWS** → Run workflow → environment = `prod` を選択して実行。

`deploy-backend` job は `environment: prod` コンテキストで `prod` の Variables を解決し、`--parameter-overrides` を組み立てて `sam deploy` に渡す。必須 Variables（`OIDC_ISSUER` / `OIDC_AUDIENCE`）または prod 用の `LIFF_ORIGIN` / `COGNITO_USER_POOL_ARN` / `USE_STRANDS=true` が未設定なら job を fail させる。

### 3.2 手動でデプロイする場合

```bash
cd backend
export OIDC_ISSUER="https://cognito-idp.ap-northeast-1.amazonaws.com/ap-northeast-1_XXXXXXXXX"
export OIDC_AUDIENCE="<UserPool Client ID>"
export LIFF_ORIGIN="https://liff.memoru.app"
export COGNITO_USER_POOL_ARN="arn:aws:cognito-idp:ap-northeast-1:<ACCOUNT_ID>:userpool/ap-northeast-1_XXXXXXXXX"
export LINE_CHANNEL_ID="1234567890"
export USE_STRANDS="true"
# 任意: export TUTOR_SESSION_BACKEND=agentcore AGENTCORE_MEMORY_ID=... BEDROCK_MODEL_ID=...

make deploy-prod
```

`make deploy-prod` は環境変数から `--parameter-overrides` を組み立てる:

- **必須**（`OIDC_ISSUER` / `OIDC_AUDIENCE`、prod は `LIFF_ORIGIN` / `COGNITO_USER_POOL_ARN` も）が未設定なら、不足変数名を表示して **fail-fast**。`LIFF_ORIGIN` は template.yaml の `Rules`（`ProdRequiresLiffOrigin`）、`COGNITO_USER_POOL_ARN` は同じく `Rules`（`ProdRequiresCognitoUserPoolArn`）でも二重にガードされる。
- **任意** 変数は設定されている場合のみ override に追加（未設定なら template.yaml の既定値を使用。空文字は渡さない）。
- `LINE_CHANNEL_ID` 未設定時は警告のみ表示して続行（template 既定 `""` と同じ挙動）。

---

## 3.5 ai-async-jobs のデプロイ順序（重要）

AI 系エンドポイントは非同期ジョブ（202 + job_id + ポーリング）に変換されている
（docs/design/ai-async-jobs/）。**フロントエンドを先にデプロイすること**:

- 新フロントは「2xx かつ body に job_id なし → 旧同期形式」のデュアル対応を持つため、
  旧バックエンドとの組み合わせでも動作する（フロント先行は安全）
- 逆順（旧フロント + 新バックエンド）は、旧フロントが 202 の `{job_id, ...}` を
  成功レスポンスとして解釈し UI が静かに壊れるため**不可**

> **CI はこの順序を強制する**: `deploy.yml` の `deploy-backend` job は
> `needs: [test-backend, test-frontend, deploy-frontend]` かつ
> `if: ... && needs.deploy-frontend.result == 'success'` を持つため、
> `deploy-frontend` の完了（成功）後にのみ実行される。`deploy-frontend` が失敗・
> スキップされた場合は `deploy-backend` も自動的にスキップされる（安全側）。
> 手動デプロイ（`make deploy-prod` 等）の場合はこの保護がないため、
> 上記の順序を手動で守ること。

---

## 4. サインアップ許可リストの有効化と検証（signup-allowlist）

Cognito PreSignUp トリガー + DynamoDB 許可リストにより、prod のサインアップ（メールの
セルフサインアップ / LINE 初回ログイン）を「運用者＋招待した知人」に限定する。設計判断・
identifier 正規化規則・運用フロー（招待・承認・除名）の詳細は
[signup-allowlist アーキテクチャ設計](design/signup-allowlist/architecture.md) を参照。
以下は既存 prod（UserPool 稼働済み）を前提としたデプロイ手順の要約。

0. **（新規構築時のみ）** `MEMORU_PROD_PRESIGNUP_LAMBDA_ARN=BOOTSTRAP-NO-TRIGGER` で
   `MemoruCognitoProd` を先行デプロイする（この時点では PreSignUp トリガー未配線）。
1. **SAM backend デプロイ**: `COGNITO_USER_POOL_ARN`（Cognito Stack Output `UserPoolArn`）を
   export して `make deploy-prod` を実行する（CI の場合は GitHub Environment Variables に
   `COGNITO_USER_POOL_ARN` を登録しておく）。`SignupAllowlistTable` / `PreSignupFunction` /
   Invoke Permission が作成される。
2. Stack Output `PreSignupFunctionArn` から PreSignupFunction の ARN を取得する。
3. `MEMORU_PROD_PRESIGNUP_LAMBDA_ARN=<手順 2 の ARN>` を export し、
   `npx cdk deploy MemoruCognitoProd -c stage=prod` で再デプロイする（2 章の手順に従う）。
4. **自分（運用者）を先に登録する**: `make allowlist-add ENV=prod ID=<自分のメール> NOTE="..."`
5. **配線検証（必須）**: `make verify-presignup ENV=prod COGNITO_USER_POOL_ARN=<UserPoolArn>`
   を実行し、UserPool の `LambdaConfig.PreSignUp` が手順 2 の ARN と一致することを
   確認する（`COGNITO_USER_POOL_ARN` は手順 1 と同じ UserPool ARN。単独実行の場合は
   必須のため省略不可）。
6. **負テスト（必須）**: 未登録メールでサインアップが拒否されること／登録済みメールで成功する
   こと／未承認の LINE アカウントで拒否され pending が記録されることを確認する。
7. **既存ユーザーの棚卸し**: 手順 0〜3 の間はサインアップが従来どおり開いていたため、
   `make scan-users` 等で既存アカウントの作成日時・sub を確認し、心当たりのないアカウントは
   `AdminDisableUser` / `AdminDeleteUser` で排除する。

> 手順 0〜3 の間はフェイルオープン（サインアップが従来どおり開いている）。作業は間隔を
> あけずに実施し、手順 5〜7 の検証・棚卸しを必ず完了させること。

日常運用（招待の追加・承認待ちの確認・承認・除名）は `make allowlist-add` /
`make allowlist-list` / `make allowlist-approve` / `make allowlist-remove` を使う。
コマンド例・LINE ユーザーの承認時に必要な本人確認手順は設計文書の「運用 CLI」「運用フロー」
節を参照。

---

## 5. 関連ドキュメント

- [deployment-guide-dev.md](./deployment-guide-dev.md): dev 環境のゼロからの構築手順。SAM デプロイは本書と同じ「環境変数 + make deploy-dev」方式。
- [signup-allowlist アーキテクチャ設計](design/signup-allowlist/architecture.md): サインアップ許可リストの設計判断・運用フローの詳細。
- [README.md](../README.md): CI/CD と GitHub Secrets/Variables の概要。
