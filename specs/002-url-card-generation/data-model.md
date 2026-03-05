# Data Model: URL からカード自動生成

**Branch**: `002-url-card-generation` | **Date**: 2026-03-05

## エンティティ定義

### URLGenerateRequest（リクエストモデル）

URL からカードを生成するための API リクエスト。

| フィールド | 型 | 必須 | バリデーション | 説明 |
|-----------|-----|------|---------------|------|
| url | string | ✅ | https スキーム、最大 2,048 文字、内部 IP ブロック | 対象ページの URL |
| card_type | enum | - | "qa" \| "definition" \| "cloze" | カードタイプ（デフォルト: "qa"） |
| target_count | int | - | 5〜30、デフォルト 10 | 生成枚数の目安 |
| difficulty | enum | - | "easy" \| "medium" \| "hard" | 難易度（デフォルト: "medium"） |
| language | enum | - | "ja" \| "en" | 言語（デフォルト: "ja"） |
| deck_id | string | - | ULID 形式 | 保存先デッキ ID |

### URLGenerateResponse（レスポンスモデル）

| フィールド | 型 | 説明 |
|-----------|-----|------|
| generated_cards | GeneratedCardResponse[] | 生成されたカードのリスト |
| generation_info | URLGenerationInfo | 生成メタデータ |
| page_info | PageInfo | 取得ページの情報 |

### URLGenerationInfo（生成メタデータ）

| フィールド | 型 | 説明 |
|-----------|-----|------|
| model_used | string | 使用した AI モデル（例: "strands_bedrock"） |
| processing_time_ms | int | 総処理時間（ミリ秒） |
| fetch_method | enum | "http" \| "browser" — コンテンツ取得方法 |
| chunk_count | int | チャンク分割数 |
| content_length | int | 取得したテキストの文字数 |

### PageInfo（ページ情報）

| フィールド | 型 | 説明 |
|-----------|-----|------|
| url | string | 最終的にアクセスした URL（リダイレクト後） |
| title | string | ページタイトル |
| fetched_at | string (ISO 8601) | 取得日時 |

### PageContent（内部モデル — API 非公開）

URL から取得したページコンテンツの内部表現。

| フィールド | 型 | 説明 |
|-----------|-----|------|
| url | string | 最終 URL |
| title | string | ページタイトル |
| text_content | string | 抽出されたテキスト（HTML タグ除去済み） |
| content_type | string | Content-Type ヘッダー |
| fetch_method | enum | "http" \| "browser" |
| fetched_at | datetime | 取得日時 |

### ContentChunk（内部モデル — API 非公開）

チャンク分割されたコンテンツの1単位。

| フィールド | 型 | 説明 |
|-----------|-----|------|
| text | string | チャンクのテキスト（最大 3,000 文字） |
| section_title | string \| None | セクション見出し |
| page_title | string | ページタイトル（コンテキスト用） |
| chunk_index | int | チャンク番号（0始まり） |
| total_chunks | int | 総チャンク数 |

## エンティティ関係図

```text
URLGenerateRequest
  │
  ▼
┌─────────────────────┐
│ url_content_service  │──→ PageContent
│ (コンテンツ取得)      │      │
└─────────────────────┘      ▼
                        ┌──────────────┐
                        │content_chunker│──→ ContentChunk[]
                        │(チャンク分割)   │      │
                        └──────────────┘      ▼
                                         ┌──────────────┐
                                         │ ai_service    │──→ GeneratedCard[]
                                         │(カード生成)    │      │
                                         └──────────────┘      ▼
                                                          URLGenerateResponse
                                                               │
                                                               ▼
                                                          Card (既存) ← 保存時
```

## 既存エンティティとの関係

### Card（既存 — 変更なし）

URL 生成されたカードは、既存の Card エンティティとして保存される。追加フィールドは不要。

- `front` / `back`: 生成されたカード内容
- `references`: ページの出典情報（type: "url", value: ページ URL）を自動付与
- `tags`: "AI生成", "URL生成" タグを自動付与
- `deck_id`: リクエストで指定されたデッキ ID

### GeneratedCardResponse（既存 — 変更なし）

既存の `GeneratedCardResponse`（front, back, suggested_tags）をそのまま使用。URL 生成固有の情報は `URLGenerateResponse` の `page_info` に格納。

## 状態遷移

### URL 生成フロー

```text
[入力] → [URL検証] → [コンテンツ取得] → [チャンク分割] → [カード生成] → [レスポンス]
  │         │            │                  │               │              │
  │         ├→ 無効URL    ├→ HTTP fetch      ├→ 短文: 1チャンク  ├→ チャンクごと   ├→ 成功
  │         └→ エラー     ├→ Browser fetch   └→ 長文: N チャンク  │  に生成        └→ GeneratedCards
  │                      └→ 取得失敗                            └→ 重複除去
  │                         → エラー
  └→ バリデーションエラー
```

## DynamoDB への影響

**テーブル変更: なし**

URL 生成機能は既存テーブル構造で完全に動作する:
- `cards` テーブル: 生成されたカードを既存の `POST /cards` API 経由で保存
- `reviews` テーブル: 保存されたカードの初回レビュー情報が自動作成される
- 新規テーブルは不要
