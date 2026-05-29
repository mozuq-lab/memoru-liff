# コードレビュー指摘事項フォローアップ

**起点レビュー日**: 2026-03-08（バックエンド/フロントエンド 30 件 × 2）
**追加レビュー日**: 2026-05-09 〜（Claude Opus 4.7 × Codex MCP の合同）
**最終更新**: 2026-05-29

このドキュメントは Claude × Codex の合同コードレビュー（16 項目）の対応進捗と残課題を、別セッションでも継続できる形で記録したものです。

---

## レビューの背景

`main` ブランチに対して以下の手順でレビューを実施しました：

1. Claude (Opus 4.7) で実コードを読みながら問題を抽出
2. Codex MCP (`mcp__codex__codex`、GPT 系) で独立レビュー
3. 双方の指摘を突き合わせて優先度を合意
4. Critical/High から順に PR 化

レビュー詳細の生ログ／合意プロセスはこの README には残していません（GitHub PR コメントと commit log が一次情報）。

---

## 全 16 項目の対応状況

| # | 優先度 | 内容 | 状態 | 関連 PR |
|---|---|---|---|---|
| 1 | 🔴 Critical | `BedrockTutorAIService` の `messages` 文字列対応 + SessionManager 拒否 | ✅ Done | [#30](https://github.com/mozuq-lab/memoru-liff/pull/30) |
| 2 | 🔴 Critical | AgentCore backend で `_ensure_agentcore_imports()` を呼ぶ | ✅ Done | [#30](https://github.com/mozuq-lab/memoru-liff/pull/30) |
| 3 | 🔴 Critical | Browser profile の所有者検証（IDOR 防止） | ✅ Done\* | [#30](https://github.com/mozuq-lab/memoru-liff/pull/30) |
| 4 | 🔴 Critical | `requirements.txt` の分裂解消 | ✅ Done | [#30](https://github.com/mozuq-lab/memoru-liff/pull/30) |
| 5 | 🔴 Critical | LINE Channel Secret を Secrets Manager dynamic reference に | ✅ Done | [#30](https://github.com/mozuq-lab/memoru-liff/pull/30) |
| 6 | 🟠 High | `UrlGenerateFunction` の IAM 最小権限化 | ✅ Done\*\* | [#32](https://github.com/mozuq-lab/memoru-liff/pull/32) |
| 7 | 🟠 High | Tutor `send_message` の楽観ロック（in-flight lock） | ✅ Done | [#32](https://github.com/mozuq-lab/memoru-liff/pull/32) |
| 8 | 🟠 High | Stage prefix 補正の調査・削除 | ⬜ TODO | — |
| 9 | 🟡 Medium | URL SSRF 対策強化（DNS rebinding / Browser 経路） | ⬜ TODO | — |
| 10 | 🟡 Medium | `related_cards` メタデータの SessionManager 永続化 | ⬜ TODO | — |
| 11 | 🟡 Medium | Deck 集計が user 全カード Query になっている | ⬜ TODO | — |
| 12 | 🟡 Medium | `DuePushJob` の concurrency と schedule のレース | ⬜ TODO | — |
| 13 | 🟡 Medium | `LineWebhookFunction` の Bedrock 濫用対策 | ⬜ TODO | — |
| 14 | 🟢 Low | CORS `AllowCredentials: true` の必要性 | ⬜ TODO | — |
| 15 | 🟢 Low | `sm.close()` の例外抑制とリソース管理 | ⬜ TODO | — |
| 16 | 🟢 Low | フロント側ハードコード値（`TIMEOUT_MS` / `MESSAGE_LIMIT`）の二重管理 | ⬜ TODO | — |
| + | 🟠 High | `browser_service.py` の本実装（PR #33 のフォローアップ） | ⏳ PR #33 オープン中 → 本実装は別 PR | [#33](https://github.com/mozuq-lab/memoru-liff/pull/33) |

> \* `BrowserProfileService.validate_profile()` 呼び出しは PR #30 でマージ済みで、現状の main にも残っている。ただし `BrowserService` 自体が壊れているため、profile_id 経路は実質動作しない（後述 PR #33 で「無効化」を提案中）。
>
> \*\* IAM のアクション名・ARN は最終的に正しい形（`Start/Get/Stop BrowserSession`, `InvokeBrowser` 等 + `browser/*` および `browser-profile/*` ARN）に修正してマージ済み。PR #33 が採用された場合は無効化に伴い IAM も削除される。

---

## マージ済み PR の要点

### PR #30 — Critical 5 件（マージ済み）
- **#1, #2**: Tutor の本番起動の死活問題（USE_STRANDS=false で壊れる、AgentCore で TypeError）
- **#3**: Browser profile の IDOR 防止（main に残存。PR #33 が採用されれば撤去予定）
- **#4**: `backend/src/requirements.txt` を本番依存の正本に統一（`backend/requirements.txt` は `-r src/requirements.txt` のみに）
- **#5**: LINE Channel Secret を CFN dynamic reference 化

### PR #32 — High 2 件（マージ済み）
- **#6**: IAM 最小権限化。Codex フィードバックを受けて 3 度書き直し（`Create/Close BrowserSession` 誤り → 実 API 名 → `browser-profile` ARN 追加）
- **#7**: 楽観ロック。当初の `message_count` race ベースでは「先行が count 進めた後の到着」を弾けなかったため、`processing_started_at` 属性ベースの **in-flight lock** に書き直し。stale lock 自動引き継ぎ（`LOCK_TIMEOUT_SECONDS`）あり

### PR #33 — browser_service 無効化（オープン中・未マージ）
- 既存の `BrowserService` が存在しない boto3 サービス名・メソッド名を参照していたため、安全側に倒して「常に 501 Not Implemented」に
- 関連 IAM・環境変数も template.yaml から削除
- **マージ判断はユーザー保留中**
- main は現状「壊れた `BrowserService` が残ったまま」「`profile_id` 指定で 500 になる」状態。マージするまでは SPA / 認証付きページ取得経路は実質的に動かない

---

## 🔥 最優先の残課題（次セッションで着手すべき）

### A. PR #33 の取り扱い決定
- **状態**: オープン中（未マージ）
- **判断材料**: SPA / 認証付きページからのカード生成機能を当面使うか？
  - 使わない → PR #33 をマージし、無効化を確定（壊れた現状から「明示 501」に格上げ）
  - 使う → PR #33 をクローズし、代わりに browser_service.py の本実装 PR を作る
- **放置のリスク**: main の `BrowserService` は `boto3.client("bedrock-agentcore-browser")` という存在しないサービス名で `UnknownServiceError` を起こすため、`profile_id` 付きリクエストや SPA fallback が **意図しない 500** を返し続ける
- **本実装のスコープ**（必要になった場合）:
  - `bedrock-agentcore` クライアント（サービス名修正）
  - `start_browser_session` / `invoke_browser` / `stop_browser_session` への置換
  - `StartBrowserSession` の `browserIdentifier` は AWS 管理 Browser ID（要調査）
  - HTML 取得は Live View Stream / CDP 経由（API 直接ではなく）
  - 関連テスト復活、IAM・環境変数復活
  - `BrowserProfileService.validate_profile()` IDOR チェックは既に main に残っているため復活不要（PR #33 をマージしていない限り）

### B. High #8 — Stage prefix 補正の調査・削除
- **箇所**: `backend/src/api/handler.py:233-236`（PR #32 マージ後の行番号が変わっている可能性あり、要確認）
- **疑い**: `stage != "$default"` のとき `rawPath` に `/${stage}` を付与しているが、`APIGatewayHttpResolver` の標準動作と矛盾し 404 を引き起こす可能性
- **次の手順**:
  1. CloudWatch Logs で実イベントの `rawPath` / `requestContext.http.path` / `requestContext.stage` を観察
  2. stage が含まれているかどうかで判断
  3. 削除 or `APIGatewayHttpResolver(strip_prefixes=[f"/{stage}"])` に置き換え
- **見積もり**: 調査込みで 1〜2 時間
- **リスク**: ルーティング全体への影響があるため単独 PR 推奨

---

## 🟡 Medium 残課題

### #9 SSRF 対策の DNS rebinding / Browser 経路強化
- **箇所**: `backend/src/utils/url_validator.py:82`、`browser_service.py:66`
- **現状**: 事前 DNS 解決でプライベート IP を拒否しているが、HTTP/Browser の実接続 IP を固定していない
- **対応案**: outbound proxy / egress allowlist、または HTTP レベルで validated IP 強制接続（curl `--resolve` 相当）
- **見積もり**: 半日〜1日

### #10 `related_cards` メタデータの SessionManager 永続化
- **箇所**: `backend/src/services/tutor_session_manager.py:200-205`
- **現状**: `_strands_to_dynamo_message` が常に `"related_cards": []` で書き込み
- **対応案**: AI 応答後に最後の assistant メッセージへ別 update で append、または UI メタデータを別テーブルに分離
- **見積もり**: 半日

### #11 Deck 集計が user 全カード Query
- **箇所**: `backend/src/services/tutor_service.py:621,624`、`deck_service.py:359,405`（行番号は変動）
- **問題**: `deck_id` 指定でも `user_id` 単独で Query して Filter
- **対応案**: `user_id + deck_id` の GSI、または DynamoDB Streams で deck カウンタ集計
- **見積もり**: 1日（スキーマ変更＋移行を慎重に。PITR 有効）

### #12 `DuePushJob` の concurrency と schedule のレース
- **箇所**: `backend/template.yaml` の `DuePushJobFunction`（schedule: `rate(5 minutes)`, Timeout 300s, ReservedConcurrency 5）
- **対応案**: まず既存 `last_notified_date` ロジックを監査。必要なら ConditionExpression 付き update、または SQS バッチ化
- **見積もり**: 監査込みで半日

### #13 LINE Webhook の Bedrock 濫用対策
- **箇所**: `backend/template.yaml` の `LineWebhookFunction`
- **対応案**: `ReservedConcurrentExecutions` 検討、Bedrock 呼び出し回数のメトリクス＋アラーム、Quota 見直し
- **見積もり**: 1 時間

---

## 🟢 Low 残課題

### #14 CORS `AllowCredentials: true` の必要性確認
- **箇所**: `backend/template.yaml` HttpApi の CorsConfiguration
- **判定**: `Authorization` ヘッダ運用で Cookie を使っていないなら不要（フロントエンドが Cookie を読まないことを確認すれば即削除可）

### #15 `sm.close()` の例外抑制
- **箇所**: `backend/src/services/tutor_service.py` の `start_session` / `send_message`
- **対応**: `try/finally` で `sm.close()` が失敗すると元例外を隠す可能性。`with sm:` パターンに変更

### #16 フロント定数二重管理
- **箇所**: `frontend/src/contexts/TutorContext.tsx:38-41`
- **対応**: API レスポンスから上限値を取得、または `/config` エンドポイントを追加

---

## 引き継ぎ：ローカル環境セットアップ

別セッションで作業する場合の初期化手順：

```bash
# Python 3.12 を uv で導入（プロジェクトは 3.12 固定、3.13 化しない）
uv python install 3.12
cd backend
echo "3.12" > .python-version   # 既に存在するならスキップ

# venv 作成 + 依存導入
uv venv
uv pip install -r requirements.txt -r requirements-dev.txt

# テスト実行（基準: 全 1418 件 PASS、約 65 秒）
source .venv/bin/activate
pytest tests/ -q

# CDK テスト
cd ../infrastructure/cdk
npm test   # 77 件 PASS

# Frontend type-check
cd ../../frontend
npm run type-check
```

---

## 引き継ぎ：レビュー手法

別セッションで同じレビュー方式を再開する場合：

1. Codex MCP を使う場合、`mcp__codex__codex` が利用可能か確認
2. プロンプトテンプレート（参考、これは README には実コピーしない）：
   - 「リポジトリ全体を 8 観点（セキュリティ／アーキ／パフォ／保守性／テスト／エラー／AgentCore Memory／CDK）でレビュー」
   - 「優先度（高/中/低）と該当ファイル/行を含めて返す」
3. Claude 側で実コードを読んで Codex の指摘を検証する流れが質を上げた

過去の合同レビューで発見できた問題例：
- 私（Claude）単独で見落とし→ Codex に拾われたもの：楽観ロックの「count 進んだ後」シナリオ、IAM のアクション名誤り
- Codex 単独で見落とし→ Claude が拾ったもの：browser_service.py 全体が動かない問題、追加観点 A〜F

---

## 引き継ぎ：判断基準・注意点

### Codex フィードバックの受け方
- IAM や AWS API の指摘は botocore のサービスモデル（`backend/.venv/lib/python3.12/site-packages/botocore/data/`）で検証してから信用する
- 過去に「正しいと思って書いた IAM アクション名」が 3 回連続で誤っていた事例あり

### 楽観ロックの設計（PR #32 の教訓）
- `message_count = :prev` だけの楽観ロックは「先行が count を進めた後に到着した 2 件目」を防げない
- `processing_started_at` 属性の存在 + stale 検出が現状の確定形

### IAM の最小権限化
- アクション名は実 API オペレーション名と一致（boto3 メソッドの snake_case から PascalCase に変換）
- ARN のアカウント部分：AWS 管理リソースは `aws` 固定、ユーザーリソースは `${AccountId}`
- 例：`arn:${Partition}:bedrock-agentcore:${Region}:aws:browser/*` ← AWS 管理 Browser
- 例：`arn:${Partition}:bedrock-agentcore:${Region}:${AccountId}:browser-profile/*` ← ユーザー作成 Profile

### Python ランタイム
- Lambda Runtime は 3.12 固定。ローカルも 3.12 で揃える（3.13 は AgentCore SDK 互換性が未検証）
- 3.13 にアップグレードしたい場合は別 PR で `template.yaml` と一緒に切り替える

---

## 引き継ぎ：参考リンク

- レビュー対象リポジトリ: `mozuq-lab/memoru-liff`
- 過去 PR：
  - [#28](https://github.com/mozuq-lab/memoru-liff/pull/28) バックエンド 30 件
  - [#29](https://github.com/mozuq-lab/memoru-liff/pull/29) フロントエンド 30 件
  - [#30](https://github.com/mozuq-lab/memoru-liff/pull/30) Critical 5 件
  - [#32](https://github.com/mozuq-lab/memoru-liff/pull/32) High 2 件
  - [#33](https://github.com/mozuq-lab/memoru-liff/pull/33) browser_service 無効化（オープン）
- 関連ドキュメント：
  - `docs/ideas/archive/agent-team-brainstorm-2026-03-08.md`（機能アイデア、レビュー対象外）
  - `CLAUDE.md` / `AGENTS.md`（プロジェクト固有ルール）

---

## 推奨：次セッションの開始手順

1. このファイルを読む
2. `gh pr view 33` で PR #33 の状態確認
3. ユーザーに「PR #33 をマージするか、browser_service を本実装するか」を確認
4. 上記決定後、A→B→Medium の順で残課題を消化
5. 各 PR ごとに Codex 合同レビューを通す
