# TDD要件定義書: 通知時刻/タイムゾーン判定

**タスクID**: TASK-0046
**要件名**: code-review-fixes-v2
**機能名**: 通知時刻/タイムゾーン判定 (notification-timezone)
**作成日**: 2026-02-21
**TDDフェーズ**: 要件定義

---

## 1. 機能の概要（EARS要件定義書・設計文書ベース）

### 1.1 何をする機能か 🔵

**信頼性**: 🔵 *REQ-V2-041, REQ-V2-042, architecture.md セクション2.3 より確認*

通知送信前にユーザーのタイムゾーンを考慮したローカル時刻を算出し、ユーザー設定の `notification_time` と一致する場合のみ通知を送信する機能。現行の `notification_service.py` では日付チェック（`last_notified_date == today`）のみで時刻チェックがなく、EventBridge の 5分間隔 cron が起動するたびに全ユーザーに対して通知処理が実行される問題がある。

### 1.2 どのような問題を解決するか 🔵

**信頼性**: 🔵 *H-03: notification_service.py L79-86 で時刻チェックなし。template.yaml L399 のコメントで「Lambda内で判定」と記載だが未実装*

- **問題1**: ユーザーが設定した通知時刻（例: 09:00）に関係なく、EventBridge 起動時に常に通知が送信される
- **問題2**: タイムゾーンが考慮されていないため、異なるタイムゾーンのユーザーに不適切な時刻に通知が届く
- **問題3**: EventBridge が 5分ごとに起動するが、`last_notified_date` チェックにより最初の起動で全員に通知されてしまう

### 1.3 想定されるユーザー 🔵

**信頼性**: 🔵 *要件定義書・user-stories.md より*

- LINE 連携済みのユーザー（暗記カード学習者）
- 異なるタイムゾーンに在住するユーザー（主に日本、一部海外）

### 1.4 システム内での位置づけ 🔵

**信頼性**: 🔵 *architecture.md セクション2.3、dataflow.md セクション4 より*

```
EventBridge (5分間隔 cron) → Lambda → NotificationService.process_notifications()
    → [新規] should_notify() でタイムゾーン/時刻判定
    → CardService.get_due_card_count()
    → LineService.push_message()
```

バックエンドの `NotificationService` 内に `should_notify()` メソッドを追加し、`process_notifications()` から呼び出す。フロントエンドの設定画面（`SettingsPage`）からタイムゾーン設定を更新可能にする。

- **参照したEARS要件**: REQ-V2-041, REQ-V2-042, REQ-V2-111, REQ-V2-112
- **参照した設計文書**: architecture.md セクション2.3「通知時刻/タイムゾーン判定 (H-03)」、dataflow.md セクション4「通知送信フロー」

---

## 2. 入力・出力の仕様（EARS機能要件・コード分析ベース）

### 2.1 should_notify メソッド 🔵

**信頼性**: 🔵 *architecture.md セクション2.3 の設計コード、notification_service.py の既存実装分析より*

#### 入力パラメータ

| パラメータ | 型 | 制約 | 説明 |
|-----------|-----|------|------|
| `user` | `User` | 必須 | ユーザーオブジェクト。`settings` 辞書内に `timezone` と `notification_time` を含む |
| `current_utc` | `datetime` | 必須、timezone-aware (UTC) | 現在のUTC時刻 |

#### 出力値

| 戻り値 | 型 | 説明 |
|-------|-----|------|
| 判定結果 | `bool` | `True`: 通知すべき（ローカル時刻が notification_time と ±5分以内で一致）、`False`: 通知不要 |

#### User.settings の関連フィールド

| フィールド | 型 | デフォルト値 | 説明 |
|-----------|-----|-------------|------|
| `settings.timezone` | `str` | `"Asia/Tokyo"` | IANA タイムゾーン名 |
| `settings.notification_time` | `str` | `"09:00"` | 通知時刻（HH:MM 24時間制） |

**現状の User モデル（コード確認済み）**: `backend/src/models/user.py`
- `settings` は `dict` 型（`Field(default_factory=lambda: {"notification_time": "09:00", "timezone": "Asia/Tokyo"})`）
- 個別の `timezone` / `notification_time` 属性はない（`settings` 辞書内に格納）
- `to_response()` メソッドで `settings.get("timezone", "Asia/Tokyo")` により取得

### 2.2 process_notifications メソッド（既存修正） 🔵

**信頼性**: 🔵 *notification_service.py の既存実装 L47-130、architecture.md セクション2.3 より*

#### 入力パラメータ（変更なし）

| パラメータ | 型 | 制約 | 説明 |
|-----------|-----|------|------|
| `current_time` | `datetime` | 必須 | 現在時刻（既存のシグネチャを維持） |

#### 出力値（変更なし）

| 戻り値 | 型 | 説明 |
|-------|-----|------|
| 結果 | `NotificationResult` | `processed`, `sent`, `skipped`, `errors` を含む結果オブジェクト |

#### 修正内容

`last_notified_date` チェック後、`should_notify()` による時刻判定を追加する。

### 2.3 update_settings メソッド（既存確認） 🔵

**信頼性**: 🔵 *user_service.py L250-309 の既存実装確認*

**現状**: `timezone` パラメータの処理は **既に実装済み**。`user_service.update_settings()` は `notification_time` と `timezone` の両方を受け付け、`settings` 辞書の対応するキーを DynamoDB で更新する。

```python
# 既存実装（user_service.py L250-309）
def update_settings(self, user_id: str, notification_time: Optional[str] = None, timezone: Optional[str] = None) -> User:
```

### 2.4 ハンドラーの settings 更新（既存確認） 🔵

**信頼性**: 🔵 *handler.py L158-196 の既存実装確認*

**現状**: ハンドラーでの `timezone` パラメータ処理は **既に実装済み**。

```python
# 既存実装（handler.py L186-190）
user = user_service.update_settings(
    user_id,
    notification_time=request.notification_time,
    timezone=request.timezone,
)
```

### 2.5 データフロー 🔵

**信頼性**: 🔵 *dataflow.md セクション4「通知送信フロー」の After 図より*

```
EventBridge (5分ごと)
  → Lambda 起動
    → NotificationService.process_notifications(current_time)
      → UserService.get_linked_users() → linked_users
      → loop 各ユーザー:
          → last_notified_date == today? → skip
          → [NEW] should_notify(user, current_utc)? → False → skip
          → CardService.get_due_card_count() → due_count
          → due_count > 0 → LineService.push_message()
          → UserService.update_last_notified_date()
```

- **参照したEARS要件**: REQ-V2-041, REQ-V2-042
- **参照した設計文書**: dataflow.md セクション4、architecture.md セクション2.3

---

## 3. 制約条件（EARS非機能要件・アーキテクチャ設計ベース）

### 3.1 パフォーマンス要件 🟡

**信頼性**: 🟡 *NFR-V2-301: EventBridge cron の実行精度を考慮した推測*

- 通知判定は ±5分の精度で実行される（EventBridge の 5分間隔 cron 実行に対応）
- `should_notify()` メソッドは各ユーザーに対して O(1) で実行される（タイムゾーン変換 + 分単位比較）

### 3.2 セキュリティ要件 🔵

**信頼性**: 🔵 *バックエンド修正のみでセキュリティ変更なし*

- タイムゾーン設定の更新は認証済みユーザー（JWT検証済み）のみ可能（既存の認証基盤を利用）
- 無効なタイムゾーン名のバリデーションは `UserSettingsRequest` の `validate_timezone` で実施済み

### 3.3 互換性要件 🔵

**信頼性**: 🔵 *architecture.md DB スキーマ変更セクション、既存コード分析より*

- DynamoDB はスキーマレスのため DDL 変更不要
- 既存レコードに `timezone` がない場合（`settings` 辞書に `timezone` キーが存在しない場合）、コード側で `"Asia/Tokyo"` をデフォルトとして扱う
- `User.from_dynamodb_item()` で `settings` が存在しない場合のデフォルト値（`{"notification_time": "09:00", "timezone": "Asia/Tokyo"}`）は既に実装済み

### 3.4 アーキテクチャ制約 🔵

**信頼性**: 🔵 *CLAUDE.md、architecture.md 技術的制約セクションより*

- Python 3.12 Lambda ランタイムを使用
- タイムゾーン処理には Python 3.9+ 標準ライブラリの `zoneinfo` モジュールを使用（外部依存なし）
- `should_notify()` は `NotificationService` クラスのインスタンスメソッドとして追加
- AWS リソースの実際のデプロイはユーザーが手動で実行

### 3.5 データベース制約 🔵

**信頼性**: 🔵 *既存コード分析より*

- `settings` は DynamoDB の Map 型として保存される
- `settings.timezone` は String 型、IANA タイムゾーン名を格納
- `settings.notification_time` は String 型、HH:MM 形式を格納

### 3.6 API制約 🔵

**信頼性**: 🔵 *api-endpoints.md、handler.py の既存実装確認より*

- `PUT /users/me/settings` は `notification_time` と `timezone` の両方を受け付ける（既に実装済み）
- `UserSettingsRequest` モデルで `timezone` フィールドのバリデーションが実装済み

- **参照したEARS要件**: NFR-V2-301, REQ-V2-112
- **参照した設計文書**: architecture.md セクション2.3、DB スキーマ変更セクション

---

## 4. 想定される使用例（EARSEdgeケース・データフローベース）

### 4.1 基本的な使用パターン 🔵

**信頼性**: 🔵 *REQ-V2-041, REQ-V2-042 より*

#### パターン1: 通知時刻一致（Asia/Tokyo）

- **Given**: `timezone='Asia/Tokyo'`, `notification_time='09:00'`, UTC時刻 = 00:00 (JST 09:00)
- **When**: `should_notify(user, current_utc)` を呼び出す
- **Then**: `True` を返す

#### パターン2: 通知時刻不一致

- **Given**: `timezone='Asia/Tokyo'`, `notification_time='09:00'`, UTC時刻 = 06:00 (JST 15:00)
- **When**: `should_notify(user, current_utc)` を呼び出す
- **Then**: `False` を返す

#### パターン3: ±5分の精度判定（範囲内）

- **Given**: `timezone='Asia/Tokyo'`, `notification_time='09:00'`, UTC時刻 = 00:03 (JST 09:03)
- **When**: `should_notify(user, current_utc)` を呼び出す
- **Then**: `True` を返す（差分3分、±5分以内）

#### パターン4: ±5分の精度判定（範囲外）

- **Given**: `timezone='Asia/Tokyo'`, `notification_time='09:00'`, UTC時刻 = 00:06 (JST 09:06)
- **When**: `should_notify(user, current_utc)` を呼び出す
- **Then**: `False` を返す（差分6分、±5分超過）

#### パターン5: 異なるタイムゾーンでの通知判定

- **Given**: `timezone='America/New_York'` (UTC-5, EST), `notification_time='09:00'`, UTC時刻 = 14:00
- **When**: `should_notify(user, current_utc)` を呼び出す
- **Then**: `True` を返す（EST 09:00）

### 4.2 エッジケース 🟡

**信頼性**: 🟡 *EDGE-V2-102 およびタイムゾーン変換の境界ケースから推測*

#### エッジケース1: タイムゾーン未設定のデフォルト

- **Given**: `settings` に `timezone` キーが存在しない、`notification_time='09:00'`, UTC時刻 = 00:00
- **When**: `should_notify(user, current_utc)` を呼び出す
- **Then**: `Asia/Tokyo` として判定され、`True` を返す

#### エッジケース2: 日付境界をまたぐケース

- **Given**: `timezone='America/New_York'`, `notification_time='23:58'`, ローカル時刻 = 00:01
- **When**: `should_notify(user, current_utc)` を呼び出す
- **Then**: `True` を返す（差分3分、日付境界を正しく処理）

#### エッジケース3: notification_time 未設定のデフォルト

- **Given**: `settings` に `notification_time` キーが存在しない、`timezone='Asia/Tokyo'`, UTC時刻 = 00:00
- **When**: `should_notify(user, current_utc)` を呼び出す
- **Then**: デフォルトの `'09:00'` として判定され、`True` を返す

### 4.3 エラーケース 🟡

**信頼性**: 🟡 *無効なタイムゾーン名の扱いは設計文書に詳細なし。防御的プログラミングから推測*

#### エラーケース1: 無効なタイムゾーン名

- **Given**: `timezone='Invalid/Timezone'`, `notification_time='09:00'`
- **When**: `should_notify(user, current_utc)` を呼び出す
- **Then**: `Asia/Tokyo` をフォールバックとして使用し、判定を継続する（例外を発生させない）

### 4.4 統合使用パターン 🔵

**信頼性**: 🔵 *dataflow.md セクション4 の After 図より*

#### 統合パターン1: process_notifications での should_notify 使用

- **Given**: 通知時刻一致ユーザー（JST 09:00 設定, UTC 00:00）と不一致ユーザー（JST 15:00 設定, UTC 00:00）が混在
- **When**: `process_notifications(current_time=UTC 00:00)` を実行
- **Then**: 時刻一致ユーザーのみに通知が送信され、不一致ユーザーは `skipped` カウントされる

- **参照したEARS要件**: EDGE-V2-102
- **参照した設計文書**: dataflow.md セクション4

---

## 5. EARS要件・設計文書との対応関係

### 参照したユーザストーリー

- 暗記カード学習者として、設定した時刻に通知を受け取りたい（タイムゾーン考慮）

### 参照した機能要件

| 要件ID | 内容 | 信頼性 |
|--------|------|--------|
| REQ-V2-041 | 通知送信前にユーザーのタイムゾーンを考慮したローカル時刻を算出する | 🔵 |
| REQ-V2-042 | ユーザー設定の notification_time とローカル時刻が一致する場合のみ通知を送信する | 🔵 |

### 参照した条件付き要件

| 要件ID | 内容 | 信頼性 |
|--------|------|--------|
| REQ-V2-111 | ユーザーのローカル時刻が notification_time と一致しない場合、通知をスキップする | 🔵 |
| REQ-V2-112 | ユーザーにタイムゾーン設定がない場合、Asia/Tokyo をデフォルトとして使用する | 🟡 |

### 参照した非機能要件

| 要件ID | 内容 | 信頼性 |
|--------|------|--------|
| NFR-V2-301 | 通知送信は notification_time ±5分の精度で実行される | 🟡 |

### 参照したEdgeケース

| 要件ID | 内容 | 信頼性 |
|--------|------|--------|
| EDGE-V2-102 | notification_time が日付境界（23:55 等）でタイムゾーン変換後に翌日になる場合の正確な判定 | 🟡 |

### 参照した設計文書

- **アーキテクチャ**: architecture.md セクション2.3「通知時刻/タイムゾーン判定 (H-03)」
- **データフロー**: dataflow.md セクション4「通知送信フロー（H-03: 時刻判定追加）」
- **API仕様**: api-endpoints.md「PUT /users/me/settings（変更）」
- **データベース**: architecture.md「DB スキーマ変更」- users テーブル timezone 属性追加

### 参照した実装ファイル

| ファイル | 確認内容 |
|---------|---------|
| `backend/src/services/notification_service.py` | 既存の process_notifications 実装（should_notify 未実装を確認） |
| `backend/src/models/user.py` | User モデル（settings 辞書に timezone/notification_time、UserSettingsRequest に timezone バリデーション済み） |
| `backend/src/services/user_service.py` | update_settings（timezone パラメータ処理 **実装済み**） |
| `backend/src/api/handler.py` | update_user_settings（timezone パラメータ処理 **実装済み**） |

---

## 6. 実装スコープの整理

### 6.1 新規実装が必要なもの 🔵

| 対象 | ファイル | 内容 |
|------|---------|------|
| `should_notify` メソッド | `backend/src/services/notification_service.py` | タイムゾーン変換 + ±5分精度の時刻一致判定 |
| `process_notifications` 修正 | `backend/src/services/notification_service.py` | `should_notify()` 呼び出しの追加 |
| 単体テスト | `backend/tests/unit/test_notification_timezone.py` | should_notify + process_notifications テスト |

### 6.2 既に実装済みのもの（追加実装不要） 🔵

| 対象 | ファイル | 確認結果 |
|------|---------|---------|
| User モデルの settings.timezone | `backend/src/models/user.py` | デフォルト値 `"Asia/Tokyo"` で実装済み |
| UserSettingsRequest の timezone バリデーション | `backend/src/models/user.py` | IANA フォーマットバリデーション実装済み |
| UserResponse の timezone フィールド | `backend/src/models/user.py` | `settings.get("timezone", "Asia/Tokyo")` で実装済み |
| UserService.update_settings の timezone 処理 | `backend/src/services/user_service.py` | DynamoDB の `settings.timezone` 更新実装済み |
| ハンドラーの timezone パラメータ処理 | `backend/src/api/handler.py` | `request.timezone` を `update_settings()` に渡す処理が実装済み |

---

## 7. should_notify アルゴリズム仕様 🔵

**信頼性**: 🔵 *architecture.md セクション2.3 の設計コードより*

### 7.1 アルゴリズム

```
1. user.settings から timezone を取得（未設定時は 'Asia/Tokyo'）
2. ZoneInfo(tz_name) でタイムゾーンオブジェクトを生成
   - 無効なタイムゾーン名の場合は Asia/Tokyo にフォールバック
3. current_utc.astimezone(user_tz) でユーザーのローカル時刻に変換
4. user.settings から notification_time を取得（未設定時は '09:00'）
5. notification_time を HH:MM パースして分単位の合計値を計算
6. ローカル時刻の HH:MM から分単位の合計値を計算
7. 差分の絶対値を計算
8. 差分が 720 (12時間) を超える場合、日付境界をまたぐケースとして 1440 - diff に補正
9. 差分が 5 以下なら True、それ以外は False を返す
```

### 7.2 ±5分判定の根拠 🟡

**信頼性**: 🟡 *NFR-V2-301: EventBridge の実行精度から推測*

- EventBridge の cron は 5分間隔で実行される（`rate(5 minutes)` 相当）
- ±5分のウィンドウにより、各 cron 実行で正しいユーザーに通知が送信される
- 例: notification_time=09:00 の場合、08:55〜09:05 の間に起動された cron で通知される

### 7.3 日付境界処理の根拠 🟡

**信頼性**: 🟡 *EDGE-V2-102 から推測*

- notification_time='23:58' でローカル時刻が 00:01 の場合、単純な差分は 1437分
- 720分（12時間）を超えるため、反対方向の差分として 1440 - 1437 = 3分と判定
- この処理により日付境界をまたぐケースが正しく判定される

---

## 信頼性レベルサマリー

### 項目別信頼性

| カテゴリ | 🔵 青 | 🟡 黄 | 🔴 赤 | 合計 |
|---------|-------|-------|-------|------|
| 機能概要 | 4 | 0 | 0 | 4 |
| 入出力仕様 | 5 | 0 | 0 | 5 |
| 制約条件 | 5 | 1 | 0 | 6 |
| 使用例・エッジケース | 7 | 3 | 0 | 10 |
| アルゴリズム仕様 | 1 | 2 | 0 | 3 |

### 全体評価

- **総項目数**: 28項目
- 🔵 **青信号**: 22項目 (79%)
- 🟡 **黄信号**: 6項目 (21%)
- 🔴 **赤信号**: 0項目 (0%)

**品質評価**: ✅ 高品質

**黄信号の項目**:
1. ±5分判定の精度根拠（EventBridge 実行間隔からの推測）
2. デフォルトタイムゾーン Asia/Tokyo（日本向けサービスとして妥当な推測）
3. 日付境界の処理方法（タイムゾーン変換の境界ケースからの推測）
4. タイムゾーン未設定のデフォルト動作
5. notification_time 未設定のデフォルト動作
6. 無効なタイムゾーン名のフォールバック動作

**特記事項**: User モデル、UserSettingsRequest、UserService.update_settings、ハンドラーの timezone 処理は全て既に実装済みであることをコード分析で確認した。新規実装は `should_notify()` メソッドと `process_notifications()` への統合のみ。
