# Backend コードレビュー 統合レポート

- **日付**: 2026-03-08
- **対象**: `backend/src/` 全体（API層、Models、Services、Utils、Webhook、Jobs、Tests）
- **レビュー方式**: Agent Teams による4並列レビュー

## 全体評価

全体的に**高品質なコードベース**。Lambda Powertools の活用、Pydantic v2 によるバリデーション、SM-2 アルゴリズムの正確な実装、TDD プロセスの一貫した適用が確認できた。以下、優先度別に指摘事項を統合する。

---

## 強み

- **Router パターンの適切な活用**: ドメイン別ハンドラー分割で可読性・保守性が高い
- **SSRF 対策**: `url_validator.py` で DNS 解決ベースの多層防御を実装
- **dev フォールバックの安全設計**: JWT の dev 用フォールバックが二重条件でのみ有効
- **エラー階層の明確化**: `AIServiceError` サブクラスと HTTP ステータスの一元マッピング
- **Sentinel パターンの一貫した活用**: `_UNSET` で「未指定」と「明示的 null」を区別
- **トランザクション設計**: カード作成と `card_count` のアトミック処理
- **SM-2 アルゴリズム**: 仕様に忠実な実装、タイムゾーン・日付境界の考慮
- **TDD プロセス**: 80本超のテストファイル、品質ゲートテストの組み込み
- **セキュリティテスト**: タイミング攻撃対策の `hmac.compare_digest` 呼び出し確認

---

## Critical（本番運用に影響するリスク）

### C-1: base64 エンコードボディの未処理

**対象**: `webhook/line_handler.py` L493

API Gateway HTTP API では `isBase64Encoded: true` かつ body が base64 文字列として渡されることがある。現在のコードはその場合を考慮しておらず、署名検証が全て失敗する。

```python
# 現状
body = event.get("body", "")

# 修正案
body_raw = event.get("body", "") or ""
is_b64 = event.get("isBase64Encoded", False)
if is_b64:
    import base64 as _b64
    body = _b64.b64decode(body_raw).decode("utf-8")
else:
    body = body_raw
```

### C-2: `save_url_cards` の URL バリデーション欠如（SSRF リスク）

**対象**: `webhook/line_handler.py` L458-L464

`postback` データの `url` パラメータが `validate_url()` を通らずに `UrlContentService.fetch_content()` に渡される。`url_validator.py` で丁寧に実装した SSRF 対策が活用されていない。

```python
# 修正案
from utils.url_validator import validate_url, UrlValidationError

url = unquote(data.get("url", ""))
try:
    url = validate_url(url)
except UrlValidationError as e:
    logger.warning(f"Invalid URL in save_url_cards: {e}")
    line_service.reply_message(event.reply_token, [create_error_message()])
    return
```

### C-3: `limit` パラメータの型変換で 500 エラー

**対象**: `api/handlers/cards_handler.py` L36, `review_handler.py`

非数値文字列（`"abc"` 等）が渡されると `int()` が `ValueError` を送出し 500 エラーになる。`stats_handler.py` では `try/except (ValueError, TypeError)` で対策済みだが不統一。

```python
# 修正案
try:
    limit = min(int(params.get("limit", 50)), 100)
except (ValueError, TypeError):
    return Response(status_code=400, ...)
```

### C-4: `datetime.utcnow()` の使用

**対象**: `models/card.py:118`, `models/user.py:95`

Python 3.12 で非推奨。`deck.py` では既に `datetime.now(timezone.utc)` を使用しており不統一。timezone-naive と timezone-aware の混在で `TypeError` 発生の恐れあり。

```python
# 修正案
created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

### C-5: `delete_card` のレビュー削除がトランザクション外

**対象**: `services/card_service.py` L355-451

レビューのバッチ削除はトランザクション外で先行実行。レビュー削除後・カード削除前にクラッシュするとデータ不整合が発生する。DynamoDB Streams や定期クリーンアップ Job による自己修復手段の検討を推奨。

### C-6: `list_cards` での重複 URL 検出が最初の50件のみ

**対象**: `api/handlers/ai_handler.py` L141

`list_cards` のデフォルト `limit=50` でページネーション未対応。カードが多いユーザーでは重複検出が不完全。`references` フィールドの GSI または専用 existence-check API の導入を推奨。

---

## Major（コード品質・一貫性に影響）

### M-1: `handle_url_card_generation` でも URL バリデーション欠如

**対象**: `webhook/line_handler.py` L185-293

C-2 と同パターン。`detect_url_in_message` は正規表現マッチのみで SSRF 防止検証なし。

### M-2: Secrets Manager 取得失敗のサイレントエラー

**対象**: `services/line_service.py` L129

```python
except ClientError:
    pass  # 完全にサイレント
```

権限エラーやシークレット未存在がログに残らず診断困難。`logger.error()` の追加を推奨。

### M-3: `notification_time` パース時の例外処理なし

**対象**: `services/notification_service.py` L79

```python
notif_hour, notif_min = map(int, notification_time.split(":"))
```

不正フォーマットで `ValueError` が発生し、該当ユーザーの処理全体がスキップされる。try-except でフォールバック（デフォルト 09:00）すべき。

### M-4: ジョブの冪等性不足

**対象**: `jobs/due_push_handler.py`

EventBridge Scheduler の at-least-once 保証により重複実行が発生しうる。`last_notified_date` は「今日」単位の粒度で、5分間隔実行でレースコンディションのリスクあり。DynamoDB の条件付き更新で対策を推奨。

### M-5: `ValidationError` シリアライズ方法が不統一

**対象**: API ハンドラー各所

3種類の方法が混在:

- `e.errors()`: `cards_handler.py`, `review_handler.py`, `tutor_handler.py`
- `str(e)`: `decks_handler.py`
- `json.loads(e.json())`: `ai_handler.py`, `handler.py`

`shared.py` にヘルパー関数を追加して統一を推奨:

```python
def make_validation_error_response(e: ValidationError) -> Response:
    return Response(
        status_code=400,
        content_type=content_types.APPLICATION_JSON,
        body=json.dumps({"error": "Invalid request", "details": e.errors()}),
    )
```

### M-6: f-string ログと構造化ログの混在

**対象**: API ハンドラー各所

Lambda Powertools の `Logger` は `extra={}` による構造化ログをサポートしているが、多くの箇所で f-string が使われており CloudWatch Logs Insights でフィールドクエリ不可。

```python
# 現状
logger.info(f"Listing cards for user_id: {user_id}")

# 推奨
logger.info("Listing cards", extra={"user_id": user_id})
```

### M-7: 集計ロジックの完全重複

**対象**: `services/review_service.py` L522-618, `services/stats_service.py` L108-181

以下の処理が重複:

- 全カード・全レビューの DynamoDB クエリ
- `tag_performance` の計算
- streak 計算

共通ロジックの集約または一方の廃止を推奨。

### M-8: `get_linked_users` が DynamoDB Scan を使用

**対象**: `services/user_service.py` L203-232

全テーブルスキャンでユーザー数に比例してコスト・遅延が増大。LINE 連携ユーザー用の GSI を設けて Query に変更を推奨。

### M-9: `UserSettingsResponse.settings` が非型付け `dict`

**対象**: `models/user.py` L65-69

クライアント側が構造を型から読み取れない。専用の `UserSettings` モデルを定義すべき。

### M-10: `mock_transact_write_items` の自前実装

**対象**: `tests/unit/test_card_service.py`

moto バグ回避の自前実装が DynamoDB の実際のトランザクション動作と乖離する可能性。統合テスト（DynamoDB Local）への移行を検討。

### M-11: SM-2 grade 1〜3 のテスト不足

**対象**: `tests/unit/test_review_service.py`

`submit_review` で grade 0, 4, 5 はテスト済みだが grade 1〜3 の中間値のイーズファクター変化量が未検証。SM-2 は grade 3 で非対称な挙動をする。

### M-12: `importlib.reload()` によるテスト間状態汚染リスク

**対象**: `tests/unit/test_notification_service.py`

`reload()` はモジュールのグローバル変数の参照を更新しないことがあり予期しない挙動の原因に。依存性注入またはモジュール変数の直接パッチに変更を推奨。

---

## Minor（品質・可読性）

| #    | 対象                          | 内容                                                                         |
| ---- | ----------------------------- | ---------------------------------------------------------------------------- |
| m-1 | `stats_handler.py` | エラーキーが `"message"` — 他は全て `"error"` |
| m-2 | `browser_profile_handler.py` | 手動バリデーション — 他は Pydantic 使用で不統一 |
| m-3 | `tutor_handler.py` | `TutorServiceError` の内部メッセージがクライアントに露出するリスク |
| m-4 | `models/review.py` | `field_validator("grade")` がデッドコード（`Field(ge=0, le=5)` と重複）|
| m-5 | `models/tutor.py` | `timestamp` / `created_at` 等が `str` 型 — 他モデルは `datetime` |
| m-6 | `review_service.py` | `_calculate_streak` が `date.today()` でタイムゾーン無視 |
| m-7 | `models/user.py` | デフォルト設定が2箇所（L93, L139）にハードコード |
| m-8 | テスト | `webhook/line_handler.py` のユニットテストが存在しない |
| m-9 | テスト | `test_review_service.py` で重複 import |
| m-10 | テスト | Sentinel パターンテストの過剰なインラインコメント |
| m-11 | `handler.py` | ステージパス補完の実装がフラジャイル |
| m-12 | `decks_handler.py` | `UpdateDeckRequest(**body)` の `noqa: F841` — 戻り値未使用 |
| m-13 | `line_handler.py` | HTTP→HTTPS 暗黙的正規化の設計上の問題 |
| m-14 | `line_handler.py` | セッション完了カウントが常に 1（不正確） |

---

## Suggestion（提案）

| #   | 内容                                                                                    |
| --- | --------------------------------------------------------------------------------------- |
| S-1 | `due_push_handler.py` に CloudWatch Metrics の埋め込みメトリクス（Powertools `Metrics`）を追加 |
| S-2 | `validate_url` の DNS 解決にタイムアウト設定またはキャッシュを検討 |
| S-3 | Webhook ハンドラーの署名検証失敗時の HTTP 400 レスポンス確認テストを追加 |
| S-4 | `to_dynamodb_item` / `from_dynamodb_item` の責務を Repository パターンに分離（長期的） |
| S-5 | テストの `dynamodb_tables` フィクスチャ名を意味のある名前にリネーム |
| S-6 | `freezegun` の導入で `datetime` パッチを簡潔化 |

---

## 推奨対応順序

1. **即時対応**: C-1（base64）、C-2/M-1（SSRF）— セキュリティに直結、修正は数行
2. **早期対応**: C-3（limit バリデーション）、C-4（utcnow 統一）、M-2（サイレントエラー）
3. **計画的対応**: M-5/M-6（横断リファクタリング）、M-7（ロジック重複解消）、M-8（Scan → GSI）
4. **テスト強化**: M-10/M-11（テスト信頼性）、m-8（webhook テスト追加）
