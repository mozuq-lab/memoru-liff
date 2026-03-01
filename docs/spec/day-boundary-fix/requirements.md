# day-boundary-fix 要件定義書（軽量版）

## 概要

`feature/day-boundary-spec` ブランチのコードレビュー（Claude Opus 4.6 + OpenAI Codex）で発見された指摘事項を修正する。マージ前に対応すべき Critical/High の不具合修正と、テスト・ドキュメントの品質改善を行う。

## 関連文書

- **コードレビュー結果**: [CODE_REVIEW_day-boundary.md](../../reviews/CODE_REVIEW_day-boundary.md)
- **ヒアリング記録**: [interview-record.md](interview-record.md)
- **コンテキストノート**: [note.md](note.md)
- **元要件定義**: [day-boundary requirements.md](../day-boundary/requirements.md)

## 主要機能要件

**【信頼性レベル凡例】**:
- 🔵 **青信号**: コードレビュー指摘・既存実装の調査に基づく確実な要件
- 🟡 **黄信号**: 既存実装・設計パターンから妥当な推測による要件

### 必須機能（Must Have）

- REQ-001: `calculate_next_review_boundary()` は `day_start_hour` 引数を `int` に正規化してから使用しなければならない 🔵 *コードレビュー指摘 #1 (Critical)。DynamoDB が Number 型を Decimal として返すため*
  - 入口で `int(day_start_hour)` を実行
  - 範囲チェック: `0 <= day_start_hour <= 23` でなければ `ValueError` を raise
  - `interval` 引数も同様に `int()` で正規化する

- REQ-002: `UserSettingsRequest.validate_timezone()` は `ZoneInfo` で IANA タイムゾーンの実在を検証しなければならない 🔵 *コードレビュー指摘 #2 (High)。非実在 TZ が保存されると実行時に 500 エラー*
  - 設定更新時に `ZoneInfo(v)` で実在検証
  - `ZoneInfoNotFoundError` または `KeyError` の場合、`ValueError` を raise して 400 を返す
  - 既存の正規表現バリデーションは削除し、`ZoneInfo` 検証に置き換える

- REQ-003: `calculate_next_review_boundary()` は `ZoneInfo` 失敗時にデフォルト `Asia/Tokyo` にフォールバックしなければならない 🔵 *ヒアリングで「両方」（多層防御）を選択*
  - `ZoneInfoNotFoundError` / `KeyError` を catch
  - フォールバック時にログ出力（Logger 使用）
  - バリデーション突破やDB直接操作による不正値への防御

- REQ-004: テストの弱いアサーション `assert A or B` を単一期待値に修正しなければならない 🔵 *コードレビュー指摘 #4 (Low)*
  - `test_review_service.py` の `test_next_review_at_normalized_to_day_boundary` で `due_date` の期待値を1つに固定
  - 現行仕様（UTC 基準の日付）に合わせた期待値を使用

- REQ-005: `interview-record.md` の Q4 選択肢範囲の記述を実装と整合させなければならない 🔵 *コードレビュー指摘 #6 (Info)*
  - 「0時〜6時（推奨）を選択。7つの選択肢。」→ 実装仕様に合わせて更新

### 推奨改善（Should Have）

- REQ-101: `srs.py` の `zoneinfo` import をモジュールレベルに移動するべきである 🟡 *コードレビュー指摘 #7 (Nit)。Python 慣例*
  - 関数内 `from zoneinfo import ZoneInfo` → モジュールレベルに移動

- REQ-102: `User.from_dynamodb_item()` のデフォルト settings に `day_start_hour` を追加するべきである 🟡 *コードレビュー指摘 #8 (Nit)。一貫性*
  - `{"notification_time": "09:00", "timezone": "Asia/Tokyo"}` → `{"notification_time": "09:00", "timezone": "Asia/Tokyo", "day_start_hour": 4}`

- REQ-103: Decimal 入力と不正 timezone のテストケースを追加するべきである 🔵 *コードレビュー指摘 #1, #2 の修正に対応するテスト*
  - `test_srs.py`: `Decimal(4)` を `day_start_hour` に渡すテスト
  - `test_srs.py`: 不正 timezone のフォールバックテスト
  - `test_user_models.py`: 非実在 timezone のバリデーションエラーテスト

### スコープ外（後続タスク）

- `due_date` の UTC vs ローカル日付問題（コードレビュー指摘 #3）→ API 契約の仕様合意が必要
- DST 遷移時の厳密処理（コードレビュー指摘 #5）→ 多タイムゾーン対応時

## 基本的な制約

- REQ-401: 既存の `calculate_next_review_boundary()` のインターフェース（引数名・戻り値型）は変更しない 🔵 *後方互換性*
- REQ-402: 既存テストが全て通る状態を維持する 🔵 *リグレッション防止*
- REQ-403: `calculate_sm2()` は変更しない 🔵 *元要件 REQ-403 の維持*

## 簡易ユーザーストーリー

### ストーリー1: DynamoDB 経由でも正常にレビューできる

**私は** 学習者 **として**
**day_start_hour を設定した後もレビュー送信が正常に動作してほしい**
**そうすることで** 実運用環境で 500 エラーに遭遇しない

**関連要件**: REQ-001

### ストーリー2: 不正な timezone を設定できない

**私は** 学習者 **として**
**存在しないタイムゾーンを設定しようとした場合にエラーが返されてほしい**
**そうすることで** 後のレビュー送信で予期せぬエラーに遭遇しない

**関連要件**: REQ-002, REQ-003

## 基本的な受け入れ基準

### REQ-001: Decimal 型の正規化

**Given**: DynamoDB に `day_start_hour` が `Decimal(4)` として保存されている
**When**: レビュー送信時に `calculate_next_review_boundary()` が呼ばれる
**Then**: `Decimal` が `int` に正規化され、正常に境界時刻が計算される

**テストケース**:
- [ ] 正常系: `Decimal(4)` を渡しても `int(4)` と同じ結果が返る
- [ ] 正常系: `Decimal(0)` / `Decimal(23)` の境界値が正常に動作する
- [ ] 異常系: 範囲外の値 `Decimal(24)` / `Decimal(-1)` で `ValueError`

### REQ-002: timezone 実在検証

**Given**: ユーザーが設定画面で timezone を変更する
**When**: 存在しない timezone `"Foo/Bar"` を送信する
**Then**: バリデーションエラー (400) が返される

**テストケース**:
- [ ] 正常系: `"Asia/Tokyo"`, `"UTC"` が受け入れられる
- [ ] 異常系: `"Foo/Bar"` が拒否される
- [ ] 異常系: `"Invalid/Zone"` が拒否される

### REQ-003: ZoneInfo フォールバック

**Given**: DynamoDB に不正な timezone が保存されている（DB直接操作等）
**When**: `calculate_next_review_boundary()` が呼ばれる
**Then**: `Asia/Tokyo` にフォールバックし、500 エラーにならない

**テストケース**:
- [ ] 正常系: 不正 timezone でフォールバック動作
- [ ] 正常系: フォールバック時にログが出力される

## 最小限の非機能要件

- **堅牢性**: DynamoDB の型変換（Decimal）と不正入力に対する防御的プログラミング 🔵
- **後方互換性**: 既存 API のインターフェースは変更しない。内部実装の修正のみ 🔵
- **テスト品質**: 修正に対応するテストケースを追加し、回帰検知力を強化 🔵
