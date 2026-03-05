# API Contract: URL からカード自動生成

**Branch**: `002-url-card-generation` | **Date**: 2026-03-05

## POST /cards/generate-from-url

URL から暗記カードを自動生成する。

### Request

**Headers**:
- `Authorization: Bearer <access_token>` (必須)
- `Content-Type: application/json`

**Body**:

```json
{
  "url": "https://example.com/article",
  "card_type": "qa",
  "target_count": 10,
  "difficulty": "medium",
  "language": "ja",
  "deck_id": "01HQXYZ..."
}
```

| Field | Type | Required | Default | Validation |
|-------|------|----------|---------|------------|
| url | string | Yes | - | https only, max 2048 chars, no internal IPs |
| card_type | string | No | "qa" | One of: "qa", "definition", "cloze" |
| target_count | integer | No | 10 | Range: 5-30 |
| difficulty | string | No | "medium" | One of: "easy", "medium", "hard" |
| language | string | No | "ja" | One of: "ja", "en" |
| deck_id | string | No | null | Valid ULID format |

### Response (200 OK)

```json
{
  "generated_cards": [
    {
      "front": "SPA とは何ですか？",
      "back": "Single Page Application の略で、ページ遷移なしに動的にコンテンツを更新する Web アプリケーションの設計パターン。",
      "suggested_tags": ["AI生成", "URL生成", "Web開発"]
    }
  ],
  "generation_info": {
    "model_used": "strands_bedrock",
    "processing_time_ms": 15200,
    "fetch_method": "browser",
    "chunk_count": 3,
    "content_length": 8500
  },
  "page_info": {
    "url": "https://example.com/article",
    "title": "SPA の基本概念と実装パターン",
    "fetched_at": "2026-03-05T10:30:00Z"
  }
}
```

### Error Responses

#### 400 Bad Request — バリデーションエラー

```json
{
  "statusCode": 400,
  "message": "URL must use https scheme"
}
```

主なバリデーションエラー:
- URL スキームが https 以外
- URL が長すぎる（2048 文字超）
- card_type / difficulty / language が無効な値
- target_count が範囲外（5 未満または 30 超）
- URL がプライベート IP アドレスを指している

#### 403 Forbidden — ドメインブロック

```json
{
  "statusCode": 403,
  "message": "Access to this domain is not allowed"
}
```

#### 408 Request Timeout — 処理タイムアウト

```json
{
  "statusCode": 408,
  "message": "Content extraction timed out. The page may be too complex or slow to load."
}
```

#### 422 Unprocessable Entity — コンテンツ抽出失敗

```json
{
  "statusCode": 422,
  "message": "Could not extract meaningful text content from the provided URL"
}
```

主なケース:
- ページにテキストコンテンツがほとんどない（画像中心）
- ログインが必要なページ（認証未設定時）
- CAPTCHA でブロックされた

#### 429 Too Many Requests — レート制限

```json
{
  "statusCode": 429,
  "message": "Rate limit exceeded. Please try again later."
}
```

#### 502 Bad Gateway — 外部サービスエラー

```json
{
  "statusCode": 502,
  "message": "Failed to fetch content from the provided URL"
}
```

外部 URL へのアクセスが失敗した場合（DNS 解決失敗、接続タイムアウト、5xx レスポンス等）。

#### 504 Gateway Timeout — AI 処理タイムアウト

```json
{
  "statusCode": 504,
  "message": "Card generation timed out. Please try again."
}
```

## Lambda 構成

### UrlGenerateFunction

| 項目 | 値 |
|------|-----|
| Handler | `api.handler.url_generate_handler` |
| Runtime | Python 3.12 |
| Timeout | 120 seconds |
| Memory | 512 MB |
| Architecture | arm64 |

### IAM Permissions（追加分）

```yaml
- Effect: Allow
  Action:
    - bedrock-agentcore:CreateBrowser
    - bedrock-agentcore:GetBrowser
    - bedrock-agentcore:StartBrowserSession
    - bedrock-agentcore:GetBrowserSession
    - bedrock-agentcore:ConnectBrowserAutomationStream
    - bedrock-agentcore:StopBrowserSession
  Resource: "arn:aws:bedrock-agentcore:*:*:browser/*"
```

## Frontend TypeScript 型定義

```typescript
// リクエスト
interface GenerateFromUrlRequest {
  url: string;
  card_type?: 'qa' | 'definition' | 'cloze';
  target_count?: number;
  difficulty?: 'easy' | 'medium' | 'hard';
  language?: 'ja' | 'en';
  deck_id?: string;
}

// レスポンス
interface GenerateFromUrlResponse {
  generated_cards: GeneratedCardResponse[];
  generation_info: UrlGenerationInfo;
  page_info: PageInfo;
}

interface UrlGenerationInfo {
  model_used: string;
  processing_time_ms: number;
  fetch_method: 'http' | 'browser';
  chunk_count: number;
  content_length: number;
}

interface PageInfo {
  url: string;
  title: string;
  fetched_at: string;
}
```
