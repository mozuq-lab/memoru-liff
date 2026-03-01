# Code Review: feature/day-boundary-spec

**レビュー日**: 2026-03-01
**レビュアー**: Claude Opus 4.6 + OpenAI Codex (MCP)
**ブランチ**: `feature/day-boundary-spec`
**ベースブランチ**: `main`
**コミット数**: 6件
**変更ファイル数**: 28件 (+1,974 / -9)

---

## 概要

復習カードの `next_review_at` を書き込み時にユーザーの日付境界時刻に正規化する機能。ユーザーごとに `day_start_hour` を設定可能にし、SRS の `next_review_at` をその時刻に正規化することで、ユーザーの生活リズムに合った復習カード表示を実現する。

### 変更内容サマリー

| コミット | 内容 |
|---------|------|
| `9d6b88c` | 要件定義・設計・タスク分割ドキュメントの追加 |
| `6c05b92` | TASK-0102: SRS 正規化関数 `calculate_next_review_boundary()` の実装 |
| `6a62e85` | TASK-0103: ユーザー設定モデルに `day_start_hour` 追加 |
| `a4472bf` | TASK-0104: レビューフロー正規化統合 |
| `481ae2f` | TASK-0105: カード interval 更新の正規化 |
| `a23cbd7` | TASK-0106: フロントエンド設定 UI |

---

## 総合評価

**設計品質**: 良好
- `calculate_sm2()` を変更せず、別関数 `calculate_next_review_boundary()` として正規化を分離した設計は適切
- 書き込み時正規化方式の採用により、クエリロジック・GSI 構成を変更不要にした判断は妥当
- 既存パターン（settings dict, UserService）の踏襲により一貫性を維持

**テスト品質**: 概ね良好（一部改善必要）
- 正規化関数のユニットテストは境界前/後、interval>1、カスタム day_start_hour を網羅
- 統合テスト（DynamoDB 保存検証）も含む
- ただし、弱いアサーションやエッジケースの不足あり

**コード品質**: 概ね良好（致命的バグ1件あり）
- 後方互換性を維持するデフォルト値設計
- 関心の分離が適切

---

## 指摘事項

### 1. [Critical / P0] DynamoDB Decimal 型による `TypeError` — このブランチで修正必須

**発見者**: Codex (Claude 追認)

**問題**: DynamoDB は Number 型を Python の `Decimal` として返す。`User.from_dynamodb_item()` (user.py:146) で `settings` dict をそのまま受け取るため、`user.settings.get("day_start_hour", 4)` は実運用では `Decimal(4)` を返す。

この `Decimal` 値が `calculate_next_review_boundary()` → `datetime(..., day_start_hour, ...)` (srs.py:116-124) に渡されると、`datetime()` コンストラクタは `__index__` プロトコルを要求するため `TypeError` が発生する。

**影響箇所**:
- `backend/src/models/user.py:146` — `from_dynamodb_item` が settings を型変換せずに返す
- `backend/src/api/handlers/review_handler.py:82` — `settings.get("day_start_hour", 4)` → Decimal
- `backend/src/api/handlers/cards_handler.py:166` — 同上
- `backend/src/services/srs.py:116-124` — `datetime()` に Decimal が渡され TypeError

**再現条件**: DynamoDB に `day_start_hour` が保存されている既存ユーザーがレビューを送信した場合。moto テストでは Python の int が返るため、テストでは再現しない。

**推奨修正**:

```python
# srs.py: calculate_next_review_boundary 入口で型正規化
def calculate_next_review_boundary(
    interval: int,
    user_timezone: str = "Asia/Tokyo",
    day_start_hour: int = 4,
) -> datetime:
    day_start_hour = int(day_start_hour)  # DynamoDB Decimal 対策
    if not 0 <= day_start_hour <= 23:
        raise ValueError(f"day_start_hour must be 0-23, got {day_start_hour}")
    ...
```

または、`User.from_dynamodb_item()` で settings 内の数値を `int` に変換する。

---

### 2. [High / P1] 非実在 timezone による `ZoneInfoNotFoundError` — このブランチで防御実装推奨

**発見者**: Codex (Claude 追認)

**問題**: `UserSettingsRequest.validate_timezone()` (user.py:40-58) は正規表現 `^[A-Za-z_]+/[A-Za-z_]+$` でのみ検証しており、`Foo/Bar` のような非実在 IANA タイムゾーンを通す。保存後に `calculate_next_review_boundary()` の `ZoneInfo(user_timezone)` (srs.py:105) で `ZoneInfoNotFoundError` が発生し、500 エラーとなる。

**補足**: このバリデーションは今回のブランチで導入されたものではなく既存問題だが、今回 `ZoneInfo` を使用するようになったことでリスクが顕在化した。

**推奨修正**:

```python
# user.py: validate_timezone で ZoneInfo 検証を追加
@field_validator("timezone")
@classmethod
def validate_timezone(cls, v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    try:
        ZoneInfo(v)
    except (ZoneInfoNotFoundError, KeyError):
        raise ValueError(f"Invalid timezone: {v}")
    return v
```

加えて、`calculate_next_review_boundary` 内で `ZoneInfo` 失敗時にデフォルト `Asia/Tokyo` へフォールバックする防御処理も検討。

---

### 3. [Medium / P2] `due_date` が UTC 日付のため day-boundary 表示と不整合 — 後続タスク

**発見者**: Codex (Claude 追認)

**問題**: `review_service.py:171` で `due_date = result.next_review_at.date().isoformat()` が UTC 基準の日付を返す。正規化された `next_review_at` が例えば `2024-06-15T19:00:00+00:00`（= JST 2024-06-16 04:00）の場合、`due_date` は `"2024-06-15"` となり、ユーザーの認識する日付 `"2024-06-16"` と不整合が生じる。

同様の問題は `review_service.py:462`（`get_due_cards` 内の `due_date` 生成）にも存在する。

**影響**: フロントエンドで「次の復習日」が1日ずれて表示される可能性がある。

**推奨対応**: 後続タスクとして、`due_date` をユーザーのローカル日付基準で生成するか、`next_review_at` の ISO 文字列をそのまま返してフロントエンドでローカル日付表示に統一するかの API 契約を整理する。

---

### 4. [Low / P2] テストの弱いアサーション — このブランチで修正推奨

**発見者**: Codex (Claude 追認)

**問題**: `test_review_service.py:477` のアサーション:

```python
assert actual_due_date == expected.date().isoformat() or actual_due_date == "2024-06-16"
```

2つの異なる値を許容しており、仕様逸脱が検出できない。

**推奨修正**: 期待値を1つに固定する。`due_date` が UTC 基準の仕様なら UTC 日付のみ、ローカル基準なら指摘 #3 の修正と合わせて対応。

---

### 5. [Low / P3] DST 遷移時のエッジケース — 後続タスク

**発見者**: Claude

**問題**: `srs.py:116-124` で `datetime(..., day_start_hour, 0, 0, tzinfo=user_tz)` を構築する際、DST ギャップ時間帯（例: `US/Eastern` の春の 2:00 AM）に `day_start_hour` が設定されていると、fold/gap 問題が発生する可能性がある。

**影響**: 現在のユーザーベースは `Asia/Tokyo`（DST なし）が主なため、現時点では理論的リスク。

**推奨対応**: 将来的に多タイムゾーン対応する場合は、`zoneinfo` の fold 処理や `dateutil` の利用を検討。

---

### 6. [Info / P3] ドキュメント間の不整合 — このブランチで整合推奨

**発見者**: Claude

**問題**: `interview-record.md` Q4 の回答では「0時〜6時（推奨）を選択。7つの選択肢。」とあるが、`requirements.md` REQ-003 では「0時〜23時（24個）、ドロップダウン形式」と記載されており、実装も 0-23 の 24 個。ヒアリング後に要件が変更されたと推測されるが、ヒアリング記録が更新されていない。

**推奨対応**: `interview-record.md` に追記するか、Q4 の回答を最新仕様に合わせて修正。

---

### 7. [Nit] `zoneinfo` のモジュールレベル import — 任意

**発見者**: Claude

**問題**: `srs.py:103` で `from zoneinfo import ZoneInfo` を関数内で import している。パフォーマンス上の問題はないが、Python の慣例ではモジュールレベルに配置するのが一般的。

---

### 8. [Nit] `from_dynamodb_item` のデフォルト settings — 任意

**発見者**: Claude

**問題**: `user.py:146` の `from_dynamodb_item` メソッドのフォールバック:

```python
settings=item.get("settings", {"notification_time": "09:00", "timezone": "Asia/Tokyo"})
```

`day_start_hour` が含まれていない。`settings.get("day_start_hour", 4)` で回収されるため実害はないが、他のデフォルト設定との一貫性のため追加が望ましい。

---

## 良い点

1. **関心の分離**: `calculate_sm2()` を変更せず、正規化を別関数に分離した設計は適切。アルゴリズムの純粋性が維持されている。
2. **後方互換性**: デフォルト引数 (`user_timezone="Asia/Tokyo"`, `day_start_hour=4`) による互換性維持が適切。
3. **既存パターンの踏襲**: `notification_time` / `timezone` と同じパターンで `day_start_hour` を実装しており、コードベースの一貫性が保たれている。
4. **テストカバレッジ**: 正規化関数に対して境界前/後、カスタム設定、異なるタイムゾーン、DynamoDB 保存検証まで網羅。
5. **ドキュメンテーション**: 要件定義・設計文書・データフロー図・タスクファイルが整備されている。

---

## 対応優先度まとめ

### このブランチで修正すべき（マージ前）

| # | 指摘 | 推定工数 |
|---|------|---------|
| 1 | DynamoDB Decimal 型変換（P0 Critical） | 15分 |
| 2 | timezone 実在検証の防御実装（P1 High） | 30分 |
| 4 | テスト `assert A or B` の修正（P2 Low） | 15分 |
| 6 | ドキュメント不整合の解消（P3 Info） | 10分 |

### 後続タスクとして対応

| # | 指摘 | 備考 |
|---|------|------|
| 3 | `due_date` UTC vs ローカル日付の整理 | API 契約の仕様合意が必要 |
| 5 | DST 遷移時の厳密処理 | 多タイムゾーン対応時 |
