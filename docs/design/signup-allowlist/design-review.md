# signup-allowlist 設計レビュー記録

対象: [architecture.md](./architecture.md) v1.0 → v1.1
実施日: 2026-07-20
体制: 2 系統の独立レビュー
- **系統 A**: アーキテクチャ・リポジトリ整合性視点（template.yaml / Makefile / deploy.yml / CDK 実装・インストール済み aws-cdk-lib ソースとの突合）
- **系統 B**: セキュリティ・Cognito 仕様視点（バイパス経路の網羅性・AWS 公式ドキュメントによる主張検証）

総評: High は系統 A の 2 件のみで、いずれも記述修正で解決。中核設計（PreSignUp 3 経路で全入口を
遮断・フェイルクローズ・拒否時に UNCONFIRMED ユーザーが残らない・pending の有界性）は
AWS 公式ドキュメントで裏付けが取れ、バイパス経路は発見されなかった。

## 指摘と対応

| ID | 重要度 | 指摘 | 対応（v1.1） |
|---|---|---|---|
| A-1 | H | Handler 記法 `src/auth/pre_signup.lambda_handler` は既存の `CodeUri: src/` + ドット区切り構成で成立しない | **反映**: `CodeUri: src/` + `Handler: auth.pre_signup.handler`、関数名も既存規約の `handler` に統一 |
| A-2 | H | CI デプロイ経路（deploy.yml）は Makefile と独立に OVERRIDES を組み立てるため `CognitoUserPoolArn` の配線が欠落。初回を CI で行うと Permission 欠落 → トリガー配線後に全サインアップ失敗 | **反映**: タスク #4 に deploy.yml 側の追加と GitHub Environment Variables 登録を明記。UsePreviousValue により 2 回目以降は省略可の注記も追加 |
| A-3 | M | prod での `CognitoUserPoolArn` 必須化ガードがなく既存規約（Rules による fail-fast）と不整合 | **反映**: `ProdRequiresCognitoUserPoolArn` Rule を追加。Makefile / deploy.yml にも prod fail-fast |
| A-4 | M | 「imported function への addPermission は no-op」は env 未指定スタック依存の条件付きの真。no-op 時は synth 警告も出る（B-L2 と同旨） | **反映**: `fromFunctionArn` → `fromFunctionAttributes({sameEnvironment: false, skipPermissions: true})` に変更し、no-op を明示・恒久化（警告も抑止） |
| A-5 | M | Timeout 10 秒は Cognito のトリガー応答制限 5 秒（変更不可・計 3 回再試行）と不整合（B-M4 と同旨） | **反映**: Timeout 5 秒 + botocore Config（connect/read 約 1 秒・リトライ最大 1 回）。再試行時の pending 重複書き込みが Condition で冪等である旨も明記 |
| A-6 | M | `allowlist-approve`（UpdateItem）は対象キーが無いと新規アイテムを作るため、ID コピーミスで幽霊 approved レコードが無言生成される | **反映**: `attribute_exists(identifier) AND status = pending` の ConditionExpression + 条件失敗時のエラー表示を仕様化 |
| A-7 | M | FunctionName / 専用 LogGroup（RetentionInDays 分岐）/ Tags の既存規約項目が未記載 | **反映**: `memoru-presignup-${Environment}` / LogGroup / Tags を明記 |
| A-8 | L | デプロイ順序の記述が「CDK 起点」と「SAM 起点」で揺れている | **反映**: 既存 prod 前提（SAM 起点）に統一し、新規構築時のみ手順 0（センチネルで CDK 先行）と場合分け。ガイド追記位置（2 章 / 3 章の往復）をタスク #5 に指定 |
| A-9 | L | template レベル pytest（`test_template_*.py` 慣行）への言及がない | **反映**: `tests/test_template_presignup.py` をテスト方針に追加 |
| A-10 | L | 細部: prod-config は VarSpec テーブル駆動に収まらない（センチネル判定を ARN 検証より先に）/ UserPool 置換時の SourceArn 陳腐化 / Makefile の `$(ID)` クォート | **反映**: いずれも該当節に明記 |
| B-1 | M | `preventUserExistenceErrors` はサインイン系のみ対象でサインアップは保護しない。SignUp の成否が許可リストのオラクルになり、承認済み・未登録メールの先回り登録（squat / pre-hijacking）が理論上可能 | **反映**: セキュリティ考慮表を正確化し残余リスクとして受容を明記。運用フローに検知・回復手順（UNCONFIRMED 確認 → AdminDeleteUser → 再登録、招待〜登録の時間窓短縮）を追加 |
| B-2 | M | トリガー未配線・フェイルオープンの検知手段がない。「公開前のクローズドな期間に実施」は背景（すでに開いている）と矛盾。既存アカウントの棚卸しが手順にない | **反映**: `make verify-presignup`（`describe-user-pool` の LambdaConfig 検証）を新設し手順で必須化。負テスト必須化。既存ユーザー棚卸しを手順 7 に追加。矛盾する注記は削除 |
| B-3 | M | LINE 経路の拒否メッセージは Hosted UI ではなくコールバックへの `error_description` リダイレクトで返り、現行 CallbackPage は握りつぶす。「PreSignUp failed with error」前置を仕様と呼ぶのは過大 | **反映**: 経路別の届き方を書き分け。承認待ちフローは招待時の事前説明で成立させる（受容）。フロント表示改修は任意タスク #7 化。前置形式に依存しない旨も明記 |
| B-4 | M | Timeout 5 秒制限（A-5 と同旨） | **反映**: A-5 参照 |
| B-5 | M | 「本人によるメール変更が不可能」は現行クライアント設定（user.admin スコープ非付与 + userSrp/custom 無効）に依存する暗黙の不変条件。将来の変更で許可リストが形骸化しうる | **反映**: セキュリティ考慮表に不変条件として明記し、前提を変える場合は `UserAttributeUpdateSettings` 導入と整合の再設計を必須とした |
| B-6 | L | pending の `display_name` は攻撃者制御値。承認判断の唯一の根拠にしてはならない。制御文字混入の余地 | **反映**: 保存時の長さ制限 + 制御文字除去を実装要件化。承認はアウトオブバンドの本人確認 + `created_at` 突合と明記 |
| B-7 | L | no-op の成立条件（A-4 と同旨） | **反映**: A-4 参照 |
| B-8 | L | 許可リスト変更（データプレーン操作）の証跡は実質ゼロであることを覆い隠す表現 | **反映**: 「証跡は残らない（受容）」と明示し、判定側の構造化ログを実質唯一の証跡として要件化 |
| B-9 | L | SignUp フラッド（UserCreation 50 RPS × 5 秒 ≈ 最大 250 同時実行）が共有同時実行プールを圧迫し本体 API に波及しうる | **反映**: `ReservedConcurrentExecutions: 10` を仕様化（スロットリングしてもフェイルクローズ）。アラームは任意タスク #6 化 |

## レビューで正しさが確認された主要な主張（抜粋）

- PreSignUp は self-service SignUp（直接 API 呼び出し含む）/ 外部 IdP 初回サインイン /
  AdminCreateUser の 3 経路すべてで発火し、federated ユーザーは Login/Authorize エンドポイント
  経由でしかサインインできないため全アカウント作成入口を覆える（残余は AWS 資格情報必須の経路のみ）
- トリガー例外はフェイルクローズで、**拒否された試行は UNCONFIRMED ユーザーとして残らない**
- ConfirmSignUp / ResendConfirmationCode / ForgotPassword 等の補助 API は侵入経路にならない
- federated username は `LINE_<sub>` 形式で、イベント `userName` からの導出 + 小文字化は
  `signInCaseSensitive: false` と整合し揺れが発生しない
- pending 書き込みは Condition + TTL + UserCreation クォータで有界
- テーブル定義・命名・Retain/PITR/SSE/TTL、CDK props / env var 注入 / プレースホルダガード、
  Makefile `build_param_overrides` 拡張、pytest+moto / Jest / mypy 構成はいずれも既存規約と整合
- ローカル開発（Keycloak / sam local / env.json）への影響なし
