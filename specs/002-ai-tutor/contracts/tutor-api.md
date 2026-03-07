# API Contract: AI Tutor

**Base Path**: `/api/tutor`
**Authentication**: Bearer JWT (既存の認証フロー)

## Endpoints

### POST /api/tutor/sessions

セッションを開始する。既存のアクティブセッションがある場合は自動終了。

**Request Body**:
```json
{
  "deck_id": "deck_abc123",
  "mode": "free_talk"
}
```

**Response** `201 Created`:
```json
{
  "session_id": "tutor_550e8400-e29b-41d4-a716-446655440000",
  "deck_id": "deck_abc123",
  "mode": "free_talk",
  "status": "active",
  "messages": [
    {
      "role": "assistant",
      "content": "こんにちは！「英単語 基礎」デッキについて一緒に学びましょう。何か質問はありますか？",
      "related_cards": [],
      "timestamp": "2026-03-07T10:00:00Z"
    }
  ],
  "message_count": 0,
  "created_at": "2026-03-07T10:00:00Z",
  "updated_at": "2026-03-07T10:00:00Z",
  "ended_at": null
}
```

**Error Responses**:
- `400 Bad Request`: 無効な mode、空デッキ
- `404 Not Found`: デッキが存在しない
- `422 Unprocessable Entity`: レビュー履歴不足 (weak_point mode)

---

### POST /api/tutor/sessions/{session_id}/messages

セッションにメッセージを送信し、AI の応答を取得する。

**Path Parameters**: `session_id` (string)

**Request Body**:
```json
{
  "content": "このカードの意味を教えてください"
}
```

**Response** `200 OK`:
```json
{
  "message": {
    "role": "assistant",
    "content": "この概念は...",
    "related_cards": ["card_abc123", "card_def456"],
    "timestamp": "2026-03-07T10:00:25Z"
  },
  "session_id": "tutor_550e8400-e29b-41d4-a716-446655440000",
  "message_count": 1,
  "is_limit_reached": false
}
```

**Error Responses**:
- `400 Bad Request`: 空メッセージ
- `404 Not Found`: セッションが存在しない
- `409 Conflict`: セッションが終了済み / タイムアウト済み
- `429 Too Many Requests`: メッセージ上限（20 ラウンドトリップ）到達
- `504 Gateway Timeout`: AI サービスタイムアウト

---

### DELETE /api/tutor/sessions/{session_id}

セッションを明示的に終了する。

**Path Parameters**: `session_id` (string)

**Response** `200 OK`:
```json
{
  "session_id": "tutor_550e8400-e29b-41d4-a716-446655440000",
  "status": "ended",
  "ended_at": "2026-03-07T10:30:00Z"
}
```

**Error Responses**:
- `404 Not Found`: セッションが存在しない
- `409 Conflict`: セッションが既に終了済み

---

### GET /api/tutor/sessions

ユーザーのセッション一覧を取得する（保持期間内の全セッション）。

**Query Parameters**:
- `status` (optional): `active` / `ended` / `timed_out`（フィルタ）
- `deck_id` (optional): 特定デッキのセッションのみ

**Response** `200 OK`:
```json
{
  "sessions": [
    {
      "session_id": "tutor_550e8400-e29b-41d4-a716-446655440000",
      "deck_id": "deck_abc123",
      "mode": "free_talk",
      "status": "ended",
      "messages": [],
      "message_count": 5,
      "created_at": "2026-03-07T10:00:00Z",
      "updated_at": "2026-03-07T10:25:00Z",
      "ended_at": "2026-03-07T10:30:00Z"
    }
  ]
}
```

注: 一覧取得時の `messages` は空配列。詳細取得で会話履歴を取得する。

---

### GET /api/tutor/sessions/{session_id}

セッション詳細（会話履歴含む）を取得する。

**Path Parameters**: `session_id` (string)

**Response** `200 OK`:
```json
{
  "session_id": "tutor_550e8400-e29b-41d4-a716-446655440000",
  "deck_id": "deck_abc123",
  "mode": "free_talk",
  "status": "ended",
  "messages": [
    {
      "role": "assistant",
      "content": "こんにちは！...",
      "related_cards": [],
      "timestamp": "2026-03-07T10:00:00Z"
    },
    {
      "role": "user",
      "content": "...",
      "related_cards": [],
      "timestamp": "2026-03-07T10:00:15Z"
    }
  ],
  "message_count": 5,
  "created_at": "2026-03-07T10:00:00Z",
  "updated_at": "2026-03-07T10:25:00Z",
  "ended_at": "2026-03-07T10:30:00Z"
}
```

**Error Responses**:
- `404 Not Found`: セッションが存在しない

## 共通エラーレスポンス形式

```json
{
  "statusCode": 400,
  "message": "エラーメッセージ"
}
```

## 認証

すべてのエンドポイントは既存の JWT 認証を使用。`user_id` はトークンから抽出。
未認証リクエストは `401 Unauthorized` を返す。
