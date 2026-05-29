# Claude × Codex 合同コードレビュー（2026-05-29）

**レビュー日**: 2026-05-29
**参加**: Claude (Opus 4.8, 1M context) ＋ Codex MCP (`mcp__codex__codex`, GPT 系)
**対象**: `main` ブランチ全体（backend / frontend / infrastructure）
**手法**: Claude が実コードを精読 → 主要論点を提示 → Codex が独立検証＋追加指摘 → 突き合わせ → 重大度を合意
**前提**: [README.md](./README.md) のフォローアップ（Critical #1〜#5 / High #6,#7 マージ済み、#8〜#16 残課題、PR #33 オープン）

> このファイルは README の続報。前回 Done とした項目の再検証結果と、今回新たに発見した問題（合意済み）を記録する。

---

## 運用前提の確認（2026-05-29 ユーザー回答反映）

レビュー後にユーザーへ確認した結果を以下に反映する。

- **本番は `USE_STRANDS=true` 想定** → N-1 の Tutor 500 は運用設定で回避される見込み。ただし `template.yaml` の既定値は `false`（`Parameters.UseStrands.Default`）であり、**設定し忘れて既定のままデプロイすると Tutor が原因不明の 500 で全滅する罠は残る**。対応として (a) 既定を `true` にする、または (b) `create_tutor_ai_service`／`TutorService` 初期化時に「session_manager 利用なのに非 Strands」を**起動時バリデーションで明示エラー化**することを推奨。N-1 の技術重大度は High のままだが、実害の発生は「設定次第」。
- **現在デプロイ環境がない** → C-2（`/cards/generate-from-url` 常時 500）は**実機未確認**。ただしコード上は `boto3.client("bedrock-agentcore-browser")` が `UnknownServiceError` を投げるため、**デプロイすれば確実に顕在化する既知の不具合**。PR #33（無効化）のマージか browser_service の本実装を、URL カード生成機能を公開する**前に**必ず決着させること。

---

## エグゼクティブサマリ

全体の作り込みは良好（in-flight ロック、SSRF のリダイレクト都度再検証、Webhook の定数時間署名比較、DynamoDB の PITR/KMS/DeletionProtection、`update_last_notified_date` の冪等ガード等）。一方で **「デフォルト設定のままだと主要機能が動かない／本番で事故る」構成上の地雷**が複数残っており、これが今回の最重要発見。

加えて、**前回レビューの結論を 1 件訂正する**（#8、後述）。

### 🔴 最優先 High（10 件、Claude/Codex 合意済み）

| ID | 内容 | 発見 | 箇所 |
|---|---|---|---|
| **N-1** | `USE_STRANDS=false`（template 既定）だと Tutor が全滅。`TutorService` は常に SessionManager を渡すが `BedrockTutorAIService` は拒否例外を投げ、それが `TutorServiceError` 継承外のため handler で捕まらず汎用 500 | Claude | `tutor_ai_service.py:123-127` / `tutor_service.py:178,309` / `tutor_handler.py:84-91,152-159` / `template.yaml:65-71` |
| **C-2** | `/cards/generate-from-url` が **profile_id の有無に関係なく常時 500**。`UrlContentService(browser_service=BrowserService())` を無条件生成し、`boto3.client("bedrock-agentcore-browser")` が `UnknownServiceError`（PR #33 未マージの帰結） | Codex | `ai_handler.py:177` / `browser_service.py:31` |
| **N-5** | LINE Webhook が URL fetch＋Bedrock 生成＋push を **同期実行**。LINE は ~2 秒で応答必須のため、超過するとリトライ→二重カード生成・二重課金 | Claude（Codex 根拠補強） | `line_handler.py:185-307,503-581` |
| **N-6** | Webhook イベントに **冪等キーがない**（`webhookEventId`/`isRedelivery` 未保持）。再配信で `handle_grade_action` 二重実行→レビュー二重記録 | Claude（Codex 確認） | `line_handler.py:558-575` / `line_service.py:47-56,150-188` |
| **C-1** | `submit_review` の SRS パラメータが **ConditionExpression なし上書き**。`review_history` のみ `list_append`。同時 submit で repetitions/ease_factor が lost update（Tutor #7 は守ったのに review は無防備という非対称）。重大度 **Medium-High** | Codex | `review_service.py:148→291-359` |
| **N-7** | URL fetch に **レスポンスサイズ上限なし**（`response.text` 全読み込み）。巨大ページでメモリ枯渇 | Claude（Codex 確認） | `url_content_service.py:121,141-161` |
| **N-8 / #12** | 二重通知が実質未解決。冪等ガードは push の **後**に呼ぶ順序のため並行実行で push が複数飛ぶ。さらに戻り値 `False` を無視して `sent += 1` し統計も不正確 | Claude＋README（Codex 補強） | `notification_service.py:135-169` / `user_service.py:254-258` |
| **N-4 / Front S-1** | refresh_token を含む全トークンが localStorage に永続保存（`oidc-client-ts` の `userStore` 未指定＝既定 localStorage）。XSS 時の被害最大化 | Front agent | `config/oidc.ts:42-74` |
| **CDK H-1** | dev Keycloak（IdP）が **平文 HTTP で全世界公開**（ALB 80 のみ／ECS public subnet＋public IP）。資格情報・トークン盗聴可能 | CDK agent | `keycloak-stack.ts:172-178` / `app.ts:35-40` |
| **CDK H-2** | prod の証明書 ARN／ドメイン／HostedZone が **プレースホルダのままハードコード**。ダミー ARN が非空のため `isProd && !certificateArn` ガードを素通り | CDK agent | `app.ts:58-78` |

---

## ⚠️ 重要な訂正 — #8 stage prefix 補正は「削除非推奨」

README #8 は `handler.py:233-236` の stage prefix 補正を「調査の上、削除」候補としていた。**今回の合同検証でこの方針を撤回する**（Claude の当初見解が誤り、Codex が正しかった）。

`aws_lambda_powertools` 2.x の `APIGatewayProxyEventV2.path`（実物 `.venv/.../api_gateway_proxy_event.py:316-321`）:

```python
@property
def path(self) -> str:
    stage = self.request_context.stage
    if stage != "$default":
        return self.raw_path[len("/" + stage):]   # ← 無条件で /{stage} を除去
    return self.raw_path
```

ルーティングは `api_gateway.py:2631` の `path = self._remove_prefix(self.current_event.path)` でこの `.path` を使う。つまり **非 `$default` ステージでは rawPath 先頭の `/{stage}` を無条件除去する**。

| 状況 | 補正なし | 補正あり（現状） |
|---|---|---|
| `rawPath="/prod/cards"`（ステージ込み） | `.path` → `/cards` ✅ | startswith で発火せず → `/cards` ✅ |
| `rawPath="/cards"`（ステージ無し構成） | `.path` → `"/cards"[5:]="rds"` → **404** ❌ | `/prod/cards` に補正 → `.path` → `/cards` ✅ |

→ 補正は「rawPath にステージが含まれない構成」で Powertools の無条件 strip による**誤切り詰めを防ぐ必要な防御**。安易に削除するとカスタムドメイン＋API マッピング等の構成で全ルートが 404 になる。

**残る改善余地（Medium）**: より明示的にするなら `APIGatewayHttpResolver(strip_prefixes=[...])` の利用や、実環境の `rawPath`/`requestContext.stage` を CloudWatch で確認した上でのコメント補強。ただし現状コードはどの構成でも安全側に倒れる。`grade_ai_handler`/`advice_handler` は独立 Lambda で `app.resolve` を経由せず単一エンドポイント固定のため、この補正非適用でも実害なし。

---

## 統合指摘一覧

### 🟠 Medium

| ID | 内容 | 発見 | 箇所 |
|---|---|---|---|
| **C-6** | `link_line` の並行 race。GSI は一意制約でないため、同じ `line_user_id` を別 user が同時 link すると両方成功し得る。`get_user_by_line_id` は先頭1件のみ返すため Webhook の user 解決が不定化 | Codex | `user_service.py:151-172,191-199` |
| **C-3** | URL 保存 postback が長い URL で壊れる。コメントは「reference key を使う（300字制限）」と書くが実際は `quote(page_url)` を丸ごと埋め込み。URL は 2048 字まで許可されるため Flex 送信失敗→保存導線消失 | Codex | `flex_messages.py:513-514` / `url_generate.py:11-14` |
| **C-4** | URL 生成が chunk 数に比例して Bedrock を無制限呼び出し。`cards_per_chunk = max(3, ...)` で全 chunk ループ、最後に `target_count` で切り捨て。`target_count` がコスト/時間上限になっていない（N-5 と相乗） | Codex | `bedrock.py:177-204` / `ai_handler.py:213` |
| **#9** | SSRF: リダイレクト先は都度 `validate_url` 済み（良好）だが、事前 DNS 解決のみで httpx 接続時に再解決されるため TOCTOU / DNS rebinding が残る | README（両者同意） | `url_validator.py:82-94,130-132` / `url_content_service.py:123-134` |
| **#11** | Deck 集計が user 全カード Query。`get_deck_card_counts` は GSI すら未使用で全件走査、`get_deck_due_counts` も due GSI 全件。カード数に線形比例（TODO コメント有） | README（Codex 同意） | `deck_service.py:363-382,410-432` |
| **Front S-2** | `automaticSilentRenew:true` だが `/silent-renew` ルート・`signinSilentCallback` が未実装で自動リフレッシュが機能しない | Front agent | `config/oidc.ts:69,73` / `App.tsx` |
| **Front A-3** | `useAuth` がトークン更新/失効イベントを未購読（マウント時 1 回のみ取得）。失効後も `isAuthenticated` が true のままになり得る | Front agent | `hooks/useAuth.ts:57-94` |
| **Front E-3** | 422 業務エラーをエラーメッセージの**文字列一致**で判定（`api.ts` が status/code を捨てている）。文言変更・i18n で破綻 | Front agent | `contexts/TutorContext.tsx:105-118` |
| **CDK M-1〜M-4** | dev CloudFront が default 証明書で TLS1.0/1.1 許容／dev ECS が public 直結で RDS と同一 VPC／Cognito セルフサインアップ＋MFA OPTIONAL／prod Keycloak desiredCount=1＋NAT 単一で可用性弱 | CDK agent | `liff-hosting-stack.ts` / `keycloak-stack.ts` / `cognito-stack.ts` |
| **N-9** | `make lint` の `mypy src/` が **114 errors / 29 files**、大半が `import-not-found`（`api.shared`・`models.tutor` 等が解決不可）。src レイアウトに対する mypy 設定（`mypy_path` / `namespace_packages` / `explicit_package_bases` 等）が無く、**型チェックが実質機能していない**（CI で型退行を検出できない）。N-1 対応中に発見 | Claude | `Makefile`(lint) / mypy 設定不在 |

### 🟢 Low / Low-Medium

| ID | 内容 | 発見 | 箇所 |
|---|---|---|---|
| **C-7** | card 作成/更新時に `deck_id` の存在・所有確認なし → 存在しない deck への dangling reference、集計/Tutor 対象から外れる（Low-Medium） | Codex | `card_service.py:102-132,277-285` / `cards_handler.py:87-94,149-169` |
| **C-5** | URL 重複警告が `list_cards` 既定 50 件しか見ない（全件ページネーション版は存在するが未使用） | Codex | `ai_handler.py:130-145` / `card_service.py:537-580` |
| **#10** | `related_cards` が DynamoDB 永続化時に常に `[]`。API 応答直後は返るが履歴復元で消失 | README（Codex は Low 調整） | `tutor_session_manager.py:181-205` |
| **#14** | CORS `AllowCredentials: true`。AllowOrigins は明示リストなので技術的には許容だが、Bearer 運用で Cookie 不使用なら削除可 | README | `template.yaml:349` |
| **#15** | `sm.close()` を `try/finally` で呼ぶため例外が元例外を隠す懸念。現状 `DynamoDBSessionManager.close` は no-op だが AgentCore backend では `with sm:` 化推奨 | README | `tutor_service.py:197-198,316-317` |
| **#16** | フロント定数二重管理（`TIMEOUT_MS`/`MESSAGE_LIMIT`、UI の「20」表示） | README | `TutorContext.tsx:38,41` / `TutorPage.tsx:314` |
| 追加 | `detect_url_in_message` は http(s) 両方抽出するが `validate_url` は https 限定 → http URL は「無効」エラー（UX） | Claude | `line_handler.py:49` vs `url_validator.py:119` |
| 追加 | `_auto_end_active_sessions` がセッション開始毎に各 active を `end_session`→`_get_session_messages`（SessionManager 読み）。messages 不要なのにコスト消費 | Claude | `tutor_service.py:657-668` |
| 追加 | Bedrock IAM の foundation-model ARN が haiku 固定。`BedrockModelId`/`TutorModelId` 変更時に権限不整合 | Claude | `template.yaml:400 ほか` |
| Front | A-1 ログアウト時のメモリ内トークン即時クリアなし／A-2 リフレッシュ起点が 3 経路／E-1 生エラー露出／Q-3 型重複 ほか | Front agent | （フロントレビュー参照） |
| CDK | L-1 CSP `unsafe-inline`／L-2 イメージタグ mutable／L-3 dev アクセスログ無し | CDK agent | （CDK レビュー参照） |

---

## README フォローアップ項目の再検証ステータス

| # | 前回 | 今回の確認 |
|---|---|---|
| #1 Tutor messages文字列対応＋SessionManager拒否 | ✅ Done | コードは Done。**ただし N-1 の前提注意**（USE_STRANDS=true 必須） |
| #2 AgentCore `_ensure_agentcore_imports` | ✅ Done | `tutor_session_factory.py:107` で確認 |
| #3 Browser profile IDOR | ✅ Done | `browser_profile_service.py` 全メソッド user_id をキーに含む。`ai_handler.py:150-173` でも所有検証。確認 |
| #4 requirements 統一 | ✅ Done | `backend/requirements.txt` は `-r src/requirements.txt` のみ |
| #5 LINE Secret | ✅ Done | `LINE_CHANNEL_SECRET_ARN` 経由で実行時取得、CFN に平文なし |
| #6 IAM 最小権限化 | ✅ Done | `template.yaml:826-835` 正しい API 名/ARN。ただし C-2 のため現状デッド |
| #7 Tutor 楽観ロック | ✅ Done | in-flight lock 確認。**ただし同種の保護が `submit_review`（C-1）に無い** |
| #8 stage prefix | ⬜ TODO（削除候補） | **🔁 方針転換: 削除非推奨**（上記） |
| #9 SSRF 強化 | ⬜ TODO | 残（TOCTOU）。リダイレクト再検証は実装済みと確認 |
| #10 related_cards 永続化 | ⬜ TODO | 残（Low へ） |
| #11 Deck 集計 | ⬜ TODO | 残 |
| #12 DuePush race | ⬜ TODO | 残（N-8: 順序問題が核心） |
| #13 Webhook Bedrock 濫用 | ⬜ TODO | 署名検証は堅牢。N-5/N-6/C-4 を追加 |
| #14 CORS | ⬜ TODO | 残（Low） |
| #15 sm.close | ⬜ TODO | 残（Low） |
| #16 フロント定数 | ⬜ TODO | 残（Low） |
| PR #33 browser_service | ⏳ オープン | **C-2: 未マージのため URL 生成エンドポイントが常時 500。要判断（マージ or 本実装）** |

---

## 推奨アクション（順序）

1. **N-1 / C-2（確認済み・上記「運用前提」参照）**: 本番は `USE_STRANDS=true` 想定のため N-1 は設定で回避されるが、既定 false の罠を是正（既定 true 化 or 起動時バリデーション）。デプロイ環境未整備のため C-2 は実機未確認だが、デプロイ即 500 が確実なので、URL カード生成を公開する前に PR #33 の判断（無効化マージ or 本実装）を必須とする。
2. **Webhook 健全化（N-5/N-6/C-4）**: 受信即 200＋重い処理を非同期化（SQS/別 Lambda）、`webhookEventId` で冪等化、chunk 数/Bedrock 呼び出しに上限。
3. **データ整合性（C-1/C-6/N-8）**: `submit_review` に ConditionExpression、`link_line` に line_user_id ロック（TransactWriteItems 等）、通知は「update 成功 → push」順へ。
4. **CDK High（H-1/H-2）**: dev Keycloak の到達範囲制限、prod プレースホルダの外部注入化＋placeholder 検出ガード。
5. **フロント認証基盤（S-1/S-2/A-3）**: トークン保存場所の見直し、silent renew 整合、トークン状態同期。
6. **#8 は「削除」タスクを「コメント補強＋実環境ログ確認」に置換**。
7. 残りは #9 → #11 → C-3/C-7 → Low の順。各 PR で本合同レビュー方式を継続。

---

## 付録: 意見交換のサマリ

- **Claude → Codex**: N-1〜N-8 と README 残課題を提示し独立検証を依頼。
- **Codex の判断**: N-1/N-5/N-6/N-7/#9/#10/#11/PR#33 に同意（うち PR#33 は「`BrowserService()` 無条件生成で URL 生成全体が 500」と深掘り＝C-2）。**#8 のみ反論**（補正は Powertools への必要な適応）。新規に C-1（submit_review lost update）、C-3（postback URL）、C-4（chunk 比例 Bedrock）、C-5（重複先頭50件）を提示。
- **Claude の再検証**: #8 について Powertools 実装（`APIGatewayProxyEventV2.path` の無条件 strip）を確認し、**Codex が正しく自説を撤回**。Codex の新規発見 4 件＋C-2 を実コードで確認し全て妥当と判断。
- **追加合意**: Codex が最終ターンで C-6（link_line race）、C-7（card deck_id 整合性）を追加。Claude が `user_service.py`/`card_service.py` で確認し採用。重大度（特に C-1 を Medium-High）を相互合意。

> 本レビューはコードを変更していない（read-only）。一次情報は GitHub PR・commit log・本ファイル。
