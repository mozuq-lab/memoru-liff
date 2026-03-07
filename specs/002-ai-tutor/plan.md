# Implementation Plan: AI Tutor (Interactive Learning)

**Branch**: `002-ai-tutor` | **Date**: 2026-03-07 | **Spec**: `specs/002-ai-tutor/spec.md`
**Input**: Feature specification from `specs/002-ai-tutor/spec.md`

## Summary

デッキ単位で AI と対話しながら学習を深める機能を実装する。Free Talk / Quiz / Weak Point Focus の 3 モードで、Bedrock (Claude) による multi-turn 会話をサポート。DynamoDB にセッションと会話履歴を保存し、React チャット UI を追加。

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.x (frontend)
**Primary Dependencies**: AWS Lambda Powertools, Pydantic v2, boto3 (Bedrock), React 19, Tailwind CSS 4
**Storage**: DynamoDB (新規 TutorSessionsTable)
**Testing**: pytest (backend), Vitest (frontend)
**Target Platform**: AWS Lambda + API Gateway (backend), LIFF/LINE (frontend)
**Project Type**: Web application (LIFF)
**Performance Goals**: 初回 AI 応答 10 秒以内 (SC-001)
**Constraints**: Lambda 実行時間制限、Bedrock レート制限、DynamoDB TTL による 7 日間保持
**Scale/Scope**: 既存ユーザーベース、1 ユーザー 1 アクティブセッション

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Pre-Phase 0 | Post-Phase 1 | Notes |
|-----------|-------------|--------------|-------|
| I. TDD | ✅ PASS | ✅ PASS | pytest + Vitest で 80%+ カバレッジ |
| II. Security First | ✅ PASS | ✅ PASS | 既存 JWT 認証使用。ユーザーデータは DynamoDB 暗号化 |
| III. API Contract Integrity | ✅ PASS | ✅ PASS | 新規エンドポイント。既存 API に影響なし |
| IV. Performance & Scalability | ✅ PASS | ✅ PASS | SC-001: 10 秒以内。PAY_PER_REQUEST |
| V. Documentation Excellence | ✅ PASS | ✅ PASS | spec/plan/research/data-model/contracts/quickstart 作成済み |

## Project Structure

### Documentation (this feature)

```text
specs/002-ai-tutor/
├── spec.md              # 機能仕様書
├── plan.md              # 本ファイル
├── research.md          # Phase 0: 技術調査
├── data-model.md        # Phase 1: データモデル
├── quickstart.md        # Phase 1: クイックスタート
├── contracts/
│   └── tutor-api.md     # Phase 1: API コントラクト
└── tasks.md             # Phase 2: タスク分解 (/speckit.tasks で作成)
```

### Source Code (repository root)

```text
backend/src/
├── api/handlers/
│   └── tutor_handler.py        # [NEW] チューター API ハンドラー
├── models/
│   └── tutor.py                # [NEW] Pydantic モデル
├── services/
│   ├── tutor_service.py        # [NEW] セッション管理ロジック
│   ├── tutor_ai_service.py     # [NEW] Bedrock 対話ロジック
│   └── prompts/
│       └── tutor.py            # [NEW] モード別プロンプト
└── template.yaml               # [MOD] テーブル・ルート・IAM 追加

backend/tests/unit/
├── test_tutor_handler.py       # [NEW]
├── test_tutor_service.py       # [NEW]
├── test_tutor_ai_service.py    # [NEW]
└── test_tutor_prompts.py       # [NEW]

frontend/src/
├── pages/
│   └── TutorPage.tsx           # [NEW] チューターページ
├── components/tutor/
│   ├── ChatMessage.tsx         # [NEW] メッセージ表示
│   ├── ChatInput.tsx           # [NEW] 入力フォーム
│   ├── ModeSelector.tsx        # [NEW] モード選択
│   ├── SessionList.tsx         # [NEW] セッション一覧
│   └── RelatedCardChip.tsx     # [NEW] 関連カード chip
├── contexts/
│   └── TutorContext.tsx        # [NEW] 状態管理
├── services/
│   └── tutor-api.ts            # [NEW] API クライアント
├── types/
│   └── tutor.ts                # [NEW] 型定義
└── App.tsx                     # [MOD] ルート追加
```

**Structure Decision**: 既存の Web アプリケーション構造（Option 2）に従う。バックエンドは `api/handlers` + `models` + `services` レイヤー、フロントエンドは `pages` + `components` + `contexts` + `services` パターン。

## Complexity Tracking

違反なし。全ゲート PASS。
