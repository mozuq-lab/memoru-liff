# Research: AI Tutor (Interactive Learning)

**Date**: 2026-03-07

## 1. Multi-Turn Conversation Architecture

**Decision**: Bedrock Messages API with DynamoDB-backed conversation history

**Rationale**: 既存の BedrockService がメッセージ配列形式を使用しており、会話履歴を DynamoDB に保存して各ターンで全履歴をロードする方式が最もシンプル。Strands Agent はセッション間でステートを保持できないため、どちらの実装でも DynamoDB にヒストリーを保存する必要がある。Bedrock Messages API は `messages` 配列で multi-turn を直接サポート。

**Alternatives considered**:
- Strands Agent の持続的エージェント: Lambda の実行モデルと合わない（ステートレス）
- Redis/ElastiCache でセッション管理: コスト増加、インフラ複雑化。DynamoDB で十分

## 2. Tutor Service の設計パターン

**Decision**: 新規 `TutorService` クラスを作成。既存 `AIService` Protocol とは独立した Protocol を定義

**Rationale**: 既存の `AIService` Protocol は単一ターンの操作（generate, grade, refine）に特化。チューター機能はセッション管理、会話履歴、モード切替など根本的に異なる責務を持つ。Protocol を分離することで既存コードへの影響を最小化。

**Alternatives considered**:
- `AIService` Protocol を拡張: 責務が肥大化。既存テスト（67ファイル）への影響大
- `AIService` をラップする Facade: 不要な間接層。チューターは独自の Bedrock 呼び出しパターンを持つ

## 3. プロンプト設計: モード別システムプロンプト

**Decision**: 学習モード（Free Talk / Quiz / Weak Point Focus）ごとにシステムプロンプトテンプレートを定義。カード内容をコンテキストとして注入

**Rationale**: 既存の prompts パッケージ（`backend/src/services/prompts/`）の設計パターンに合致。モードごとに AI の振る舞いを明確に分離でき、テスト容易性が高い。

**Alternatives considered**:
- 単一プロンプト + モードフラグ: プロンプトが複雑化。テスト・デバッグが困難
- Strands Tools でモード切替: Tool 呼び出しのオーバーヘッド。シンプルなプロンプト切替で十分

## 4. セッションタイムアウトの実装方式

**Decision**: クライアント側チェック + サーバー側バリデーション

**Rationale**: Lambda はステートレスのため、タイマーベースのタイムアウトは不可。メッセージ送信時にサーバー側で `last_message_at + 30分` をチェック。クライアント側でも UI をタイムアウト表示に切替。DynamoDB TTL は 7 日後のデータ削除に使用（タイムアウトとは別）。

**Alternatives considered**:
- EventBridge スケジュール: タイムアウト処理にしては過剰。コスト増
- クライアントのみ: セキュリティ上不十分。サーバー側での検証が必要

## 5. フロントエンド: チャット UI の実装

**Decision**: 新規 `TutorPage` + `ChatMessage` コンポーネント。既存の Context パターンに従い `TutorContext` を作成

**Rationale**: 既存の CardsContext/DecksContext パターンに合致。チャット UI は独立したページとして実装し、既存ページへの影響ゼロ。

**Alternatives considered**:
- 外部チャットライブラリ: 依存性追加。Tailwind CSS との統合が煩雑
- ReviewPage への統合: 責務が異なる。ページが複雑化

## 6. 関連カード提案の実装

**Decision**: AI のレスポンスから card_id 参照を抽出し、フロントエンドで tappable chip として表示

**Rationale**: AI にデッキ内のカード情報（card_id 含む）を提供し、応答内で関連カードを参照させる。フロントエンドは card_id を使ってカード詳細画面に遷移。既存の `CardDetailPage` を再利用。

**Alternatives considered**:
- 別途 similarity search API: 実装コスト大。AI が既にカード内容を理解しているので不要
- インラインカード表示: UI が複雑化。chip + 遷移のほうがモバイルに適切

## 7. モデル選定

**Decision**: 既存の `BEDROCK_MODEL_ID` 環境変数を使用（デフォルト: Claude Haiku 4.5）。チューター用に別モデルを設定可能にする `TUTOR_MODEL_ID` 環境変数を追加

**Rationale**: チューターは対話品質が重要なため、将来的により高性能なモデル（Claude Sonnet）への切替が想定される。既存のカード生成/採点とは独立してモデルを選択できるべき。

**Alternatives considered**:
- 共通の BEDROCK_MODEL_ID のみ: チューター固有のモデル最適化ができない
- ハードコード: 環境ごとの柔軟性が失われる
