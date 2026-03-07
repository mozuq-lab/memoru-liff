# Quickstart: AI Tutor (Interactive Learning)

**Date**: 2026-03-07

## 概要

デッキ単位で AI と対話しながら学習を深める機能。Free Talk / Quiz / Weak Point Focus の 3 モードをサポート。

## アーキテクチャ概要

```
Frontend (React)                Backend (Lambda)              AWS Services
┌────────────────┐         ┌──────────────────────┐     ┌──────────────────┐
│ TutorPage      │──POST──▶│ tutor_handler.py     │────▶│ DynamoDB         │
│ ChatMessage    │         │   start_session()    │     │  TutorSessions   │
│ ModeSelector   │◀─JSON──│   send_message()     │     │                  │
│ SessionList    │         │   end_session()      │     │ Bedrock          │
│                │         │   list_sessions()    │────▶│  Claude Haiku    │
└────────────────┘         │   get_session()      │     │  (or Sonnet)     │
                           └──────────────────────┘     └──────────────────┘
```

## 新規ファイル一覧

### バックエンド

| ファイル | 説明 |
|---------|------|
| `backend/src/api/handlers/tutor_handler.py` | API ハンドラー（5 エンドポイント） |
| `backend/src/models/tutor.py` | Pydantic モデル（Request/Response） |
| `backend/src/services/tutor_service.py` | セッション管理ビジネスロジック |
| `backend/src/services/tutor_ai_service.py` | AI 対話ロジック（Bedrock 呼び出し） |
| `backend/src/services/prompts/tutor.py` | モード別システムプロンプト |

### フロントエンド

| ファイル | 説明 |
|---------|------|
| `frontend/src/pages/TutorPage.tsx` | チューターメインページ |
| `frontend/src/components/tutor/ChatMessage.tsx` | チャットメッセージ表示 |
| `frontend/src/components/tutor/ChatInput.tsx` | メッセージ入力フォーム |
| `frontend/src/components/tutor/ModeSelector.tsx` | 学習モード選択 |
| `frontend/src/components/tutor/SessionList.tsx` | 過去セッション一覧 |
| `frontend/src/components/tutor/RelatedCardChip.tsx` | 関連カード chip |
| `frontend/src/contexts/TutorContext.tsx` | チューター状態管理 |
| `frontend/src/services/tutor-api.ts` | チューター API クライアント |
| `frontend/src/types/tutor.ts` | TypeScript 型定義 |

### インフラ

| ファイル | 変更内容 |
|---------|---------|
| `backend/template.yaml` | TutorSessionsTable 追加、IAM ポリシー追加、API ルート追加 |

## 主要な実装パターン

### 1. セッション開始フロー

```
User → ModeSelector → POST /api/tutor/sessions
                       ↓
              TutorService.start_session()
                ↓ 既存アクティブセッション終了
                ↓ デッキのカード取得
                ↓ システムプロンプト構築
                ↓ Bedrock 初回呼び出し（挨拶生成）
                ↓ DynamoDB にセッション保存
              ← TutorSessionResponse
```

### 2. メッセージ送信フロー

```
User → ChatInput → POST /api/tutor/sessions/{id}/messages
                    ↓
           TutorService.send_message()
             ↓ セッション読み込み（DynamoDB）
             ↓ タイムアウトチェック（30分）
             ↓ メッセージ上限チェック（20 RT）
             ↓ 会話履歴 + 新メッセージ → Bedrock
             ↓ AI 応答から関連カード抽出
             ↓ セッション更新（DynamoDB）
           ← SendMessageResponse
```

### 3. Bedrock 呼び出しパターン

```python
messages = [
    {"role": msg.role, "content": msg.content}
    for msg in session.messages
]
messages.append({"role": "user", "content": user_message})

request_body = {
    "anthropic_version": "bedrock-2023-05-31",
    "max_tokens": 1024,
    "temperature": 0.7,
    "system": system_prompt,  # モード別 + カードコンテキスト
    "messages": messages
}
```

## ローカル開発手順

```bash
# 1. バックエンド起動
cd backend
make local-all          # DynamoDB Local + Keycloak + Ollama
make local-api          # SAM Local API (port 8080)

# 2. フロントエンド起動
cd frontend
npm run dev             # Vite (port 3000)

# 3. テスト実行
cd backend && make test
cd frontend && npm run test
```

## 環境変数（追加分）

| 変数名 | デフォルト | 説明 |
|--------|-----------|------|
| `TUTOR_SESSIONS_TABLE` | `memoru-tutor-sessions-{env}` | DynamoDB テーブル名 |
| `TUTOR_MODEL_ID` | `BEDROCK_MODEL_ID` と同じ | チューター用 Bedrock モデル ID |
| `TUTOR_MAX_ROUNDS` | `20` | セッションあたりの最大ラウンドトリップ数 |
| `TUTOR_TIMEOUT_MINUTES` | `30` | セッションタイムアウト（分） |
