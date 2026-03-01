# day-boundary データフロー図

**作成日**: 2026-03-01
**関連アーキテクチャ**: [architecture.md](architecture.md)
**関連要件定義**: [requirements.md](../../spec/day-boundary/requirements.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: EARS要件定義書・既存実装・ユーザヒアリングを参考にした確実なフロー
- 🟡 **黄信号**: 既存実装・設計パターンから妥当な推測によるフロー

---

## レビュー送信フロー（変更後） 🔵

**関連要件**: REQ-001, REQ-403

```
ユーザー → フロントエンド → API Gateway → review_handler
                                              │
                                              ├─ 1. get_user_id_from_context()
                                              ├─ 2. user_service.get_or_create_user(user_id)  ← 追加
                                              │     └─ DynamoDB GetItem (UsersTable)
                                              │        → settings.timezone, settings.day_start_hour
                                              │
                                              └─ 3. review_service.submit_review(
                                                    user_id, card_id, grade,
                                                    user_timezone, day_start_hour)  ← パラメータ追加
                                                    │
                                                    ├─ 3a. card_service.get_card(user_id, card_id)
                                                    │
                                                    ├─ 3b. calculate_sm2(grade, repetitions, ease_factor, interval)
                                                    │      → SM2Result { interval, next_review_at, ... }
                                                    │
                                                    ├─ 3c. calculate_next_review_boundary(  ← 新規
                                                    │        result.interval,
                                                    │        user_timezone,
                                                    │        day_start_hour)
                                                    │      → normalized_next_review_at
                                                    │
                                                    ├─ 3d. _update_card_review_data(
                                                    │        next_review_at=normalized_next_review_at)
                                                    │      → DynamoDB UpdateItem (CardsTable)
                                                    │
                                                    └─ 3e. _record_review(...)
                                                           → DynamoDB PutItem (ReviewsTable)
```

**変更点**:
- ステップ2: ユーザー設定の取得（追加）
- ステップ3c: 正規化関数の呼び出し（追加）
- ステップ3d: 正規化済み `next_review_at` の保存

## 正規化ロジック詳細 🔵

**関連要件**: REQ-001

```
入力: interval=1, timezone="Asia/Tokyo", day_start_hour=4

ケースA: 10:00 JST (01:00 UTC) に復習
  local_now = 2026-03-01 10:00 JST
  10 >= 4 → effective_date = 2026-03-01
  target_date = 2026-03-01 + 1 day = 2026-03-02
  boundary = 2026-03-02 04:00 JST = 2026-03-01 19:00 UTC
  → next_review_at = 2026-03-01T19:00:00+00:00

ケースB: 01:00 JST (前日 16:00 UTC) に復習（境界前）
  local_now = 2026-03-01 01:00 JST
  1 < 4 → effective_date = 2026-02-28 (前日扱い)
  target_date = 2026-02-28 + 1 day = 2026-03-01
  boundary = 2026-03-01 04:00 JST = 2026-02-28 19:00 UTC
  → next_review_at = 2026-02-28T19:00:00+00:00

ケースC: interval=6, 14:00 JST に復習
  local_now = 2026-03-01 14:00 JST
  14 >= 4 → effective_date = 2026-03-01
  target_date = 2026-03-01 + 6 days = 2026-03-07
  boundary = 2026-03-07 04:00 JST = 2026-03-06 19:00 UTC
  → next_review_at = 2026-03-06T19:00:00+00:00
```

## クエリフロー（変更なし） 🔵

**関連要件**: REQ-005

```
ユーザーがアプリを開く (2026-03-02 08:00 JST = 2026-03-01 23:00 UTC)
  │
  └─ GET /cards/due → review_service.get_due_cards()
       │
       └─ card_service.get_due_cards(before=datetime.now(UTC))
            │
            └─ DynamoDB Query:
                 GSI: user_id-due-index
                 KeyCondition: user_id = :user_id AND next_review_at <= :before
                 :before = "2026-03-01T23:00:00+00:00"

                 カードA: next_review_at = "2026-03-01T19:00:00+00:00" ← 19:00 <= 23:00 ✅ 表示
                 カードB: next_review_at = "2026-03-02T19:00:00+00:00" ← 翌日分 ❌ 非表示
```

**ポイント**: 正規化により同じ日の復習カードは同じ境界時刻を持つため、境界時刻を過ぎれば全て表示される。

## カード interval 更新フロー 🟡

**関連要件**: REQ-004

```
ユーザー → フロントエンド → API Gateway → cards_handler.update_card()
                                              │
                                              ├─ 1. interval が指定されているか確認
                                              │
                                              ├─ 2. (interval指定時のみ)
                                              │     user_service.get_or_create_user(user_id)
                                              │     → settings.timezone, settings.day_start_hour
                                              │
                                              └─ 3. card_service.update_card(
                                                    ..., interval=N,
                                                    user_timezone, day_start_hour)
                                                    │
                                                    └─ calculate_next_review_boundary(interval, tz, hour)
                                                       → normalized next_review_at
                                                       → DynamoDB UpdateItem
```

## 設定変更フロー 🔵

**関連要件**: REQ-002, REQ-003

```
ユーザー → SettingsPage.tsx
              │
              ├─ useEffect: fetchUser() → GET /users/me
              │   → user.day_start_hour を selectedDayStartHour にセット
              │
              ├─ onChange: selectedDayStartHour 更新
              │   → hasChanges = true
              │
              └─ handleSave: PUT /users/me/settings
                    body: { notification_time, day_start_hour }
                    │
                    └─ user_handler → user_service.update_settings(
                          ..., day_start_hour=N)
                          │
                          └─ DynamoDB UpdateItem:
                               SET settings.day_start_hour = :day_start_hour
```

## 関連文書

- **アーキテクチャ**: [architecture.md](architecture.md)
- **要件定義**: [requirements.md](../../spec/day-boundary/requirements.md)

## 信頼性レベルサマリー

- 🔵 青信号: 5件 (83%)
- 🟡 黄信号: 1件 (17%)
- 🔴 赤信号: 0件 (0%)

**品質評価**: 高品質
