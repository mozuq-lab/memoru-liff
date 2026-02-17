# code-review-fixes-v2 要件定義書

## 概要

2026-02-16 実施の第2回全体コードレビュー（Claude Opus 4.6 + OpenAI Codex MCP経由）で検出された Critical 2件・High 6件の計8件を修正するための要件定義。第1回レビュー修正（TASK-0023〜0041）完了後に実施された再レビューで、API契約不一致の残存と新規6件の問題が特定された。

## 関連文書

- **コードレビュー結果**: [📋 CODE_REVIEW_2026-02-16.md](../../CODE_REVIEW_2026-02-16.md)
- **ヒアリング記録**: [💬 interview-record.md](interview-record.md)
- **ユーザストーリー**: [📖 user-stories.md](user-stories.md)
- **受け入れ基準**: [✅ acceptance-criteria.md](acceptance-criteria.md)
- **コンテキストノート**: [📝 note.md](note.md)
- **API仕様**: [🔌 api-endpoints.md](../../design/memoru-liff/api-endpoints.md)
- **前回修正要件**: [📋 code-review-remediation/requirements.md](../code-review-remediation/requirements.md)

## 機能要件（EARS記法）

**【信頼性レベル凡例】**:

- 🔵 **青信号**: コードレビュー結果・既存設計文書・実装コード・ユーザヒアリングから確実に特定された要件
- 🟡 **黄信号**: コードレビュー結果から妥当な推測による要件
- 🔴 **赤信号**: コードレビュー結果にない推測による要件

---

### 通常要件

#### API 契約整合性（CR-01）

- REQ-V2-001: システムは SAM テンプレートの設定更新イベントパスを `PUT /users/me/settings` に定義しなければならない 🔵 *CR-01: SAM L255-260 が `PUT /users/me` で handler `PUT /users/me/settings` と不一致。設計文書 api-endpoints.md に準拠*
- REQ-V2-002: システムは SAM テンプレートのレビュー送信イベントパスを `POST /reviews/{cardId}` に定義しなければならない 🔵 *CR-01: SAM L305-310 が `POST /reviews` でパスパラメータなし。handler/frontend は `/reviews/<card_id>` で一致*
- REQ-V2-003: システムは SAM テンプレートに LINE 連携エンドポイント `POST /users/link-line` を定義しなければならない 🔵 *CR-01: SAM に LINE 連携イベント定義が欠落*
- REQ-V2-004: システムは Frontend API クライアントの LINE 連携パスを `POST /users/link-line` に統一しなければならない 🔵 *CR-01: frontend api.ts L149 が `/users/me/link-line` で handler `/users/link-line` と不一致*

#### データ整合性（CR-02）

- REQ-V2-011: システムは カード作成時の card_count 加算に `if_not_exists(card_count, :zero) + :inc` を使用しなければならない 🔵 *CR-02: card_service.py L106-127 で card_count 属性が存在しない場合にトランザクション失敗*
- REQ-V2-012: システムは TransactionCanceledException の CancellationReasons を解析し、上限超過とその他のエラーを正確に分類しなければならない 🔵 *CR-02: card_service.py L130-132 で一律 CardLimitExceededError に変換している*
- REQ-V2-013: システムは カード削除時にトランザクションで card_count を減算しなければならない 🔵 *CR-02: card_service.py L234-250 の delete_card で card_count 未減算*
- REQ-V2-014: システムは カード作成前にユーザーレコードの存在を保証しなければならない 🔵 *CR-02: handler.py L361 でユーザー存在保証なし*

#### セキュリティ（H-01）

- REQ-V2-021: システムは LINE 連携時にフロントエンドから LIFF ID トークンを受信しなければならない 🔵 *H-01: LinkLinePage.tsx L75-77 で line_user_id を直接送信。ユーザヒアリングで LIFF IDトークン検証方式に決定*
- REQ-V2-022: システムは LINE 連携時にサーバー側で LIFF ID トークンを LINE ID トークン検証 API で検証しなければならない 🔵 *H-01: handler.py L112-132 で本人性検証なし。ユーザヒアリングで方式決定*
- REQ-V2-023: システムは ID トークン検証成功後に取得した line_user_id でのみ連携を確定しなければならない 🟡 *H-01: IDトークン検証フローの実装詳細は LINE Login API 仕様に依存*

#### レスポンス契約（H-02）

- REQ-V2-031: システムは `PUT /users/me/settings` のレスポンスとして User 型オブジェクトを返却しなければならない 🔵 *H-02: handler.py L184 が `{success, settings}` を返却、frontend api.ts L141 は User 型を期待*
- REQ-V2-032: システムは `POST /users/link-line` のレスポンスとして User 型オブジェクトを返却しなければならない 🔵 *H-02: handler.py L133 が `{success, message}` を返却、frontend api.ts L148 は User 型を期待*
- REQ-V2-033: システムは Frontend の LINE 連携解除で専用エンドポイント `POST /users/me/unlink-line` を使用しなければならない 🔵 *H-02: LinkLinePage.tsx L94 が usersApi.updateUser() を使用、専用 API を呼んでいない*

#### 通知機能（H-03）

- REQ-V2-041: システムは 通知送信前にユーザーのタイムゾーンを考慮したローカル時刻を算出しなければならない 🔵 *H-03: notification_service.py L79-86 で時刻チェックなし。template.yaml L399 のコメントで「Lambda内で判定」と記載だが未実装*
- REQ-V2-042: システムは ユーザー設定の notification_time とローカル時刻が一致する場合のみ通知を送信しなければならない 🔵 *H-03: 日付チェックのみで時刻チェックがない*

#### 設定整合性（H-04, H-05, H-06）

- REQ-V2-051: システムは Frontend の API ベース URL 環境変数名を `VITE_API_BASE_URL` に統一しなければならない 🔵 *H-04: api.ts L14 が `VITE_API_BASE_URL`、deploy.yml L91/L169 が `VITE_API_URL`*
- REQ-V2-052: システムは Backend の HTTP クライアントライブラリを httpx に統一しなければならない 🔵 *H-05: line_service.py L12 で `import requests` だが requirements.txt に未宣言。ユーザヒアリングで httpx 統一に決定*
- REQ-V2-053: システムは OIDC クライアント ID を全レイヤーで `liff-client` に統一しなければならない 🔵 *H-06: realm-export.json/template.yaml L213 は `liff-client`、deploy.yml L95/auth.fixture.ts L32 は `memoru-liff`*

---

### 条件付き要件

#### データ整合性

- REQ-V2-101: card_count 属性がユーザーレコードに存在しない場合、システムは 0 として扱い安全に加算しなければならない 🔵 *CR-02: if_not_exists による初期値保証*
- REQ-V2-102: TransactionCanceledException のキャンセル理由がカード上限の場合のみ、システムは CardLimitExceededError を返却しなければならない 🔵 *CR-02: CancellationReasons の解析*
- REQ-V2-103: TransactionCanceledException のキャンセル理由がカード上限以外の場合、システムは 適切な内部エラーとして処理しなければならない 🟡 *CR-02: 条件分岐のフォールバック。具体的なエラー種別は実装時に確認*

#### 通知判定

- REQ-V2-111: ユーザーのローカル時刻が notification_time と一致しない場合、システムは そのユーザーへの通知をスキップしなければならない 🔵 *H-03: 時刻不一致時のスキップ動作*
- REQ-V2-112: ユーザーにタイムゾーン設定がない場合、システムは Asia/Tokyo をデフォルトとして使用しなければならない 🟡 *H-03: デフォルトタイムゾーンの設定。日本向けサービスとして妥当な推測*

#### LINE 連携検証

- REQ-V2-121: LIFF ID トークンの検証に失敗した場合、システムは 401 エラーを返却し連携を拒否しなければならない 🟡 *H-01: 検証失敗時の動作。セキュリティのベストプラクティスから推測*

---

### 制約要件

#### 技術制約

- REQ-V2-401: API 契約の統一は設計文書（api-endpoints.md）を単一ソースとし、SAM/handler/frontend を同時修正する 🔵 *ユーザヒアリングより*
- REQ-V2-402: HTTP ライブラリは httpx に統一し、requests は使用しない 🔵 *ユーザヒアリングより*
- REQ-V2-403: OIDC クライアント ID は `liff-client` に統一する 🔵 *ユーザヒアリングより*
- REQ-V2-404: 環境変数名は `VITE_API_BASE_URL` に統一する 🔵 *ユーザヒアリングより*
- REQ-V2-405: AWS リソースの実際のデプロイはユーザーが手動で実行する 🔵 *CLAUDE.md の注意事項より*

---

## 非機能要件

### セキュリティ

- NFR-V2-101: LINE 連携は LIFF ID トークンのサーバー側検証を必須としなければならない 🔵 *H-01: ユーザヒアリングで方式決定*
- NFR-V2-102: ID トークン検証は LINE Login API（`https://api.line.me/oauth2/v2.1/verify`）を使用しなければならない 🟡 *H-01: LINE Login API の標準的な検証エンドポイント*

### データ整合性

- NFR-V2-201: card_count の更新は DynamoDB トランザクションで原子的に行わなければならない 🔵 *CR-02: 並行リクエスト下でのデータ整合性*
- NFR-V2-202: カード作成・削除ともに card_count の整合性を維持しなければならない 🔵 *CR-02: 削除時の減算も含む*

### 信頼性

- NFR-V2-301: 通知送信は notification_time ±5分の精度で実行されるべき 🟡 *H-03: EventBridge cron の実行精度を考慮*

---

## Edgeケース

### エラー処理

- EDGE-V2-001: LINE ID トークンの有効期限が切れている場合、再取得を促すエラーメッセージを返却する 🟡 *H-01: IDトークンのライフサイクルから推測*
- EDGE-V2-002: card_count が負数にならないよう、削除トランザクションで下限チェックする 🟡 *CR-02: 削除減算時の防御的プログラミング*
- EDGE-V2-003: TransactionCanceledException が CancellationReasons なしで発生した場合、内部エラーとして処理する 🟡 *CR-02: DynamoDB API の例外パターンから推測*

### 境界値

- EDGE-V2-101: card_count = 0 のユーザーがカードを削除しようとした場合、card_count を負数にしない 🟡 *CR-02: card_count 整合性の境界ケース*
- EDGE-V2-102: notification_time が日付境界（23:55 等）で、タイムゾーン変換後に翌日になる場合の正確な判定 🟡 *H-03: タイムゾーン変換の境界ケース*

---

## 信頼性レベルサマリー

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 29件 | 76% |
| 🟡 黄信号 | 9件 | 24% |
| 🔴 赤信号 | 0件 | 0% |

**品質評価**: ✅ 高品質（青信号が76%、赤信号なし）

---

## 対応フェーズ

### Phase 1: Critical 修正（P0）

| # | 要件ID | 対応項目 | レビューID |
|---|--------|---------|-----------|
| 1 | REQ-V2-001〜004 | API ルート統一（SAM/handler/frontend 3レイヤー同時修正） | CR-01 |
| 2 | REQ-V2-011〜014, 101〜103 | card_count トランザクション修正 | CR-02 |

### Phase 2: High 修正（P1）

| # | 要件ID | 対応項目 | レビューID |
|---|--------|---------|-----------|
| 3 | REQ-V2-021〜023, 121 | LINE 連携サーバー側本人性検証 | H-01 |
| 4 | REQ-V2-031〜033 | レスポンス DTO 統一 + unlinkLine API 使用 | H-02 |
| 5 | REQ-V2-041〜042, 111〜112 | 通知時刻/タイムゾーン判定実装 | H-03 |
| 6 | REQ-V2-051 | 環境変数名統一 | H-04 |
| 7 | REQ-V2-052 | httpx 統一（requests 除去） | H-05 |
| 8 | REQ-V2-053 | OIDC クライアント ID 統一 | H-06 |

---

## 付録: Medium/Low レベル指摘事項（将来対応）

以下は今回の修正スコープ外だが、将来の改善として記録する。

### Medium (P2)

| ID | 問題 | 影響 |
|----|------|------|
| M-01 | Reviews テーブル TTL 未設定 | レビューデータ無限蓄積、コスト増加 |
| M-02 | レビュー記録失敗のサイレントキャッチ | 障害検知不可 |
| M-03 | limit パラメータ直キャストで 500 エラー | 不正入力時のサーバーエラー |
| M-04 | エラーレスポンス形式の不一致 | フロントのエラー解析失敗 |
| M-05 | 通知対象取得が全件 scan | スケーラビリティ課題 |
| M-06 | CSP に unsafe-inline 残存 | XSS 耐性低下（LIFF SDK 制約との兼ね合い） |
| M-07 | 契約テスト・E2E テスト不足 | API 不整合の再発リスク |
| M-08 | silent renew コールバック経路不足 | トークン自動更新失敗 |

### Low (P3)

| ID | 問題 | 影響 |
|----|------|------|
| L-01 | README の API 表が実装と不一致 | ドキュメント信頼性低下 |
| L-02 | テストユーザーの平文パスワード記載 | セキュリティリスク（低） |
