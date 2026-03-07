# Feature Specification: URL からカード自動生成（AgentCore Browser 活用）

**Feature Branch**: `002-url-card-generation`
**Created**: 2026-03-05
**Status**: Draft
**Input**: User description: "URL を貼るだけで Web ページの内容を AI が読み取り、暗記カードを自動生成する。AgentCore Browser を活用し、JavaScript レンダリングが必要な SPA やログイン後のページにも対応する。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 公開 Web ページからカード生成 (Priority: P1)

ユーザーが学習したい Web ページの URL を LIFF アプリに貼り付けると、AI がページ内容を読み取り、重要なポイントを暗記カードとして自動生成する。ユーザーはプレビューで確認・編集してから保存できる。

**Why this priority**: 最も基本的なユースケース。公開ページのカード生成ができれば、多くのユーザーの学習効率を即座に向上できる。技術記事、Wikipedia、ドキュメントサイトなど幅広い用途に対応。

**Independent Test**: URL を入力フォームに貼り付け → 生成ボタンを押す → カードがプレビュー表示される → 保存してデッキに追加される、という一連の流れを単独でテスト可能。

**Acceptance Scenarios**:

1. **Given** ユーザーが LIFF アプリのカード生成画面にいる, **When** 公開 Web ページの URL を入力して生成ボタンを押す, **Then** AI がページ内容を解析し、5〜20枚の暗記カードを生成してプレビュー表示する
2. **Given** カードが生成されプレビュー表示されている, **When** ユーザーが個別カードの内容を編集する, **Then** 編集内容がプレビューに即座に反映される
3. **Given** カードが生成されプレビュー表示されている, **When** ユーザーが保存先デッキを選択して保存する, **Then** 選択したカードが指定デッキに追加される
4. **Given** ユーザーが URL を入力した, **When** URL が無効またはアクセスできない, **Then** わかりやすいエラーメッセージが表示される

---

### User Story 2 - SPA・動的コンテンツページからのカード生成 (Priority: P2)

JavaScript でレンダリングされる SPA（Single Page Application）や動的コンテンツのページから、AgentCore Browser を使ってレンダリング済みの DOM を取得し、カードを生成する。

**Why this priority**: 多くの現代の学習サイト（MDN、Qiita、Zenn、技術ドキュメント等）は SPA で構築されており、単純な HTTP fetch ではコンテンツを取得できない。AgentCore Browser の最大の差別化ポイント。

**Independent Test**: SPA で構築されたサイト（例：React ベースのドキュメントサイト）の URL を入力し、JavaScript レンダリング後のコンテンツからカードが生成されることを確認。

**Acceptance Scenarios**:

1. **Given** ユーザーが SPA サイトの URL を入力する, **When** 生成ボタンを押す, **Then** AgentCore Browser が JavaScript をレンダリングし、完全なコンテンツからカードを生成する
2. **Given** ページに遅延読み込み（lazy loading）コンテンツがある, **When** 生成処理が実行される, **Then** メインコンテンツが読み込まれるまで適切に待機してからカードを生成する

---

### User Story 3 - 生成オプションのカスタマイズ (Priority: P2)

ユーザーが生成するカードの粒度や形式をカスタマイズできる。例えば、「用語の定義」「Q&A形式」「穴埋め形式」などのカードタイプを指定したり、生成枚数の目安を指定できる。

**Why this priority**: 既存のテキストベースのカード生成（`POST /cards/generate`）との差別化と、学習スタイルへの適応のため。URL からの生成はコンテンツ量が多いため、カスタマイズの価値が高い。

**Independent Test**: 同じ URL に対して異なるオプション（Q&A形式 vs 穴埋め形式、10枚 vs 20枚）で生成し、出力が指定に応じて変わることを確認。

**Acceptance Scenarios**:

1. **Given** ユーザーが URL を入力している, **When** カードタイプ（用語定義 / Q&A / 穴埋め）を選択して生成する, **Then** 選択したタイプに沿ったカードが生成される
2. **Given** ユーザーが URL を入力している, **When** 生成枚数の目安（少なめ / 標準 / 多め）を指定する, **Then** 指定に近い枚数のカードが生成される
3. **Given** ユーザーがオプションを未指定のまま生成する, **When** 生成ボタンを押す, **Then** デフォルト設定（Q&A形式、標準枚数）でカードが生成される

---

### User Story 4 - LINE チャットからの URL カード生成 (Priority: P3)

ユーザーが LINE チャットで URL を送信すると、Bot が自動的にカードを生成し、確認メッセージを返す。

**Why this priority**: LINE 上で完結する体験を提供し、LIFF アプリを開く手間を省く。ただし LIFF での体験が先にあるべき。

**Independent Test**: LINE チャットに URL を送信 → Bot が「カード生成中...」と返信 → 生成完了後にカード一覧の Flex Message が送信される。

**Acceptance Scenarios**:

1. **Given** ユーザーが LINE チャットに URL を送信する, **When** Bot が URL を検知する, **Then** カード生成を開始し、進捗メッセージを返信する
2. **Given** カード生成が完了した, **When** 結果が返される, **Then** 生成されたカードのプレビューを Flex Message で表示し、保存ボタンを提供する

---

### User Story 5 - 認証が必要なページからのカード生成 (Priority: P3)

AgentCore Browser の Browser Profiles 機能を活用し、ログインが必要な学習サイト（社内 Wiki、有料学習サービス等）からもカードを生成できる。

**Why this priority**: 高度なユースケースであり、セキュリティ上の考慮も必要。MVP 後の拡張機能として位置づける。

**Independent Test**: Browser Profile にログインセッションを保存 → 認証済みの状態でページにアクセス → コンテンツからカードが生成される。

**Acceptance Scenarios**:

1. **Given** ユーザーが Browser Profile を設定済み, **When** 認証が必要なページの URL を入力して生成する, **Then** 保存された認証情報を使ってページにアクセスし、カードを生成する
2. **Given** Browser Profile が未設定または期限切れ, **When** 認証が必要なページの URL を入力する, **Then** 「認証設定が必要です」というガイダンスを表示する

---

### Edge Cases

- URL がペイウォール付きコンテンツの場合、アクセス可能な部分のみからカード生成を試みる
- 非常に長いページ（例：10,000語超）の場合、コンテンツを適切にチャンク分割して処理する
- 画像中心のページ（インフォグラフィック等）で、テキストコンテンツが不足する場合は警告を表示する
- PDF リンクの場合、PDF のテキスト内容を抽出してカード生成する
- 同じ URL から再度生成する場合、既存カードとの重複を検知して警告する
- 複数言語が混在するページの場合、主要言語でカードを生成する
- ページがリダイレクトする場合、最終 URL のコンテンツを使用する
- AgentCore Browser セッションがタイムアウトした場合、適切にリトライまたはフォールバックする
- CAPTCHA が出現した場合、AgentCore Browser の CAPTCHA 低減機能を活用しつつ、解決できない場合はエラーを返す

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: ユーザーが URL を入力すると、システムは Web ページのコンテンツを取得し、暗記カードを自動生成できること
- **FR-002**: システムは AgentCore Browser を使用して、JavaScript レンダリングが必要な SPA ページのコンテンツを取得できること
- **FR-003**: 生成されたカードをプレビュー画面で一覧表示し、個別に編集・選択・削除できること
- **FR-004**: ユーザーが保存先デッキを選択してカードを一括保存できること
- **FR-005**: カードタイプ（用語定義 / Q&A / 穴埋め）と生成枚数の目安を指定できること
- **FR-006**: URL の有効性を検証し、アクセスできない場合はわかりやすいエラーメッセージを表示すること
- **FR-007**: 生成中は進捗状態をユーザーに表示すること（ページ取得中 → コンテンツ解析中 → カード生成中）
- **FR-008**: 静的コンテンツのみのページの場合は、ブラウザレンダリングなしで高速かつ低コストに処理できること（コスト最適化）
- **FR-009**: 既存のカード生成 API（`POST /cards/generate`）と同じ品質基準でカードを生成すること
- **FR-010**: 1回の生成で最大 30 枚までのカードを生成できること
- **FR-011**: ページコンテンツが長大な場合（10,000語超）、適切にチャンク分割して処理すること
- **FR-012**: 生成結果にページの出典情報（URL、タイトル、アクセス日時）をカードの参考情報（references）として自動付与すること
- **FR-013**: AgentCore Browser のセッションタイムアウトやエラー発生時に、適切にリトライまたはフォールバックすること
- **FR-014**: AgentCore Browser の利用ドメインを許可リストで制限できること（セキュリティ対策）

### Key Entities

- **URLGenerationRequest**: 生成リクエスト。URL、カードタイプ、生成枚数目安、保存先デッキ ID を含む
- **PageContent**: 取得したページコンテンツ。URL、タイトル、本文テキスト、メタデータ、取得方法（browser / fetch）を含む
- **GeneratedCard**: 生成されたカード。既存の Card エンティティのサブセット（front、back、references）にプレビュー状態を追加
- **BrowserSession**: AgentCore Browser のセッション情報。セッション ID、状態、タイムアウト設定を含む

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: ユーザーが URL を入力してからカードのプレビュー表示まで 60 秒以内に完了すること（公開ページの場合）
- **SC-002**: SPA ページからの生成成功率が 90% 以上であること
- **SC-003**: 生成されたカードの内容が元ページの主要ポイントを 80% 以上カバーしていること（人手評価）
- **SC-004**: 静的ページの場合、AgentCore Browser を使用せず HTTP fetch で処理する割合が 70% 以上であること（コスト最適化）
- **SC-005**: URL カード生成機能の利用率が、テキスト入力によるカード生成と同等以上であること（リリース後 1 ヶ月時点）
- **SC-006**: 生成エラー時に、ユーザーが原因を理解できるエラーメッセージが表示される割合が 95% 以上であること

## Assumptions

- Amazon Bedrock AgentCore Browser が ap-northeast-1（東京リージョン）で利用可能であること（利用不可の場合は us-west-2 等にクロスリージョンアクセス）
- AgentCore Browser のセッション単価は許容範囲内であること（静的ページへのフォールバックでコスト最適化）
- Strands Agents SDK の `AgentCoreBrowser` ツールが安定版としてリリースされていること
- 既存の AI カード生成のプロンプト設計を URL コンテンツ向けに拡張可能であること
- ページのコンテンツ取得は著作権法の範囲内でのフェアユースに該当する個人学習目的に限定すること
