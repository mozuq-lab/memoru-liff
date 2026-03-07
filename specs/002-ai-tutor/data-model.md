# Data Model: AI Tutor (Interactive Learning)

**Date**: 2026-03-07

## DynamoDB テーブル: TutorSessionsTable

既存の single-table design パターンに従い、新規テーブルを追加。

### テーブル定義

| 属性 | 型 | 説明 |
|------|------|------|
| **PK: user_id** | S | ユーザー ID |
| **SK: session_id** | S | セッション ID (`tutor_` prefix + UUID) |
| deck_id | S | 対象デッキ ID |
| mode | S | 学習モード: `free_talk` / `quiz` / `weak_point` |
| status | S | セッション状態: `active` / `ended` / `timed_out` |
| messages | L | 会話履歴（メッセージリスト） |
| message_count | N | 現在のラウンドトリップ数 |
| created_at | S | セッション作成日時 (ISO 8601) |
| updated_at | S | 最終更新日時 (ISO 8601) |
| ended_at | S | セッション終了日時 (ISO 8601, nullable) |
| ttl | N | DynamoDB TTL (セッション終了後 7 日間で自動削除) |

### GSI

| GSI 名 | PK | SK | 用途 |
|--------|------|------|------|
| user_id-status-index | user_id | status | アクティブセッションの検索、セッション一覧取得 |

### messages 属性の構造

```json
[
  {
    "role": "assistant",
    "content": "こんにちは！このデッキについて一緒に学びましょう。",
    "related_cards": [],
    "timestamp": "2026-03-07T10:00:00Z"
  },
  {
    "role": "user",
    "content": "このカードの意味を教えてください",
    "related_cards": [],
    "timestamp": "2026-03-07T10:00:15Z"
  },
  {
    "role": "assistant",
    "content": "この概念は...",
    "related_cards": ["card_abc123", "card_def456"],
    "timestamp": "2026-03-07T10:00:25Z"
  }
]
```

## Pydantic モデル

### TutorSession

```python
class TutorMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    related_cards: list[str] = []  # card_id のリスト
    timestamp: str

class TutorSessionResponse(BaseModel):
    session_id: str
    deck_id: str
    mode: Literal["free_talk", "quiz", "weak_point"]
    status: Literal["active", "ended", "timed_out"]
    messages: list[TutorMessage]
    message_count: int
    created_at: str
    updated_at: str
    ended_at: str | None = None

class StartSessionRequest(BaseModel):
    deck_id: str
    mode: Literal["free_talk", "quiz", "weak_point"]

class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)

class SendMessageResponse(BaseModel):
    message: TutorMessage  # AI の応答メッセージ
    session_id: str
    message_count: int
    is_limit_reached: bool  # 20 ラウンドトリップ到達フラグ

class SessionListResponse(BaseModel):
    sessions: list[TutorSessionResponse]
```

## 状態遷移

```
[新規作成] → active
active → ended      (ユーザーが明示的に終了 / 新規セッション開始による自動終了)
active → timed_out  (30 分間メッセージなし)
active → ended      (20 ラウンドトリップ上限到達)
ended/timed_out → [TTL 削除]  (7 日後に自動削除)
```

## 既存エンティティとの関連

```
User (1) ──── (0..1) TutorSession [active]
User (1) ──── (0..N) TutorSession [ended/timed_out]
Deck (1) ──── (0..N) TutorSession
TutorSession.messages[].related_cards ──── Card.card_id
```

## バリデーションルール

- `message_count` ≤ 20 (ラウンドトリップ上限)
- `content` の長さ: 1〜2000 文字
- 1 ユーザー 1 アクティブセッション制約（新規作成時に既存アクティブを自動終了）
- タイムアウト判定: `updated_at` + 30 分 < 現在時刻
- TTL 計算: `ended_at` + 7 日間（UNIX epoch 秒）
