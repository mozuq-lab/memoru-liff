# code-review-remediation 要件定義書

## 概要

2026-02-15 実施の全体コードレビュー（Claude Opus 4.6 × 3 ドメイン別 + OpenAI Codex 全体横断）で検出された Critical（7 件）および High（12 件）レベルの問題を修正するための要件定義。本番デプロイ前に必ず対処すべき品質・セキュリティ・機能不備を網羅する。

## 関連文書

- **コードレビュー結果**: [📋 CODE_REVIEW_2026-02-15.md](../../CODE_REVIEW_2026-02-15.md)
- **ヒアリング記録**: [💬 interview-record.md](interview-record.md)
- **ユーザストーリー**: [📖 user-stories.md](user-stories.md)
- **受け入れ基準**: [✅ acceptance-criteria.md](acceptance-criteria.md)
- **コンテキストノート**: [📝 note.md](note.md)
- **元要件定義書**: [📋 requirements.md](../memoru-liff/requirements.md)
- **API仕様**: [🔌 api-endpoints.md](../../design/memoru-liff/api-endpoints.md)

## 機能要件（EARS記法）

**【信頼性レベル凡例】**:

- 🔵 **青信号**: コードレビュー結果・既存設計文書・実装コードから確実に特定された要件
- 🟡 **黄信号**: コードレビュー結果から妥当な推測による要件
- 🔴 **赤信号**: コードレビュー結果にない推測による要件

---

### 通常要件

#### API 契約整合性

- REQ-CR-001: システムは Backend ハンドラーのルート定義と SAM テンプレートの API パスを一致させなければならない 🔵 *C-01: handler.py `/cards/due` vs template.yaml `/reviews/due` の不一致*
- REQ-CR-002: システムは Backend ハンドラーのルート定義と Frontend API クライアントのパスを一致させなければならない 🔵 *C-01: api.ts のパス定義との整合*
- REQ-CR-003: システムは Backend のレスポンスモデル（Pydantic）と Frontend の TypeScript 型定義のフィールド名・構造を一致させなければならない 🔵 *C-02: Card/User モデルの契約不一致*
- REQ-CR-004: システムは DELETE 操作の 204 No Content レスポンスを正しくハンドリングしなければならない 🔵 *C-05: api.ts が全レスポンスを JSON パース*

#### 認証フロー

- REQ-CR-005: システムは OIDC コールバックページで `authService.handleCallback()` を呼び出し、PKCE フローを完結させなければならない 🔵 *C-03: CallbackPage.tsx でトークン取得未完了*
- REQ-CR-006: システムは アプリ起動時に OIDC 環境変数バリデーション（`validateOidcConfig()`）を実行しなければならない 🔵 *C-07: main.tsx でバリデーション未呼び出し*
- REQ-CR-007: システムは API クライアントで 401 エラー時にトークンリフレッシュとリトライを自動実行しなければならない 🟡 *H-08: api.ts にリフレッシュ機能なし*
- REQ-CR-008: システムは ProtectedRoute で認証リダイレクトの重複呼び出しを防止しなければならない 🔵 *H-09: render 中の login() 無限ループリスク*

#### セキュリティ

- REQ-CR-009: システムは LINE Webhook 署名検証で空署名の場合も `hmac.compare_digest` を使用したタイミングセーフな比較を行わなければならない 🔵 *C-06: 早期リターンによるタイミング攻撃リスク*
- REQ-CR-010: システムは CSP ヘッダーから `unsafe-eval` を除去しなければならない 🔵 *H-02: XSS 耐性低下*
- REQ-CR-011: システムは 本番環境の Keycloak で HTTPS を強制しなければならない 🔵 *H-03: HTTP 運用可能な構成*

#### IAM / 権限

- REQ-CR-012: システムは DuePush Lambda に Users テーブルへの `dynamodb:UpdateItem` 権限を付与しなければならない 🔵 *C-04: last_notified_date 更新が権限不足で失敗*

#### データ整合性

- REQ-CR-013: システムは 全ての datetime 処理で timezone-aware な `datetime.now(timezone.utc)` を使用しなければならない 🔵 *H-01: naive/aware 混在*
- REQ-CR-014: システムは 通知スケジュールの cron 式とコメントの記述を一致させ、ユーザー設定の通知時刻を尊重しなければならない 🔵 *H-05: cron 式とコメントの矛盾*
- REQ-CR-015: システムは カード数制限チェックにおいて Race Condition を防止しなければならない 🔵 *H-06: get_card_count と put_item の間の並行リスク*

#### 品質・パフォーマンス

- REQ-CR-016: システムは Bedrock API リトライにフルジッター（Full Jitter）を適用しなければならない 🔵 *H-07: Thundering Herd 問題*
- REQ-CR-017: システムは Context API の Provider 値を `useMemo`/`useCallback` でメモ化しなければならない 🔵 *H-10: 不要な再レンダリング*

#### 機能追加

- REQ-CR-018: システムは LINE 連携解除 API エンドポイントを提供しなければならない 🔵 *H-04: Frontend に UI あるが Backend 未実装*

### 条件付き要件

#### API レスポンス処理

- REQ-CR-101: API レスポンスの HTTP ステータスコードが 204 の場合、システムは JSON パースをスキップして `undefined` を返さなければならない 🔵 *C-05: 204 レスポンス処理*

#### 認証エラー

- REQ-CR-102: API レスポンスの HTTP ステータスコードが 401 の場合、システムは トークンリフレッシュを試行し、成功すれば元のリクエストをリトライしなければならない 🟡 *H-08: トークン期限切れ対策*
- REQ-CR-103: トークンリフレッシュが失敗した場合、システムは ユーザーをログイン画面にリダイレクトしなければならない 🟡 *H-08: リフレッシュ失敗時のフォールバック*

#### 認証ガード

- REQ-CR-104: ProtectedRoute で login() が既に呼び出し済みの場合、システムは 重複した login() 呼び出しを抑止しなければならない 🔵 *H-09: loginAttempted フラグ*

#### インフラ環境分離

- REQ-CR-105: 環境が開発（dev）の場合、システムは Keycloak で HTTP を許可してもよいが、本番（prod）では HTTPS のみを許可しなければならない 🟡 *H-03: 環境に応じた設定*

---

### 制約要件

#### 技術制約

- REQ-CR-401: API 契約の統一は手動で実施し、OpenAPI スキーマの自動生成は導入しない 🔵 *ユーザヒアリングより*
- REQ-CR-402: 既存テストを更新し、回帰テストを確認する。新規テストケースの追加も行う 🔵 *ユーザヒアリングより*
- REQ-CR-403: AWS リソースの実際のデプロイはユーザーが手動で実行する 🔵 *CLAUDE.md の注意事項より*

#### インフラ制約

- REQ-CR-411: DuePush Lambda の IAM ポリシー変更は SAM テンプレートで管理する 🔵 *既存インフラ管理方針*
- REQ-CR-412: CSP ヘッダーの変更は CloudFront ResponseHeadersPolicy で管理する 🔵 *既存インフラ管理方針*
- REQ-CR-413: CloudWatch Logs の保存期間は本番 90 日、開発 14 日とする 🟡 *H-12: コスト最適化の推奨値*
- REQ-CR-414: 開発環境の NAT Gateway を削除し、ECS タスクを Public Subnet に配置可能とする 🟡 *H-11: コスト最適化*

---

## 非機能要件

### パフォーマンス

- NFR-CR-001: Context API のメモ化により、不要な再レンダリングを 50% 以上削減すべき 🟡 *H-10: パフォーマンス改善目標*
- NFR-CR-002: Bedrock API リトライのジッターにより、並列 Lambda 実行時のリクエスト集中を緩和すべき 🔵 *H-07: Thundering Herd 対策*

### セキュリティ

- NFR-CR-101: LINE Webhook 署名検証はタイミングセーフでなければならない 🔵 *C-06: hmac.compare_digest 徹底*
- NFR-CR-102: CSP ヘッダーは `unsafe-eval` を含んではならない 🔵 *H-02: XSS 耐性*
- NFR-CR-103: 本番環境の全通信は HTTPS でなければならない 🔵 *H-03: 既存 NFR-101 の強化*

### 信頼性

- NFR-CR-201: DuePush Lambda は通知送信後に確実に `last_notified_date` を更新できなければならない 🔵 *C-04: 重複通知防止*
- NFR-CR-202: カード数制限は並行リクエスト下でも正確に機能しなければならない 🔵 *H-06: データ整合性*

### コスト

- NFR-CR-301: 開発環境の月額コストを NAT Gateway 削除により $30-40 削減すべき 🟡 *H-11: 年間 $360-480 削減*
- NFR-CR-302: CloudWatch Logs の保存期間設定により年間 $50-200 のコスト削減を目指すべき 🟡 *H-12: コスト最適化*

---

## Edgeケース

### エラー処理

- EDGE-CR-001: LINE Webhook 署名が空文字列の場合、タイミングセーフに拒否する 🔵 *C-06: 空署名のハンドリング*
- EDGE-CR-002: OIDC コールバックでエラーパラメータが含まれる場合、エラー画面を表示する 🟡 *C-03: コールバック異常系*
- EDGE-CR-003: トークンリフレッシュ中に複数の API リクエストが 401 を受けた場合、リフレッシュを1回のみ実行する 🟡 *H-08: 並行リフレッシュの防止*

### 境界値

- EDGE-CR-101: カード数がちょうど 2,000 枚の状態で同時に 2 つのカード作成リクエストが到着した場合、1 つのみ成功する 🔵 *H-06: Race Condition の境界値*
- EDGE-CR-102: datetime が UTC+0 の日付境界（00:00:00）をまたぐ場合、due 計算が正しく動作する 🟡 *H-01: timezone 統一後の境界値*
- EDGE-CR-103: Bedrock API が 3 回連続でタイムアウトした場合、ジッター付きバックオフで最大待機時間を超えない 🟡 *H-07: リトライ上限*

---

## 信頼性レベルサマリー

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 30件 | 73% |
| 🟡 黄信号 | 11件 | 27% |
| 🔴 赤信号 | 0件 | 0% |

**品質評価**: ✅ 高品質（青信号が70%以上、赤信号なし）

---

## 対応フェーズ

### Phase 1: Critical 修正（1 週間以内）

| # | 要件ID | 対応項目 | 工数目安 |
|---|--------|---------|---------|
| 1 | REQ-CR-001, 002 | API ルート統一 | 0.5日 |
| 2 | REQ-CR-003 | API レスポンス契約統一 | 1日 |
| 3 | REQ-CR-005 | OIDC コールバック実装 | 0.5日 |
| 4 | REQ-CR-012 | DuePush IAM 権限修正 | 0.5日 |
| 5 | REQ-CR-004, 101 | 204 レスポンス処理修正 | 0.5日 |
| 6 | REQ-CR-009 | LINE 署名タイミング攻撃対策 | 0.5日 |
| 7 | REQ-CR-006 | 環境変数バリデーション有効化 | 0.5日 |

### Phase 2: High 修正（2 週間以内）

| # | 要件ID | 対応項目 | 工数目安 |
|---|--------|---------|---------|
| 1 | REQ-CR-013 | datetime 統一 | 0.5日 |
| 2 | REQ-CR-010 | CSP 強化 | 0.5日 |
| 3 | REQ-CR-011, 105 | Keycloak HTTPS 強制 | 0.5日 |
| 4 | REQ-CR-018 | LINE 連携解除 API | 0.5日 |
| 5 | REQ-CR-014 | 通知 cron 修正 | 0.5日 |
| 6 | REQ-CR-015 | Race Condition 対策 | 0.5日 |
| 7 | REQ-CR-016 | Bedrock リトライジッター | 0.5日 |
| 8 | REQ-CR-007, 102, 103 | Token リフレッシュ | 1日 |
| 9 | REQ-CR-008, 104 | ProtectedRoute 修正 | 0.5日 |
| 10 | REQ-CR-017 | Context メモ化 | 0.5日 |
| 11 | REQ-CR-413, 414 | NAT Gateway / Logs 最適化 | 0.5日 |
