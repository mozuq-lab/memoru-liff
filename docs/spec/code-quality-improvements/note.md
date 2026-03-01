# code-quality-improvements コンテキストノート

**作成日**: 2026-03-01

## 要件の背景

コミット d3a30fe から 0f1df22 の間（約50コミット）のコードレビューが未実施だったため、
Claude Opus 4.6 と OpenAI Codex の2レビュアーによるコードレビューを実施。
計25件の指摘事項が発見され、うち Critical+High+Medium の 17件を改善対象とする。

## 技術スタック

- **バックエンド**: Python 3.12 / AWS SAM (Lambda, API Gateway, DynamoDB)
- **フロントエンド**: React 19 + TypeScript 5.x / Vite 7 / Tailwind CSS 4
- **AI サービス**: Strands Agents SDK / Amazon Bedrock
- **認証**: Keycloak / OIDC + PKCE

## 対象ファイル（主要）

### バックエンド
- `backend/src/api/handler.py` - Lambda ハンドラー（JWT フォールバック）
- `backend/src/api/shared.py` - 共通ユーティリティ（JWT フォールバック重複）
- `backend/src/services/ai_service.py` - AIService Protocol
- `backend/src/services/strands_service.py` - Strands AI 実装
- `backend/src/services/bedrock.py` - Bedrock AI 実装
- `backend/src/services/review_service.py` - 復習サービス
- `backend/src/services/card_service.py` - カードサービス
- `backend/src/services/user_service.py` - ユーザーサービス

### フロントエンド
- `frontend/src/pages/ReviewPage.tsx` - 復習ページ
- `frontend/src/services/api.ts` - API クライアント
- `frontend/src/contexts/CardsContext.tsx` - カードコンテキスト

## 関連文書

- **コードレビュー結果**: `docs/reviews/code-review-d3a30fe-to-0f1df22.md`
- **既存要件定義**: `docs/spec/` 配下の各要件
- **既存設計文書**: `docs/design/` 配下の各設計

## 注意事項

- M-08 (link_line 非原子的) は対象コミット範囲での変更量が少なく、既存コードの問題
- H-08 (undo reviews_table) はユーザー確認済み: 仕様として明文化する方針
- M-06 (_get_next_due_date) はユーザー確認済み: 条件追加して明示的に将来日のみ取得
