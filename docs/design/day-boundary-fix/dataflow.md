# day-boundary-fix データフロー図

**作成日**: 2026-03-01
**関連アーキテクチャ**: [architecture.md](architecture.md)
**関連要件定義**: [requirements.md](../../spec/day-boundary-fix/requirements.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: コードレビュー指摘・既存実装を参考にした確実なフロー
- 🟡 **黄信号**: 既存実装・設計パターンから妥当な推測によるフロー

---

## 修正後のレビュー送信フロー 🔵

**関連要件**: REQ-001, REQ-003

既存フローのステップ 3c `calculate_next_review_boundary` 内部に防御処理が追加される。フロー全体の構造は変更なし。

```
review_handler.submit_review()
  │
  ├─ user.settings.get("day_start_hour", 4)
  │   └─ ※ DynamoDB から取得した場合 Decimal(4) が返る可能性あり
  │
  └─ review_service.submit_review(
        ..., user_timezone, day_start_hour)
        │
        └─ calculate_next_review_boundary(interval, user_timezone, day_start_hour)
             │
             ├─ [Step 1] int(interval), int(day_start_hour)  ← REQ-001: Decimal → int 変換
             │   └─ 0 <= day_start_hour <= 23 チェック → 範囲外なら ValueError
             │
             ├─ [Step 2] ZoneInfo(user_timezone)  ← REQ-003: TZ フォールバック
             │   ├─ 成功 → 指定 TZ を使用
             │   └─ ZoneInfoNotFoundError/KeyError
             │       ├─ Logger.warning("Invalid timezone '...', falling back to Asia/Tokyo")
             │       └─ ZoneInfo("Asia/Tokyo") をフォールバックとして使用
             │
             └─ [Step 3] 正規化ロジック（変更なし）
                 ├─ effective_date 計算
                 ├─ target_date = effective_date + interval
                 ├─ boundary = datetime(target_date, day_start_hour, tzinfo=user_tz)
                 └─ return boundary.astimezone(UTC)
```

**変更点**:
- Step 1: `int()` による型変換と範囲チェック追加
- Step 2: `try/except` による TZ フォールバック追加
- Step 3: 変更なし

## 設定更新時のバリデーションフロー 🔵

**関連要件**: REQ-002

```
ユーザー → SettingsPage → PUT /users/me/settings
  │
  └─ user_handler.update_settings()
       │
       └─ UserSettingsRequest(timezone="Foo/Bar")
            │
            └─ validate_timezone("Foo/Bar")
                 │
                 ├─ ZoneInfo("Foo/Bar")  ← REQ-002: 実在検証
                 │   └─ ZoneInfoNotFoundError 発生
                 │
                 └─ raise ValueError("Invalid timezone: Foo/Bar")
                      └─ Pydantic ValidationError → 400 Bad Request
                           {
                             "error": "Invalid request",
                             "details": [{"msg": "Invalid timezone: Foo/Bar"}]
                           }
```

**ポイント**: 設定更新時に不正 TZ を拒否することで、後続のレビュー送信時の 500 エラーを予防。

## 多層防御の全体像 🔵

**関連要件**: REQ-002, REQ-003

```
Layer 1: 設定更新時バリデーション（REQ-002）
┌─────────────────────────────────────────────────┐
│  UserSettingsRequest.validate_timezone()          │
│  ZoneInfo(v) → 非実在なら 400 返却               │
│  → 正常な TZ のみ DynamoDB に保存される            │
└─────────────────────────────────────────────────┘
         │
         │ ※ DB直接操作や旧データで不正値が混入する可能性
         ▼
Layer 2: 実行時フォールバック（REQ-003）
┌─────────────────────────────────────────────────┐
│  calculate_next_review_boundary()                │
│  try: ZoneInfo(user_timezone)                    │
│  except: → Asia/Tokyo にフォールバック + ログ出力  │
│  → 500 エラーを回避                               │
└─────────────────────────────────────────────────┘
         │
         │ ※ DynamoDB の Number → Decimal 変換
         ▼
Layer 3: 型変換（REQ-001）
┌─────────────────────────────────────────────────┐
│  calculate_next_review_boundary()                │
│  int(day_start_hour) → Decimal を int に変換     │
│  0 <= day_start_hour <= 23 → 範囲外なら ValueError│
│  → TypeError を回避                               │
└─────────────────────────────────────────────────┘
```

## テスト修正のカバレッジ 🔵

**関連要件**: REQ-004, REQ-103

```
修正前のテストカバレッジ:
┌─────────────────────────────────────────────────┐
│  test_srs.py:                                    │
│  ✅ 境界前/後の正規化                              │
│  ✅ interval > 1                                  │
│  ✅ デフォルトパラメータ                            │
│  ✅ カスタム day_start_hour                        │
│  ✅ 異なる TZ (UTC)                               │
│  ❌ Decimal 入力                                  │
│  ❌ 不正 TZ フォールバック                          │
├─────────────────────────────────────────────────┤
│  test_review_service.py:                         │
│  ⚠️ assert A or B（弱いアサーション）              │
├─────────────────────────────────────────────────┤
│  test_user_models.py:                            │
│  ❌ 非実在 TZ バリデーション                       │
└─────────────────────────────────────────────────┘

修正後のテストカバレッジ:
┌─────────────────────────────────────────────────┐
│  test_srs.py:                                    │
│  ✅ 境界前/後の正規化                              │
│  ✅ interval > 1                                  │
│  ✅ デフォルトパラメータ                            │
│  ✅ カスタム day_start_hour                        │
│  ✅ 異なる TZ (UTC)                               │
│  ✅ Decimal(4) 入力                        ← NEW │
│  ✅ Decimal 境界値 (0, 23)                  ← NEW │
│  ✅ 範囲外 Decimal (24, -1) で ValueError  ← NEW │
│  ✅ 不正 TZ フォールバック                   ← NEW │
│  ✅ フォールバック結果の正確性               ← NEW │
├─────────────────────────────────────────────────┤
│  test_review_service.py:                         │
│  ✅ 単一期待値のアサーション               ← FIXED│
├─────────────────────────────────────────────────┤
│  test_user_models.py:                            │
│  ✅ 非実在 TZ "Foo/Bar" 拒否              ← NEW │
│  ✅ 有効 TZ "Asia/Tokyo" 受け入れ          ← NEW │
└─────────────────────────────────────────────────┘
```

## 関連文書

- **アーキテクチャ**: [architecture.md](architecture.md)
- **要件定義**: [requirements.md](../../spec/day-boundary-fix/requirements.md)
- **コードレビュー結果**: [CODE_REVIEW_day-boundary.md](../../reviews/CODE_REVIEW_day-boundary.md)

## 信頼性レベルサマリー

- 🔵 青信号: 5件 (100%)
- 🟡 黄信号: 0件 (0%)
- 🔴 赤信号: 0件 (0%)

**品質評価**: ✅ 高品質
