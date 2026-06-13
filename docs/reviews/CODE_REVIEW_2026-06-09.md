# 全体コードレビュー（2026-06-09）

**レビュー日**: 2026-06-09
**レビュアー**: Claude Code（バックエンド / フロントエンド / インフラの 3 並列レビュー + 統合検証）
**対象**: `main` 相当（`77a32f5` 時点）全体 — backend / frontend / infrastructure / CI
**前提**: [joint-review-2026-05-29.md](../tasks/code-review-followup-2026-03-08/joint-review-2026-05-29.md) の既知指摘は重複報告せず、状態確認のみ実施

---

## エグゼクティブサマリ

- **直近の修正 4 コミット（N-1 / N-6 / C-1 / N-7 対応）はいずれも妥当で、退行なし。**
- 新規の最重要発見は **B-1**: `line_service` の `except httpx.RequestError` が `raise_for_status()` の送出する `httpx.HTTPStatusError` を捕捉できず（サブクラス関係にない・実機検証済み）、`LineApiError` 変換が HTTP 4xx/5xx で効かない。これにより**ブロック済みユーザーへの push を終日リトライ**し続け、Webhook では reply 失敗が再配信→二重処理を誘発し、**せっかく入れた N-6/C-1 の保護を一部迂回し得る**。
- インフラ面では **prod の samconfig が必須パラメータをほぼ上書きしておらず**（I-1/I-2）、現状の設定のままデプロイすると LINE 連携・OIDC issuer 検証・Tutor が prod で機能しない。
- 既知の未対応指摘（CDK H-1/H-2、フロント S-1/S-2/A-3 等）は**すべて未対応のまま残存**。

---

## 1. 直近修正コミットの検証結果

| コミット | 対応 | 判定 |
|---|---|---|
| `88b57ec` | N-1: USE_STRANDS=false 時の Tutor 503 化 | ✅ 問題なし。AI を呼ぶのは `create_session`/`send_message` のみで、両方とも `TutorAIServiceError` を `TutorServiceError` より前に捕捉し 503 を返す。網羅性・except 順序ともに正しい |
| `f3dfb2a` | N-6: Webhook 冪等ガード | ✅ 概ね問題なし。二段階（in_progress/processed）+ stale 180s + 失敗時 release の設計は妥当。⚠️ コメントの「Lambda Timeout 120s」前提に対し `LineWebhookFunction` に明示 `Timeout` がない点は要確認。また `handle_postback`/`handle_grade_action` が内部で例外を握り潰すため release はほぼ発火しない（B-1 と関連、下記 B-4） |
| `ed266bc` | C-1: submit_review 楽観ロック | ✅ 問題なし。CAS の条件式・`attribute_not_exists` フォールバック・409 マッピング・更新順序（card 更新 → review 記録で孤立レコード防止）すべて正しい。※ `ease_factor` の `str(float)` 往復比較は現行書式（`str(round(x,2))`）では安定。過去データに別書式があると誤 409 の可能性のみ留意 |
| `77a32f5` | N-7: URL fetch サイズ上限 | ✅ 問題なし。Content-Length 事前チェック + `iter_bytes()` 逐次累積の 10MB ハードキャップで、chunked / Content-Length 詐称にも対応。リダイレクトの SSRF 再検証も維持 |

---

## 2. 新規指摘 — バックエンド

### 🔴 High

#### B-1: `reply_message`/`push_message` が LINE API の HTTP 4xx/5xx を `LineApiError` に変換しない

- **場所**: `backend/src/services/line_service.py:283-288`（reply）, `:320-325`（push）
- **根拠**: `response.raise_for_status()` は `httpx.HTTPStatusError` を送出するが、これは `httpx.RequestError` のサブクラスではない（両者は `HTTPError` 直下の兄弟。`issubclass(HTTPStatusError, RequestError) == False` を実機検証済み）。`except httpx.RequestError` は接続/タイムアウト系のみ捕捉し、HTTP ステータスエラーは生のまま呼び出し元へ漏れる。
- **影響**:
  1. `notification_service.process_notifications` の `except LineApiError`（`notification_service.py:174`）が**ブロック済みユーザーの 403 を捕捉できず**、汎用 `except Exception` に落ちて `update_last_notified_date` がスキップされ、**5 分間隔で終日リトライ**し続ける。
  2. Webhook の reply 失敗（期限切れ reply token = 400 等）が `handle_postback` の `except LineApiError` を素通りし、handler の `except Exception` → 冪等キー release → **LINE 再配信 → 二重処理**を誘発しうる。
- **修正案**:

```python
except httpx.HTTPError as e:   # RequestError と HTTPStatusError の共通親
    raise LineApiError(f"Failed to send reply: {e}") from e
```

### 🟠 Medium

#### B-2: `undo_review` に楽観ロックがなく lost update / 履歴破損が残る

- **場所**: `backend/src/services/review_service.py:254-276`
- C-1 は `submit_review` のみ CAS 化したが、`undo_review` は `review_history` 全体を read→truncate→write し、SRS フィールドも `ConditionExpression` なしで上書き。undo と submit の並行、undo の二重実行で履歴と SRS 状態が不整合になりうる。
- **修正案**: undo も CAS 化（`updated_at` 比較等）し、競合時は `ConcurrentReviewError` → 409。

### 🟢 Low

#### B-3: `limit` の下限未検証で DynamoDB `Limit<=0` が 500 化

- **場所**: `backend/src/api/handlers/cards_handler.py:37` / `review_handler.py:39`
- `min(int(limit), 100)` は上限のみで、`?limit=0` / 負数が DynamoDB ValidationException → 未捕捉 500。修正: `max(1, min(..., 100))`。

#### B-4: Webhook の release 経路が実質デッドで、挙動が経路依存に非一貫

- **場所**: `backend/src/webhook/line_handler.py:158-184, 461-502, 574-584`
- `handle_grade_action`/`handle_postback` が内部で例外を握り潰すため、handler レベルの「失敗時 release」はほぼ発火しない。B-1 の生 `HTTPStatusError` が漏れた場合**のみ** release される非一貫な状態。B-1 修正で「reply 失敗は processed 扱い」に統一されるのが望ましい。

---

## 3. 新規指摘 — フロントエンド

### 🔴 High

#### F-1: `useAuth()` の Context 外直接呼び出しで認証状態が二重管理

- **場所**: `frontend/src/pages/ReviewPage.tsx:60` / `SettingsPage.tsx:42`
- 両ページが `useAuthContext()` ではなく `useAuth()` を直接呼んでおり、ページごとに独立した認証 state マシン（独自 `initAuth` effect）が生成される。マウント毎の余分な `getUser()`、`SettingsPage` の `logout()` が `AuthContext` 側の `apiClient.setAccessToken(null)` 同期をトリガーしない等、A-3（既知）と同根の不整合。
- **修正案**: 両ページを `useAuthContext()` に統一し認証状態をシングルソース化。

### 🟠 Medium

#### F-2: TutorPage の「再試行」ボタンがエラーを消すだけ

- **場所**: `frontend/src/pages/TutorPage.tsx:181` — `<Error message={error} onRetry={clearError} />`。`clearError` は `startSession` を再実行しない。直前モードを保持して再実行するか、文言を「閉じる」に変更。

#### F-3: CardsContext の AbortController が fetch を実際にはキャンセルしない

- **場所**: `frontend/src/contexts/CardsContext.tsx:55-101`
- `options.signal` を `cardsApi.getCards()` に渡しておらず、await 後に `aborted` を見るだけ。呼び出し側（`CardsPage.tsx:85-91`）は signal 自体を渡していないため、タブ/デッキ連続切替時に古いレスポンスが新しい結果を上書きしうる。**修正案**: signal を fetch まで伝播、または最新リクエスト ID で古い結果を破棄。

#### F-4: GeneratePage の保存ループが途中失敗で部分保存 + 再試行重複

- **場所**: `frontend/src/pages/GeneratePage.tsx:219-231`
- 逐次 `createCard` の途中失敗時、保存済み分が選択集合に残ったまま再試行で二重登録。成功 tempId を選択集合から除去するか「N 枚中 M 枚保存済み」を提示。

#### F-5: RelatedCardChip の N+1 フェッチ（キャッシュなし）

- **場所**: `frontend/src/components/tutor/RelatedCardChip.tsx:13-31`
- チップごとに `getCard(cardId)` を個別実行し、履歴が伸びるほど API コール線形増加。Map でのメモ化かバッチ取得を推奨。

### 🟢 Low

- **F-6**: CallbackPage が StrictMode の effect 二重実行で「No matching state」偽エラーになりうる（開発環境限定・要確認）。処理済み ref ガード推奨 — `CallbackPage.tsx:10-22`
- **F-7**: useSpeech のアンマウント cleanup が `speechSynthesis.cancel()` を無条件実行（グローバル停止）— `useSpeech.ts:59-65`
- **F-8**: CardsContext の loading/error をページ横断で共有しており、他ページの失敗が HomePage 再訪時に無関係なエラー画面を出しうる — `HomePage.tsx:33,45`
- **F-9**: CardList に仮想化なし（数千枚規模で再レンダリングコスト）— `CardList.tsx:22-34`

---

## 4. 新規指摘 — インフラ / CI

### 🔴 High

#### I-1: prod samconfig が必須パラメータをほぼ上書きしておらず、LINE 連携・OIDC 検証が prod で機能しない

- **場所**: `backend/samconfig.toml:43`（prod セクション）
- prod の `parameter_overrides` は `Environment` と `OidcIssuer` のみ。`LineChannelId`（既定 `""`）未設定だと `line_service.py:225` で ID トークン検証が常に失敗し `/users/link-line` 等が機能しない。さらに `OidcIssuer` の値自体が `keycloak.your-domain.com`（プレースホルダ）のままで JWT オーソライザの issuer 検証が実環境と不一致。
- **修正案**: prod に `OidcAudience` / `LineChannelId` / `BedrockModelId` / 実 `OidcIssuer` を明示（CI からは GitHub Environment variables で注入）。

#### I-2: prod で Tutor が既定で 503 のまま（UseStrands 未上書き）

- **場所**: `backend/samconfig.toml:43` / `template.yaml:70-89`
- prod samconfig が `UseStrands` を上書きしないため既定 `false` → Tutor 全エンドポイントが 503。N-1 の 503 化で「原因不明の 500」は解消されたが、**prod で Tutor を稼働させる構成自体が存在しない**。`UseStrands=true`（AgentCore 利用なら `TutorSessionBackend`/`AgentCoreMemoryId` も）を追加するか、提供しない意図を明記。

### 🟠 Medium

- **I-3**: 全 Lambda に DLQ / OnFailure がなく、Schedule 起動の `DuePushJobFunction`（`template.yaml:702`）の失敗イベントが消失 → 復習リマインダ欠落を検知不能。SQS/SNS DLQ + Alarm を推奨。
- **I-5**: CI（`.github/workflows/ci.yml:32-34`）が backend は pytest のみで `make lint`（ruff+mypy）を未実行。静的解析の退行が PR でブロックされない（既知 N-9 の mypy 設定不備とも関連）。
- **I-6**: `deploy.yml` の `paths` が `backend/**`/`frontend/**` のみで、`infrastructure/**` 変更時に CDK の synth/test が CI で一切検証されない。PR CI に `npm test` + `cdk synth` 追加を推奨。

### 🟢 Low

- **I-4**: DuePushJob の IAM が UsersTable へ Read ポリシー + `UpdateItem` 別建て付与で整理余地（実害低・要確認）— `template.yaml:712-721`
- **I-7**: Reviews テーブルは TTL（`expires_at`）有効化済みだが、`review_service.py:418-428` の put_item が `expires_at` を書かず TTL が実質無効。保持方針を確定し template とコードを一致させる。
- **I-8**: `browser_profile_service.py:39` の既定テーブル名 `memoru-browser-profiles` が実テーブル名 `memoru-browser-profiles-${Environment}` と不一致（env 注入で回避中・要確認）
- **I-9**: dev S3 LIFF バケットの CORS が `allowedOrigins: ['*']`（CloudFront 経由前提なら不要）— `liff-hosting-stack.ts:58-60`
- **I-10**: リフレッシュトークン 30 日 + セルフサインアップ + MFA OPTIONAL の合算リスク（既知 M-3 の補足）— `cognito-stack.ts:155-157`
- **I-11**: docker-compose の Keycloak `admin/admin` 固定・Ollama `0.0.0.0` バインド（ローカル限定）— `docker-compose.yaml:121-122,145`

---

## 5. 既知指摘の現状（2026-05-29 比）

| 指摘 | 現状 |
|---|---|
| N-1（Tutor 500） | ✅ **503 化で対応済み**（88b57ec）。ただし I-2 のとおり prod で Tutor を有効化する構成は未整備 |
| N-6（Webhook 冪等） | ✅ **対応済み**（f3dfb2a） |
| C-1（submit_review lost update） | ✅ **対応済み**（ed266bc）。ただし同種の穴が `undo_review` に残存（B-2） |
| N-7（URL fetch サイズ上限） | ✅ **対応済み**（77a32f5） |
| N-8 / C-6 / C-7 | ✅ **2026-06-10 対応済み**。N-8: 通知を claim → push 順に変更。C-6: link_line/unlink_line を TransactWriteItems + ロックアイテム（`LINELINK#<line_user_id>`）で排他。C-7: card の deck_id 存在・所有検証を追加（不正時 400 invalid_deck） |
| C-2 | ✅ **解消済みと確認** (PR #33 が 2026-05-29 にマージ済み)。BrowserService はスタブ化され profile_id は早期 501、静的 HTML 経路は正常動作。本実装はデプロイ環境整備後に判断（A案採用）。2026-06-11 にフロントのプロファイル UI を「準備中」表示化 |
| C-3 / C-4 / C-5 | ✅ **2026-06-11 対応済み**。C-3: postback を reference key 方式化（保存時の再生成も廃止）。C-4: Bedrock 呼び出しに MAX_CHUNK_CALLS=8 + 早期 break。C-5: 重複警告を全カード走査に変更（contains FilterExpression が常に空を返す潜在バグも修正） |
| N-5 | ✅ **2026-06-12 対応済み**。URL カード生成を SQS ワーカーへ非同期化（受付は進捗 reply + enqueue で即 200）。インラインフォールバック付き（ローカル/enqueue 失敗時）。MaximumConcurrency=2 で Bedrock 同時実行も制御 |
| #9 / #11 | ✅ **2026-06-12 対応済み**。#9: DNS を 1 回解決して全 IP 検査 + 検証済み IP への接続固定（Host + SNI で TLS 検証は元ホスト名）により rebinding の TOCTOU 窓を閉鎖。#11: CardsTable に deck_id-due-index GSI を追加し Deck 集計を Select=COUNT クエリ化（N-9 は #41 で解消済み） |
| CDK H-1 / H-2 / M-1〜M-4 / L-1〜L-3 | 🔶 **一部対応（2026-06-13）**。H-2: prod 値を `resolveProdConfig`（プレースホルダ + 証明書リージョン検証）+ `stage` フィルタで外部注入化し解消済み。M-1: CloudFront に `minimumProtocolVersion=TLSv1.2_2021` を明示（PR #60）。H-1: dev Keycloak ALB の受信元を `MEMORU_DEV_KEYCLOAK_ALLOWED_CIDR` で制限可能化（既定は従来どおり全公開、PR #60）。**残（要判断）**: H-1 完全版/M-2（dev HTTPS 化・NAT 追加＝コスト/環境決定）、M-3（Cognito self-signup 無効化・MFA 必須＝プロダクト方針）、M-4（prod Keycloak HA＝NAT コスト増）、L-1（CSP `unsafe-inline` 削減＝アプリ破損リスク・要実機確認）、L-2/L-3（image digest 固定・dev アクセスログ＝軽微） |
| フロント S-1 / S-2 / A-1〜A-3 | ✅ **2026-06-10 対応済み**（下記「対応状況」参照）。⚠️ **S-1 は指摘自体を訂正**: oidc-client-ts の `userStore` 既定値は localStorage ではなく **sessionStorage**（旧 `oidc-client` との混同による誤指摘）。トークンは元々タブ単位の sessionStorage 保存だった。対応としては既定依存をやめ `userStore` を明示設定 |
| フロント E-3 / Q-3 / #16 | ⬜ 未対応（E-1 のみ部分対応: `GeneratePage.tsx:175` と `TutorContext.tsx:119,167` に生メッセージ露出が残存） |

---

## 6. 推奨アクション（優先順）

1. **B-1**（`httpx.HTTPError` への except 拡大）— 1 行級の修正で通知リトライストーム・Webhook 再配信二重処理を同時に解消。N-6/C-1 の保護を完全に活かすための前提。
2. **I-1 / I-2**（prod samconfig の必須パラメータ整備）— デプロイ前必須。既知 CDK H-2（プレースホルダ）と合わせて prod 構成を一括で外部注入化。
3. **F-1**（`useAuthContext` への統一）— 既知 A-3/S-2 の認証フロー是正と同一 PR で対応するのが効率的。
4. **B-2**（undo_review の CAS 化）— C-1 と同パターンの横展開で低コスト。
5. **I-5 / I-6**（CI に backend lint + CDK synth/test 追加）— 既知 N-9（mypy 設定）とセットで品質ゲートを回復。
6. **I-3**（DuePushJob の DLQ）→ F-2/F-3/F-4 → Low 群の順。

---

## 7. 総評

直近のフォローアップ 4 件はいずれも正しく実装されており、レビュー → 修正のサイクルは機能している。コードベース全体としても、冪等ガード・楽観ロック・SSRF 再検証・ストリーミングサイズ上限・DynamoDB の PITR/KMS など防御的な作り込みは着実に積み上がっている。一方で今回の新規発見は「**例外型の取りこぼし（B-1）が直近の保護機構を迂回する**」「**prod のデプロイ構成が実は未完成（I-1/I-2）**」という、個々のコード品質ではなく**境界（例外階層・環境設定・CI ゲート）の検証漏れ**に集中している。既知の High（CDK H-1/H-2、フロント S-1/S-2）が 2 レビュー連続で未着手な点も含め、次のスプリントは新機能よりフォローアップ消化を優先することを推奨する。

> 本レビューはコードを変更していない（read-only）。

---

## 8. 対応状況（2026-06-09 追記）

レビュー当日に以下を修正済み（各タスク個別コミット、全テスト成功を確認: backend 1455 passed / カバレッジ 84%、frontend 785 passed / type-check 成功）。

| ID | 状態 | 対応内容 |
|---|---|---|
| B-1 | ✅ 修正済み | `except httpx.HTTPError` へ拡大し `LineApiError` 変換を回復 |
| B-2 | ✅ 修正済み | `undo_review` を submit と同パターンで CAS 化、競合時 409 |
| B-3 | ✅ 修正済み | `limit` を [1, 100] にクランプ |
| B-4 | ✅ 実質解消 | B-1 修正により reply 失敗時の挙動が「processed 扱い」に統一 |
| F-1 | ✅ 修正済み | `useAuthContext()` に統一 |
| F-2 | ✅ 修正済み | 直前モードを保持し再試行で `startSession` 再実行 |
| F-3 | ✅ 修正済み | signal を fetch まで伝播 + リクエスト ID で古い結果を破棄 |
| F-4 | ✅ 修正済み | 保存成功分を選択集合から除去、部分保存メッセージ表示 |
| F-5 | ✅ 修正済み | モジュールレベルキャッシュ + in-flight Promise 共有 |
| I-3 | ✅ 修正済み | DuePushJob に SQS DLQ（KMS 暗号化・14日保持）を追加 |
| I-5 | ✅ 修正済み | ruff 違反 112 件（src 16 + tests 96）を解消し、CI に ruff + mypy を有効化。N-9 も同時解消（pyproject.toml に mypy 設定、実型エラー 44 件修正）。副産物として tutor SessionManager 復元の timestamp ValidationError（潜在バグ）を発見・修正 |
| I-6 | ✅ 修正済み | ci.yml に infrastructure-test job（build + test + cdk synth）を追加 |
| I-1 / I-2 | ⬜ 要ユーザー対応 | prod samconfig への実値設定が必要: `LineChannelId`（LINE Developer Console の値）、実ドメインの `OidcIssuer`、`OidcAudience`、Tutor 提供時は `UseStrands=true`（+ AgentCore 利用なら `TutorSessionBackend`/`AgentCoreMemoryId`）。コードでは対応不可のため運用設定で対応 |
| S-1 / S-2 / A-1〜A-3 | ✅ 対応済み (2026-06-10) | 認証基盤セット対応。**S-1 は誤指摘と判明**（oidc-client-ts 既定は sessionStorage）→ `userStore` を明示設定に変更。S-2: `/silent-renew` ルート + `signinSilentCallback` を実装。A-3: `onUserChanged`（userLoaded/userUnloaded/accessTokenExpired）を useAuth が購読しトークン更新・失効を状態へ反映。A-1: logout 失敗時に `removeUser()` でローカルトークンを必ず破棄。A-2: 手動 `addAccessTokenExpiring` リフレッシュを削除し、更新起点を automaticSilentRenew + API 401 リトライの 2 経路に集約 |
| Low 群 (E-3/E-1 残り/Q-3/#16/F-6〜F-8/#10/#14/#15/I-4/I-7〜I-9/I-11/Bedrock IAM 固定) | ✅ **2026-06-12 一括対応済み**。E-3: ApiError 導入で status/code 判定化 + 生メッセージ露出解消。#10: related_cards 永続化。#15: sm.close 例外マスキング防止。#14/I-7: template 整理。Bedrock IAM ARN をパラメータ化。F-9 (仮想化) は実需が出るまで見送り、I-10 は dev ハードニング群 (CDK H-1/M-1〜M-4) と合わせて別途 |
| CDK M-1 / H-1（ノブ） | ✅ **2026-06-13 対応済み (PR #60)**。M-1: CloudFront `minimumProtocolVersion=TLSv1.2_2021` を明示（prod 強制 + 既定ドリフト回帰ガード、dev デフォルトドメインは CloudFront 制約で無視）。H-1: dev Keycloak ALB の受信元を `MEMORU_DEV_KEYCLOAK_ALLOWED_CIDR` で制限可能化（未指定時は従来どおり全公開＝後方互換）。証明書併用時は 80/443 両方を許可（HTTP→HTTPS リダイレクト対応）。回帰テスト追加 |
| 構造リファクタ B4 / F3 | ✅ **2026-06-13 対応済み**。B4: 肥大バックエンドを Repository/Service 分離（card_service #56・tutor_service #57・line_handler #58）。F3: 巨大ページのロジックをフック抽出（ReviewPage→useReviewSession・GeneratePage→useCardGeneration #59）。いずれも公開 API・挙動不変で全テスト緑（本レビュー指摘外の改善） |
