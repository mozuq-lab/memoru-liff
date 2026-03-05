# Implementation Plan: URL からカード自動生成（AgentCore Browser 活用）

**Branch**: `002-url-card-generation` | **Date**: 2026-03-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-url-card-generation/spec.md`

## Summary

URL を入力するだけで Web ページのコンテンツを AI が読み取り、暗記カードを自動生成する機能。AgentCore Browser を活用し、SPA や動的コンテンツにも対応する。既存の Strands Agents SDK アーキテクチャを拡張し、新規エンドポイント `POST /cards/generate-from-url` として実装する。静的ページは HTTP fetch にフォールバックしてコスト最適化を図る。

## Technical Context

**Language/Version**: Python 3.12（バックエンド）, TypeScript 5.x（フロントエンド）
**Primary Dependencies**: Strands Agents SDK, strands-agents-tools（AgentCoreBrowser）, BeautifulSoup4/markdownify, Bedrock Claude Haiku 4.5, React 19, Vite 7, Tailwind CSS 4
**Storage**: DynamoDB（既存テーブル: cards, reviews, decks, users）
**Testing**: pytest + coverage（バックエンド）, Vitest（フロントエンド）
**Target Platform**: AWS Lambda（バックエンド）, LIFF（LINE Frontend Framework）on CloudFront + S3
**Project Type**: Web application（サーバーレス）
**Performance Goals**: URL 入力からカードプレビュー表示まで 60 秒以内（公開ページ）、SPA ページでも 90 秒以内
**Constraints**: Lambda タイムアウト上限 120 秒、AgentCore Browser セッションコスト最小化、既存 API との後方互換性維持
**Scale/Scope**: 既存ユーザーベース対象、1回の生成で最大 30 枚

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Pre-Phase 0 Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Test-Driven Development | ✅ Pass | TDD サイクルで実装。コンテンツ取得サービス、URL バリデーション、チャンク分割ロジックにユニットテスト。AI 統合はモックベースのインテグレーションテスト |
| II. Security First | ✅ Pass | SSRF 防止（内部 IP ブロック）、ドメイン制御、URL スキーム制限（https のみ）、コンテンツサニタイズ |
| III. API Contract Integrity | ✅ Pass | 新規エンドポイントとして追加。既存 API に変更なし。Pydantic v2 モデルで型安全性確保 |
| IV. Performance & Scalability | ✅ Pass | 静的/動的ページの判定による AgentCore Browser 呼び出し最小化。進捗表示で長時間処理の UX 対応 |
| V. Documentation Excellence | ✅ Pass | API ドキュメント、設計文書、クイックスタートガイドを本プランで作成 |

### Post-Phase 1 Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Test-Driven Development | ✅ Pass | テスト戦略確定: ユニット（URL バリデーション、SPA 判定、チャンク分割）、インテグレーション（AI サービス統合）、E2E（フロントエンド→API→Browser） |
| II. Security First | ✅ Pass | 3 層防御設計確定: AgentCore Browser ドメイン制御 + URL バリデーション + HTML サニタイズ |
| III. API Contract Integrity | ✅ Pass | contracts/ にエンドポイント定義完了。Pydantic モデルと TypeScript 型の対応確認済み |
| IV. Performance & Scalability | ✅ Pass | 判定ロジックとフォールバック設計でコスト/パフォーマンス最適化 |
| V. Documentation Excellence | ✅ Pass | research.md, data-model.md, contracts/, quickstart.md 完成 |

## Project Structure

### Documentation (this feature)

```text
specs/002-url-card-generation/
├── plan.md              # This file
├── research.md          # Phase 0: 技術調査と意思決定
├── data-model.md        # Phase 1: データモデル定義
├── quickstart.md        # Phase 1: 実装クイックスタート
├── contracts/           # Phase 1: API コントラクト
│   └── api.md           # POST /cards/generate-from-url 定義
├── checklists/
│   └── requirements.md  # 仕様品質チェックリスト
└── tasks.md             # Phase 2: タスク分割（/speckit.tasks で作成）
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── api/
│   │   └── handlers/
│   │       └── ai_handler.py          # 既存ファイル: generate_from_url() ハンドラー追加
│   ├── models/
│   │   └── url_generate.py            # 新規: URL 生成リクエスト/レスポンスモデル
│   ├── services/
│   │   ├── url_content_service.py     # 新規: URL コンテンツ取得サービス
│   │   ├── content_chunker.py         # 新規: コンテンツチャンク分割
│   │   ├── strands_service.py         # 既存: URL 生成メソッド追加
│   │   ├── ai_service.py             # 既存: Protocol にメソッド追加
│   │   └── prompts/
│   │       └── url_generate.py        # 新規: URL 生成用プロンプト
│   └── utils/
│       └── url_validator.py           # 新規: URL バリデーション + SSRF 防止
├── tests/
│   ├── unit/
│   │   ├── test_url_content_service.py
│   │   ├── test_content_chunker.py
│   │   └── test_url_validator.py
│   └── integration/
│       └── test_url_generate_api.py
└── template.yaml                      # 既存: UrlGenerateFunction 追加

frontend/
├── src/
│   ├── pages/
│   │   └── GeneratePage.tsx           # 既存: URL 入力タブ追加
│   ├── components/
│   │   ├── UrlInput.tsx               # 新規: URL 入力フォーム
│   │   ├── GenerateOptions.tsx        # 新規: 生成オプション（カードタイプ、枚数）
│   │   └── GenerateProgress.tsx       # 新規: 3段階プログレス表示
│   ├── services/
│   │   └── api.ts                     # 既存: generateFromUrl() メソッド追加
│   └── types/
│       └── generate.ts                # 既存: URL 生成用型定義追加
└── tests/
    └── components/
        ├── UrlInput.test.tsx
        └── GenerateOptions.test.tsx
```

**Structure Decision**: 既存の Web アプリケーション構成（backend/ + frontend/）に新規ファイルを追加。既存ファイルの拡張を優先し、新規ファイルは責務が明確に分離される場合のみ作成。

## Complexity Tracking

> 本機能は Constitution に違反する要素なし。以下は設計上の複雑性に関する注記。

| 複雑性 | 理由 | シンプルな代替案を却下した理由 |
|--------|------|-------------------------------|
| 2段階コンテンツ取得（HTTP fetch + AgentCore Browser） | コスト最適化のため静的ページは Browser 不使用 | 常に Browser を使用する案はコストが 3〜5 倍になる |
| チャンク分割 + 重複除去 | Web ページはテキスト生成の入力上限を超えることが多い | 全文投入は Bedrock のトークン上限に抵触 |
| 専用 Lambda 関数 | タイムアウト/メモリ要件が既存 API と異なる | 既存 ApiFunction の拡張ではタイムアウト 120 秒の設定が他のエンドポイントに影響 |
