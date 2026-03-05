# Research: URL からカード自動生成（AgentCore Browser 活用）

**Branch**: `002-url-card-generation` | **Date**: 2026-03-05

## Research Tasks

### R-001: AgentCore Browser と Strands Agents SDK の統合方法

**Decision**: Strands Agents SDK の `AgentCoreBrowser` ツールを使用し、既存の Agent ベースアーキテクチャに統合する

**Rationale**:
- プロジェクトは既に Strands Agents SDK（`strands` パッケージ）を使用しており、`Agent` クラスに `tools` パラメータとして `AgentCoreBrowser` を渡すだけで統合可能
- `strands-agents-tools` パッケージに `AgentCoreBrowser` が含まれており、追加の抽象化レイヤーは不要
- 既存の `StrandsAIService` クラスのパターン（Protocol + Factory）をそのまま拡張できる

**Alternatives considered**:
- Playwright 直接利用: AgentCore Browser の CDP 接続を使えるが、AI エージェントとの統合が手動になる
- browser-use ライブラリ: Strands 以外のフレームワーク。既存アーキテクチャとの整合性が低い
- AWS SDK (boto3) 直接利用: 低レベルすぎ。セッション管理やオートメーション制御のコードが増大

### R-002: コンテンツ取得方式の判定（Browser vs HTTP fetch）

**Decision**: 2段階方式を採用。まず軽量な HTTP HEAD リクエストで Content-Type を確認し、HTML の場合はレスポンスヘッダーと簡易パースで SPA 判定を行う。SPA と判定された場合のみ AgentCore Browser を使用する

**Rationale**:
- AgentCore Browser はセッション単位で課金されるため、静的ページにまで使用するとコストが不必要に増加
- 多くの技術ドキュメント（MDN、AWS Docs の一部）は SSR されており HTTP fetch で十分
- Content-Type が HTML 以外（PDF 等）の場合は専用のパーサーにルーティング

**判定ロジック**:
1. HTTP HEAD → Content-Type 確認
2. HTML の場合: HTTP GET → レスポンス解析
   - `<noscript>` タグの存在、`<div id="root"></div>` のような空コンテナ、`bundle.js` 等のパターンで SPA 判定
   - メインコンテンツのテキスト量が閾値未満の場合も SPA 候補
3. SPA と判定 → AgentCore Browser で再取得
4. 非 SPA → HTTP fetch の結果をそのまま使用

**Alternatives considered**:
- 常に AgentCore Browser を使用: シンプルだがコスト高。静的ページには過剰
- ユーザーに選択させる: UX が複雑化。ユーザーは SPA かどうか判断できない
- URL パターンで判定（ドメインベースの許可リスト）: メンテナンスコストが高い

### R-003: 長大コンテンツのチャンク分割戦略

**Decision**: トークン数ベースでチャンク分割し、各チャンクから独立してカード生成後、重複除去を行う

**Rationale**:
- 既存の `generate_cards()` は入力テキスト 2,000 文字制限。Web ページは数千〜数万文字になりうる
- Claude のコンテキストウィンドウ内に収まるよう、適切なサイズに分割が必要
- セマンティックな区切り（見出し `<h1>`〜`<h6>` 単位）でチャンク化し、文脈を保持

**チャンク戦略**:
1. HTML からテキスト抽出（BeautifulSoup / markdownify）
2. 見出しベースでセクション分割
3. 各セクションが 3,000 文字以下になるようさらに分割（段落単位）
4. 各チャンクにページタイトルとセクション見出しをコンテキストとして付与
5. チャンクごとにカード生成 → 最終的に重複除去・マージ

**Alternatives considered**:
- 固定長分割（500文字ずつ）: 文脈が失われやすい
- 全文を要約してから生成: 要約段階で重要情報が欠落するリスク
- ページ全体を1回のプロンプトに投入: トークン制限に抵触。コスト増大

### R-004: AgentCore Browser のリージョンとコスト

**Decision**: ap-northeast-1（東京）を優先し、利用不可の場合は us-west-2 にフォールバック

**Rationale**:
- AgentCore Browser は 14 リージョンで利用可能（ap-northeast-1 含む）
- レイテンシ最小化のため東京リージョンが最適
- Bedrock モデルとは異なるリージョンでも動作可能

**コスト考慮**:
- AgentCore Browser は秒単位課金（最小 1 秒、最小 128 MB メモリ）
- 典型的な Web ページ取得は 5〜15 秒程度
- FR-008（静的ページのフォールバック）でコスト最適化

**Alternatives considered**:
- us-east-1 固定: レイテンシが高い（ユーザーは日本在住が多い）
- マルチリージョンフェイルオーバー: 複雑性に対してメリットが少ない

### R-005: 既存 API との統合パターン

**Decision**: 新規 API エンドポイント `POST /cards/generate-from-url` を追加。既存の `POST /cards/generate` とは分離する

**Rationale**:
- URL 生成は処理時間が長い（30〜60 秒）ため、既存 API のタイムアウト設定では不足
- 入力パラメータが異なる（テキスト vs URL + オプション）
- 専用の Lambda 関数で、メモリ・タイムアウトを個別設定可能

**Lambda 構成**:
- 新規 Lambda 関数: `UrlGenerateFunction`
- タイムアウト: 120 秒（AgentCore Browser セッション + AI 生成時間を考慮）
- メモリ: 512 MB（HTML パース + AI 処理に十分）
- IAM: 既存の Bedrock 権限 + `bedrock-agentcore:*` 権限を追加

**Alternatives considered**:
- 既存 `POST /cards/generate` を拡張: 入力バリデーションが複雑化。単一責任の原則に反する
- 非同期ジョブ（Step Functions）: MVP には過剰。将来の拡張で検討
- WebSocket でリアルタイム進捗: 実装コストが高い。まずはポーリングで十分

### R-006: セキュリティ対策

**Decision**: ドメイン許可リスト + SSRF 防止 + コンテンツサニタイズの3層防御

**Rationale**:
- AgentCore Browser は外部サイトにアクセスするため、SSRF（Server-Side Request Forgery）リスクがある
- ユーザーが悪意のある URL を入力する可能性を考慮

**実装方針**:
1. **ドメイン許可リスト**: AgentCore Browser のドメイン制御機能で、内部ネットワーク（10.x, 172.16.x, 192.168.x, localhost）をブロック
2. **URL バリデーション**: スキーム制限（https のみ）、IP アドレス直指定の禁止
3. **コンテンツサニタイズ**: 取得した HTML からスクリプトタグ等を除去してからテキスト抽出
4. **セッション分離**: AgentCore Browser のセッション分離機能で、ユーザー間のデータ漏洩を防止

**Alternatives considered**:
- ドメインホワイトリストのみ: 柔軟性が低い（ユーザーが任意のサイトを使いたい）
- WAF ルール: API Gateway レベルでは URL の内容まで検証できない

### R-007: フロントエンドの UX 設計

**Decision**: 既存の GeneratePage を拡張し、入力モード切替（テキスト / URL）タブを追加

**Rationale**:
- 既存の GeneratePage のプレビュー・編集・保存フローはそのまま再利用可能
- ユーザーが慣れた UI パターンを維持

**UI フロー**:
1. 入力タブ切替: 「テキスト入力」| 「URL から生成」
2. URL 入力フォーム + オプション（カードタイプ、枚数目安）
3. 生成ボタン → プログレスバー（3段階: ページ取得 → 解析 → カード生成）
4. 以降は既存と同じ（プレビュー → 編集 → デッキ選択 → 保存）

**Alternatives considered**:
- 別ページとして実装: ナビゲーションが増え、UX が分散
- URL 検知の自動切替: 入力内容のリアルタイム判定が不安定
