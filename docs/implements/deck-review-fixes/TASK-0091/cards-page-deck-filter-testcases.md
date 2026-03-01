# TASK-0091: CardsPage deck_id フィルタ対応 - テストケース定義

**タスクID**: TASK-0091
**要件名**: deck-review-fixes
**機能名**: CardsPage deck_id フィルタ対応
**作成日**: 2026-03-01

---

## テスト対象ファイル

| 対象ファイル | テストファイル |
|-------------|--------------|
| `frontend/src/contexts/CardsContext.tsx` | `frontend/src/__tests__/CardsContext.test.tsx` |
| `frontend/src/pages/CardsPage.tsx` | `frontend/src/pages/__tests__/CardsPage.test.tsx` |
| `frontend/src/services/api.ts` | `frontend/src/services/__tests__/api.test.ts`（必要に応じて） |

---

## 1. 正常系テストケース

### TC-091-001: deck_id 指定時に fetchCards に deckId が渡される（CardsContext）

- **テスト名**: deck_id 指定時に fetchCards が deckId パラメータ付きで API を呼び出す
  - **何をテストするか**: `fetchCards(deckId)` が `cardsApi.getCards(deckId)` を正しく呼び出すこと
  - **期待される動作**: API 呼び出しに deckId 文字列が引数として渡される
- **入力値**: `deckId = 'deck-abc-123'`
  - **入力データの意味**: 既存のデッキを表す UUID 形式の文字列
- **期待される結果**: `cardsApi.getCards('deck-abc-123')` が呼び出される。返却されたカードが `cards` ステートにセットされる
  - **期待結果の理由**: fetchCards に渡された deckId が API レイヤーに正しく伝搬されることを保証する
- **テストの目的**: CardsContext の fetchCards パラメータ追加が正しく動作すること
  - **確認ポイント**: getCards の引数に deckId が含まれること、返却データが cards にセットされること
- 🔵 青信号: architecture.md セクション6・既存 CardsContext 実装・requirements REQ-001 に基づく

### TC-091-002: deck_id 未指定時に fetchCards が従来動作を維持する（CardsContext）

- **テスト名**: deck_id 未指定で fetchCards を呼ぶと全カードを取得する
  - **何をテストするか**: `fetchCards()` を引数なしで呼んだ際、従来通り全カードが取得されること
  - **期待される動作**: `cardsApi.getCards(undefined)` が呼ばれ、全カードが返される
- **入力値**: `deckId = undefined`（引数なし）
  - **入力データの意味**: deck_id フィルタなし = 全カード取得
- **期待される結果**: `cardsApi.getCards(undefined)` または `cardsApi.getCards()` が呼ばれる。全カードが cards にセットされる
  - **期待結果の理由**: 後方互換性を維持し、既存の呼び出し箇所で従来通り全カード表示を保証
- **テストの目的**: 後方互換性の確認（REQ-102）
  - **確認ポイント**: 引数なしの呼び出しで既存動作が壊れないこと
- 🔵 青信号: REQ-102・既存 CardsContext 実装パターンに基づく

### TC-091-003: deck_id 指定時に fetchDueCards に deckId が渡される（CardsContext）

- **テスト名**: deck_id 指定時に fetchDueCards が deckId パラメータ付きで API を呼び出す
  - **何をテストするか**: `fetchDueCards(deckId)` が `cardsApi.getDueCards(undefined, deckId)` を正しく呼び出すこと
  - **期待される動作**: API 呼び出しに deckId が渡され、該当デッキの復習対象カードが返される
- **入力値**: `deckId = 'deck-abc-123'`
  - **入力データの意味**: デッキ別復習対象カードの取得を想定
- **期待される結果**: `cardsApi.getDueCards(undefined, 'deck-abc-123')` が呼ばれる。返却された due_cards が dueCards にセットされる
  - **期待結果の理由**: fetchDueCards に渡された deckId が getDueCards API に正しく伝搬されることを保証する
- **テストの目的**: CardsContext の fetchDueCards パラメータ追加が正しく動作すること
  - **確認ポイント**: getDueCards の引数に deckId が含まれること
- 🔵 青信号: architecture.md セクション6・既存 getDueCards 実装（deckId パラメータ対応済み）に基づく

### TC-091-004: deck_id 未指定時に fetchDueCards が従来動作を維持する（CardsContext）

- **テスト名**: deck_id 未指定で fetchDueCards を呼ぶと全復習対象カードを取得する
  - **何をテストするか**: `fetchDueCards()` を引数なしで呼んだ際、従来通り全復習対象カードが取得されること
  - **期待される動作**: `cardsApi.getDueCards()` が呼ばれ、全復習対象カードが返される
- **入力値**: `deckId = undefined`（引数なし）
  - **入力データの意味**: フィルタなしの復習対象カード取得
- **期待される結果**: `cardsApi.getDueCards()` が呼ばれる。全 due_cards が dueCards にセットされる
  - **期待結果の理由**: 後方互換性の維持
- **テストの目的**: fetchDueCards の後方互換性の確認
  - **確認ポイント**: 引数なしの呼び出しで既存動作が壊れないこと
- 🔵 青信号: REQ-102・既存 getDueCards 実装に基づく

### TC-091-005: CardsPage で deck_id クエリパラメータを読み取り fetchCards に渡す

- **テスト名**: URL に deck_id パラメータがある場合に fetchCards(deckId) が呼ばれる
  - **何をテストするか**: CardsPage が `useSearchParams()` で `deck_id` を読み取り、`fetchCards(deckId)` を呼ぶこと
  - **期待される動作**: `/cards?deck_id=deck-abc-123` でアクセスした際、`fetchCards('deck-abc-123')` が呼ばれる
- **入力値**: URL = `/cards?deck_id=deck-abc-123`
  - **入力データの意味**: デッキ一覧からの遷移を想定したクエリパラメータ
- **期待される結果**: `mockFetchCards` が `'deck-abc-123'` を引数として呼び出される
  - **期待結果の理由**: URL クエリパラメータが正しくパースされ Context に渡されることを保証
- **テストの目的**: CardsPage → CardsContext の deckId 伝搬確認（REQ-001）
  - **確認ポイント**: useSearchParams で deck_id を正しく取得していること
- 🔵 青信号: REQ-001・architecture.md セクション6・dataflow.md フロー1 に基づく

### TC-091-006: CardsPage で deck_id 未指定時に fetchCards() が引数なしで呼ばれる

- **テスト名**: URL に deck_id がない場合に fetchCards() が引数なしで呼ばれる
  - **何をテストするか**: `/cards` でアクセスした際の従来動作維持
  - **期待される動作**: `fetchCards()` が引数なし（undefined）で呼ばれる
- **入力値**: URL = `/cards`（deck_id なし）
  - **入力データの意味**: Navigation バーからのカード一覧遷移
- **期待される結果**: `mockFetchCards` が引数なし（undefined）で呼び出される
  - **期待結果の理由**: deck_id 未指定時の後方互換性
- **テストの目的**: 従来動作の維持確認（REQ-102）
  - **確認ポイント**: deck_id パラメータがない場合に全カード取得が行われること
- 🔵 青信号: REQ-102・既存 CardsPage 動作に基づく

### TC-091-007: deck_id 指定時にページヘッダーにデッキ名が表示される

- **テスト名**: deck_id 指定時にヘッダーにデッキ名が表示される
  - **何をテストするか**: `deck_id` が指定され、DecksContext にそのデッキが存在する場合、ヘッダーにデッキ名が表示されること
  - **期待される動作**: ヘッダー部分に「英語基礎」などのデッキ名が表示される
- **入力値**: URL = `/cards?deck_id=deck-abc-123`、DecksContext.decks にデッキ名「英語基礎」のデッキが存在
  - **入力データの意味**: デッキが正常に読み込まれた状態での表示確認
- **期待される結果**: `data-testid="cards-title"` 要素に「英語基礎」が含まれる
  - **期待結果の理由**: ユーザーがどのデッキのカードを表示しているか視覚的に確認できるようにする
- **テストの目的**: デッキ名ヘッダー表示の確認（REQ-101）
  - **確認ポイント**: DecksContext から正しいデッキ名を検索して表示していること
- 🟡 黄信号: REQ-101 から妥当な推測（表示方法の詳細は要件で一部未定義）

### TC-091-008: deck_id 未指定時にヘッダーが「カード一覧」のまま

- **テスト名**: deck_id 未指定時にヘッダーが「カード一覧」を表示する
  - **何をテストするか**: `deck_id` がない場合に従来の「カード一覧」ヘッダーが表示されること
  - **期待される動作**: ヘッダーに「カード一覧」が表示される
- **入力値**: URL = `/cards`（deck_id なし）
  - **入力データの意味**: 従来のカード一覧画面アクセス
- **期待される結果**: `data-testid="cards-title"` 要素に「カード一覧」が表示される
  - **期待結果の理由**: 後方互換性。既存のUIを維持
- **テストの目的**: 従来ヘッダー表示の維持確認
  - **確認ポイント**: 既存テスト（テストケース1）と同等の確認
- 🔵 青信号: 既存 CardsPage 実装・REQ-102 に基づく

### TC-091-009: deck_id 指定時に復習対象タブでも deckId が維持される

- **テスト名**: deck_id 指定時にタブを「復習対象」に切り替えても deck_id フィルタが維持される
  - **何をテストするか**: `/cards?deck_id=xxx` でタブを「復習対象」に切り替えた際、`fetchDueCards(deckId)` が呼ばれること
  - **期待される動作**: タブ切り替え後も deck_id パラメータが保持され、fetchDueCards に deckId が渡される
- **入力値**: URL = `/cards?deck_id=deck-abc-123`、タブ = 'due'
  - **入力データの意味**: デッキ別表示中のタブ切り替え操作
- **期待される結果**: `mockFetchDueCards` が `'deck-abc-123'` を引数として呼び出される
  - **期待結果の理由**: タブ切り替え時に deck_id パラメータが失われないことを保証
- **テストの目的**: タブ切り替え時の deck_id 保持確認（TC-001-03）
  - **確認ポイント**: setSearchParams でタブ変更時に deck_id が保持されること
- 🟡 黄信号: TC-001-03 から妥当な推測（既存 setActiveTab の実装が deck_id をクリアする可能性を考慮）

### TC-091-010: API レイヤー getCards に deckId パラメータが渡される

- **テスト名**: getCards(deckId) が deck_id クエリパラメータ付きで API を呼び出す
  - **何をテストするか**: `apiClient.getCards(deckId)` がリクエスト URL に `?deck_id=xxx` を含めること
  - **期待される動作**: `GET /cards?deck_id=deck-abc-123` のリクエストが発行される
- **入力値**: `deckId = 'deck-abc-123'`
  - **入力データの意味**: デッキフィルタ付きのカード取得リクエスト
- **期待される結果**: fetch が `/cards?deck_id=deck-abc-123` を含む URL で呼び出される
  - **期待結果の理由**: バックエンド API が deck_id クエリパラメータでフィルタリングする仕様のため
- **テストの目的**: API レイヤーの getCards メソッド修正確認
  - **確認ポイント**: URLSearchParams で正しくクエリ文字列が構築されること
- 🔵 青信号: api.ts 既存実装パターン（getDueCards の deckId 対応と同様）に基づく

### TC-091-011: API レイヤー getCards(undefined) でクエリパラメータなし

- **テスト名**: getCards() を引数なしで呼ぶとクエリパラメータなしで API を呼び出す
  - **何をテストするか**: `apiClient.getCards()` が `/cards` のみの URL でリクエストすること
  - **期待される動作**: `GET /cards` のリクエストが発行される（クエリ文字列なし）
- **入力値**: `deckId = undefined`（引数なし）
  - **入力データの意味**: 全カード取得のリクエスト
- **期待される結果**: fetch が `/cards` のみの URL で呼び出される
  - **期待結果の理由**: 後方互換性。既存の getCards() 呼び出しが影響を受けないこと
- **テストの目的**: API レイヤーの後方互換性確認
  - **確認ポイント**: deckId が undefined の場合にクエリ文字列が追加されないこと
- 🔵 青信号: 既存 api.ts 実装・getDueCards のパターンに基づく

---

## 2. 異常系テストケース

### TC-091-E01: 存在しない deck_id の場合に空のカード一覧が表示される

- **テスト名**: 存在しない deck_id で空のカード一覧が表示される
  - **エラーケースの概要**: URL に存在しないデッキの deck_id が指定された場合
  - **エラー処理の重要性**: ブックマークや外部リンクから無効なデッキにアクセスする可能性がある
- **入力値**: URL = `/cards?deck_id=nonexistent-deck`、API が空のカード配列を返す
  - **不正な理由**: 該当するデッキが存在しない、またはカードが0件
  - **実際の発生シナリオ**: ブックマークしたURLのデッキが削除された場合
- **期待される結果**: `data-testid="empty-state"` 要素が表示され、「カードがありません」メッセージが表示される
  - **エラーメッセージの内容**: 通常の空状態表示と同じ（エラーではなく空状態）
  - **システムの安全性**: アプリがクラッシュせず、正常な空状態を表示する
- **テストの目的**: 存在しないデッキへの安全なフォールバック確認（EDGE-003）
  - **品質保証の観点**: 不正な入力に対するユーザー体験の維持
- 🟡 黄信号: EDGE-003 から妥当な推測

### TC-091-E02: deck_id 指定時にデッキ名が DecksContext に存在しない場合のフォールバック

- **テスト名**: DecksContext にデッキ情報がない場合のヘッダー表示フォールバック
  - **エラーケースの概要**: deck_id は URL に存在するが DecksContext.decks にそのデッキが見つからない場合
  - **エラー処理の重要性**: ダイレクトアクセスや DecksContext 初期化前のケースに対応する必要がある
- **入力値**: URL = `/cards?deck_id=deck-abc-123`、DecksContext.decks = []（空配列）
  - **不正な理由**: DecksContext がまだロードされていない、またはデッキが削除された
  - **実際の発生シナリオ**: ブラウザで直接 URL を入力した場合やデッキ削除後のアクセス
- **期待される結果**: ヘッダーにフォールバック表示（「カード一覧」またはデッキ名なしの表示）。アプリがクラッシュしない
  - **エラーメッセージの内容**: 不要なエラー表示は行わない
  - **システムの安全性**: undefined のプロパティアクセスでクラッシュしないこと
- **テストの目的**: DecksContext 未ロード時の安全なフォールバック確認
  - **品質保証の観点**: ダイレクトアクセスやタイミング問題への耐性
- 🟡 黄信号: REQ-201・note.md 注意事項より妥当な推測

### TC-091-E03: API エラー時のエラー表示（deck_id 指定時）

- **テスト名**: deck_id 指定時に API エラーが発生した場合にエラー表示される
  - **エラーケースの概要**: fetchCards(deckId) 呼び出し時に API がエラーを返す場合
  - **エラー処理の重要性**: ネットワークエラーやサーバーエラー時のユーザー体験
- **入力値**: URL = `/cards?deck_id=deck-abc-123`、CardsContext.error = new Error('API Error')
  - **不正な理由**: API が 500 エラーやネットワークエラーを返す
  - **実際の発生シナリオ**: サーバーダウンやネットワーク切断時
- **期待される結果**: 「カードの取得に失敗しました」エラーメッセージが表示される
  - **エラーメッセージの内容**: 既存のエラー表示パターンと同一
  - **システムの安全性**: エラーがハンドリングされ、再取得ボタンが表示される
- **テストの目的**: deck_id 指定時でもエラーハンドリングが正常に動作すること
  - **品質保証の観点**: 既存のエラーハンドリングがフィルタ追加で壊れないこと
- 🔵 青信号: 既存 CardsPage エラー表示パターンに基づく

---

## 3. 境界値テストケース

### TC-091-B01: deck_id が空文字列の場合

- **テスト名**: deck_id が空文字列の場合は全カードが表示される
  - **境界値の意味**: `?deck_id=` のように値なしのクエリパラメータが指定された場合
  - **境界値での動作保証**: 空文字列は undefined と同等に扱われるべき
- **入力値**: URL = `/cards?deck_id=`
  - **境界値選択の根拠**: searchParams.get('deck_id') は空文字列 `''` を返すケースがある
  - **実際の使用場面**: URL の手動編集やブラウザの自動補完
- **期待される結果**: fetchCards が引数なし（undefined）で呼ばれ、全カードが表示される
  - **境界での正確性**: 空文字列を falsy として扱い、フィルタなしと同等に動作
  - **一貫した動作**: deck_id なしの場合と同一の動作
- **テストの目的**: 空文字列の deck_id が適切にハンドリングされること
  - **堅牢性の確認**: 不正な入力に対する防御的プログラミング
- 🟡 黄信号: 一般的なクエリパラメータ処理のベストプラクティスから妥当な推測

### TC-091-B02: deck_id と tab パラメータの共存

- **テスト名**: deck_id と tab=due の両方が指定された場合に正しくフィルタされる
  - **境界値の意味**: 複数のクエリパラメータが同時に指定された場合の動作
  - **境界値での動作保証**: 両方のフィルタが同時に適用される
- **入力値**: URL = `/cards?deck_id=deck-abc-123&tab=due`
  - **境界値選択の根拠**: デッキ別表示で復習対象タブを初期表示する場合
  - **実際の使用場面**: DecksPage から「復習する」リンクで遷移する可能性
- **期待される結果**: `mockFetchDueCards` が `'deck-abc-123'` を引数として呼び出される。activeTab が 'due' で表示される
  - **境界での正確性**: deck_id と tab の両方が正しくパースされて利用される
  - **一貫した動作**: 個別に指定した場合と同じ動作
- **テストの目的**: 複数クエリパラメータの組み合わせ動作確認
  - **堅牢性の確認**: パラメータの組み合わせによる予期しない動作がないこと
- 🟡 黄信号: TC-001-03・既存 useSearchParams 実装パターンから妥当な推測

### TC-091-B03: タブ切り替え時に deck_id パラメータが保持される

- **テスト名**: タブ切り替え後も URL の deck_id パラメータが保持される
  - **境界値の意味**: setSearchParams によるタブ切り替えが deck_id を上書きしないこと
  - **境界値での動作保証**: 既存の setActiveTab 実装が deck_id を削除しないよう修正が必要
- **入力値**: 初期 URL = `/cards?deck_id=deck-abc-123`、タブを「復習対象」に切り替え
  - **境界値選択の根拠**: 既存の setActiveTab は `setSearchParams({ tab: 'due' })` のように全パラメータを置き換える実装のため、deck_id が失われる可能性がある
  - **実際の使用場面**: デッキ別カード一覧でタブを切り替える操作
- **期待される結果**: タブ切り替え後の URL が `?deck_id=deck-abc-123&tab=due` のように deck_id を維持する
  - **境界での正確性**: setSearchParams の呼び出しで deck_id が保持される
  - **一貫した動作**: ユーザーのデッキフィルタ意図が失われない
- **テストの目的**: setActiveTab の deck_id 保持修正の検証
  - **堅牢性の確認**: 既存のパラメータ操作ロジックとの整合性
- 🟡 黄信号: 既存 setActiveTab 実装（setSearchParams で全パラメータ置換）から妥当な推測。修正が必要な箇所

---

## 4. 開発言語・フレームワーク

- **プログラミング言語**: TypeScript
  - **言語選択の理由**: プロジェクト全体で TypeScript を使用。型安全性によりパラメータ追加の影響範囲を検出可能
  - **テストに適した機能**: 型推論によるモックの整合性チェック、インターフェース変更の検出
- **テストフレームワーク**: Vitest + React Testing Library
  - **フレームワーク選択の理由**: 既存テスト（CardsPage.test.tsx、CardsContext.test.tsx）で使用済み。プロジェクト標準
  - **テスト実行環境**: `cd frontend && npx vitest run`、MemoryRouter でルーティングをモック
- 🔵 青信号: 既存テストファイルの技術スタック確認済み

---

## 5. テストケース実装時の日本語コメント指針

### テストファイル: `frontend/src/pages/__tests__/CardsPage.test.tsx`（追記）

#### describe ブロック構造

```typescript
describe('TASK-0091: deck_id フィルタ対応', () => {
  describe('deck_id 指定時のカード取得', () => {
    // TC-091-005, TC-091-006
  });

  describe('deck_id 指定時のヘッダー表示', () => {
    // TC-091-007, TC-091-008
  });

  describe('タブ切り替え時の deck_id 保持', () => {
    // TC-091-009, TC-091-B02, TC-091-B03
  });

  describe('エッジケース', () => {
    // TC-091-E01, TC-091-E02, TC-091-E03, TC-091-B01
  });
});
```

#### テストケース開始時のコメント

```typescript
// 【テスト目的】: deck_id クエリパラメータによるカードフィルタが正しく動作すること
// 【テスト内容】: URL に deck_id=xxx がある場合、fetchCards(deckId) が呼ばれることを確認
// 【期待される動作】: fetchCards が指定された deckId 引数付きで呼び出される
// 🔵 青信号: REQ-001・architecture.md セクション6
```

#### Given（準備フェーズ）のコメント

```typescript
// 【テストデータ準備】: DecksContext にデッキ情報をセット（デッキ名検索用）
// 【初期条件設定】: MemoryRouter の initialEntries に deck_id パラメータ付き URL をセット
// 【前提条件確認】: CardsContext と DecksContext のモックが初期化済み
```

#### When（実行フェーズ）のコメント

```typescript
// 【実際の処理実行】: CardsPage コンポーネントをレンダリング
// 【処理内容】: useSearchParams で deck_id を読み取り、useEffect で fetchCards を実行
// 【実行タイミング】: コンポーネントマウント時に自動的にフェッチが実行される
```

#### Then（検証フェーズ）のコメント

```typescript
// 【結果検証】: fetchCards が deckId 引数付きで呼ばれたことを確認
// 【期待値確認】: mockFetchCards.toHaveBeenCalledWith('deck-abc-123')
// 【品質保証】: URL パラメータから Context への deckId 伝搬の正確性を保証
```

#### セットアップのコメント

```typescript
beforeEach(() => {
  // 【テスト前準備】: モック関数のクリア、Context 初期状態の設定
  // 【環境初期化】: cards, dueCards を空配列、isLoading=false, error=null にリセット
  vi.clearAllMocks();
  mockCardsContext.cards = [];
  mockCardsContext.dueCards = [];
  mockCardsContext.isLoading = false;
  mockCardsContext.error = null;
});
```

### テストファイル: `frontend/src/__tests__/CardsContext.test.tsx`（追記）

#### describe ブロック構造

```typescript
describe('TASK-0091: fetchCards/fetchDueCards deckId パラメータ', () => {
  describe('fetchCards(deckId) パラメータ伝搬', () => {
    // TC-091-001, TC-091-002
  });

  describe('fetchDueCards(deckId) パラメータ伝搬', () => {
    // TC-091-003, TC-091-004
  });
});
```

---

## 6. 要件定義との対応関係

### 参照した機能概要
- 要件定義書 セクション1「機能の概要」: CardsPage に URL クエリパラメータ `deck_id` によるフィルタ機能を追加
- architecture.md セクション6: CardsPage deck_id フィルタの実装概要

### 参照した入力・出力仕様
- 要件定義書 セクション2「入力・出力の仕様」: deck_id パラメータの型・ソース・制約
- 要件定義書 セクション2「CardsContext インターフェース変更」: fetchCards/fetchDueCards のシグネチャ変更

### 参照した制約条件
- 要件定義書 セクション3「アーキテクチャ制約」: Context パターン維持、後方互換性
- 要件定義書 セクション3「useSearchParams の制約」: setSearchParams 互換、useEffect 依存配列

### 参照した使用例
- 要件定義書 セクション4「基本パターン1〜3」: デッキ別カード一覧表示、全カード表示、デッキ別復習対象タブ
- 要件定義書 セクション4「エッジケース1〜2」: 存在しない deck_id、DecksContext 未ロード

### テストケースと要件の対応表

| テストケース | 対応要件 | 信頼性 |
|-------------|---------|--------|
| TC-091-001 | REQ-001 | 🔵 |
| TC-091-002 | REQ-102 | 🔵 |
| TC-091-003 | REQ-001 | 🔵 |
| TC-091-004 | REQ-102 | 🔵 |
| TC-091-005 | REQ-001, dataflow フロー1 | 🔵 |
| TC-091-006 | REQ-102 | 🔵 |
| TC-091-007 | REQ-101 | 🟡 |
| TC-091-008 | REQ-102 | 🔵 |
| TC-091-009 | TC-001-03 | 🟡 |
| TC-091-010 | REQ-001, api.ts パターン | 🔵 |
| TC-091-011 | REQ-102, api.ts パターン | 🔵 |
| TC-091-E01 | EDGE-003 | 🟡 |
| TC-091-E02 | REQ-201, note.md | 🟡 |
| TC-091-E03 | 既存エラーパターン | 🔵 |
| TC-091-B01 | 防御的プログラミング | 🟡 |
| TC-091-B02 | TC-001-03 | 🟡 |
| TC-091-B03 | setActiveTab 修正 | 🟡 |

---

## 信頼性レベルサマリー

| カテゴリ | 🔵 青信号 | 🟡 黄信号 | 🔴 赤信号 |
|---------|-----------|-----------|-----------|
| 正常系 (TC-091-001〜011) | 9 | 2 | 0 |
| 異常系 (TC-091-E01〜E03) | 1 | 2 | 0 |
| 境界値 (TC-091-B01〜B03) | 0 | 3 | 0 |
| 技術スタック | 1 | 0 | 0 |
| **合計** | **11** | **7** | **0** |

- 🔵 青信号: 11項目 (61%)
- 🟡 黄信号: 7項目 (39%)
- 🔴 赤信号: 0項目 (0%)

**品質評価**: ✅ 高品質 - 全テストケースが要件定義・既存実装に基づいており、赤信号なし。黄信号は主にUI表示詳細とタブ切り替え時のパラメータ保持に関するもので、実装時に確認可能な範囲。
