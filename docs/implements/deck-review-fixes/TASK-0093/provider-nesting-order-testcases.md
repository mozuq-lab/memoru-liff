# TASK-0093: App.tsx Provider ネスト順序修正 - テストケース定義書

## テストケース作成対象の情報

機能名: provider-nesting-order
タスクID: TASK-0093
要件名: deck-review-fixes
出力ファイル名: provider-nesting-order-testcases.md

---

## テストファイル

- `frontend/src/__tests__/App.test.tsx`

---

### 1. 正常系テストケース

#### TC-APP-001: App コンポーネントが正常にレンダリングされること 🔵

- **テスト名**: App コンポーネントの正常レンダリング
  - **何をテストするか**: Provider ネスト順序修正後、App コンポーネントがエラーなくレンダリングされること
  - **期待される動作**: App() がクラッシュせずに DOM を生成する
- **入力値**: なし（App コンポーネントをレンダリング）
  - **入力データの意味**: デフォルト状態でのアプリケーション起動を検証
- **期待される結果**: エラーなくレンダリングされ、Layout 要素が DOM に存在する
  - **期待結果の理由**: 正しい Provider ネスト順序であれば、全 Provider が初期化されてレンダリングが成功する
- **テストの目的**: Provider 順序変更後のリグレッション防止
  - **確認ポイント**: render() がエラーをスローしないこと
- 🔵 REQ-201・TASK-0093 完了条件「Provider 順序変更後も全ページが正常動作」に基づく

#### TC-APP-002: 全 Context にページ内からアクセス可能であること 🔵

- **テスト名**: Context アクセス可能性確認
  - **何をテストするか**: Routes 内のコンポーネントから `useAuthContext()`, `useCardsContext()`, `useDecksContext()` がアクセス可能であること
  - **期待される動作**: テスト用コンポーネントから各 Context のプロパティを取得でき、undefined でないこと
- **入力値**: App 内に配置されたテスト用コンポーネント
  - **入力データの意味**: 実際のページコンポーネントが Context にアクセスするパターンを模擬
- **期待される結果**: 各 Context の値（isLoading, decks 等）が取得でき、Provider 外エラーが発生しないこと
  - **期待結果の理由**: 全 Provider が正しくネストされていれば、内側のコンポーネントは全 Context にアクセス可能
- **テストの目的**: TASK-0093 完了条件「既存の全コンテキスト動作に影響がないこと」の検証
  - **確認ポイント**: useAuthContext, useCardsContext, useDecksContext それぞれが値を返すこと
- 🔵 TASK-0093 完了条件・note.md「Context アクセステスト」に基づく

#### TC-APP-003: 既存ルーティングが正常に動作すること 🟡

- **テスト名**: ルーティング正常動作確認
  - **何をテストするか**: Provider 順序変更後もルーティング定義が正しく機能し、各パスに対応するページがレンダリングされること
  - **期待される動作**: "/" パスで HomePage がレンダリングされること
- **入力値**: MemoryRouter の initialEntries に "/" を指定
  - **入力データの意味**: 最も基本的なルーティングパスで動作確認
- **期待される結果**: HomePage のコンテンツ（Memoru タイトル等）が表示されること
  - **期待結果の理由**: Provider 順序を変更してもルーティング定義には影響しないことを確認
- **テストの目的**: Provider 順序変更による副作用がないことの確認
  - **確認ポイント**: Route 定義と Layout ラッピングが正しく機能すること
- 🟡 TASK-0093 完了条件から妥当な推測

---

### 2. 異常系テストケース

なし。

**理由**: このタスクは Provider ネスト順序の修正であり、新たなエラーハンドリングロジックは追加しない。各 Provider の外からの Context アクセスエラーは既存の `AuthContext.test.tsx`, `CardsContext.test.tsx`, `DecksContext.test.tsx` で検証済み。

---

### 3. 境界値テストケース

なし。

**理由**: このタスクは JSX 構造変更のみであり、数値や文字列の境界値は存在しない。

---

### 4. 開発言語・フレームワーク

- **プログラミング言語**: TypeScript
  - **言語選択の理由**: プロジェクト全体で TypeScript を使用（CLAUDE.md 参照）
  - **テストに適した機能**: 型安全なモック、型によるテストコードの品質保証
- **テストフレームワーク**: Vitest + React Testing Library
  - **フレームワーク選択の理由**: プロジェクトの既存テスト（`CardsContext.test.tsx`, `DecksContext.test.tsx` 等）で使用されているフレームワーク
  - **テスト実行環境**: `cd frontend && npm run test` (Vitest)
- 🔵 既存テストファイルの実装パターンに基づく

---

### 5. テストケース実装時の日本語コメント指針

```typescript
/**
 * 【テスト目的】: Provider ネスト順序修正後の App コンポーネントの正常動作を確認
 * 【テスト内容】: AuthProvider > CardsProvider > DecksProvider の順序で全 Context にアクセス可能
 * 【期待される動作】: App がエラーなくレンダリングされ、各 Context が正しく提供される
 * 🔵 青信号: TASK-0093・REQ-201 に基づく
 */
```

#### モック戦略

既存テストパターン（`HomePage.test.tsx` 等）に準拠:

```typescript
// 【テスト前準備】: 各 Context のモック設定
// AuthContext - useAuth をモック
vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

// CardsContext - cardsApi をモック
vi.mock('@/services/api', () => ({
  apiClient: { setAccessToken: vi.fn() },
  cardsApi: { getCards: vi.fn(), getDueCards: vi.fn(), getDueCount: vi.fn() },
  decksApi: { getDecks: vi.fn(), createDeck: vi.fn(), updateDeck: vi.fn(), deleteDeck: vi.fn() },
}));
```

---

### 6. 要件定義との対応関係

- **参照した機能概要**: 要件定義書セクション1「機能の概要」 - Provider ネスト順序を設計文書に準拠させる
- **参照した入力・出力仕様**: 要件定義書セクション2「修正後の Provider 構造」 - AuthProvider > CardsProvider > DecksProvider
- **参照した制約条件**: 要件定義書セクション3「互換性要件」 - 全ページが全 Context にアクセス可能であること
- **参照した使用例**: 要件定義書セクション4.1「基本使用パターン」 - 全 Provider 正常初期化

---

### テストケースとタスク完了条件の対応

| 完了条件 | テストケース |
|---------|------------|
| Provider 順序が `AuthProvider > CardsProvider > DecksProvider` | TC-APP-001（レンダリング成功 = 正しい Provider 構造） |
| 既存の全コンテキスト動作に影響がないこと | TC-APP-002（全 Context アクセス可能確認） |
| Provider 順序変更後も全ページが正常動作 | TC-APP-003（ルーティング正常動作確認） |

---

## 信頼性レベルサマリー

| テストケース | レベル | 根拠 |
|------------|--------|------|
| TC-APP-001 | 🔵 | TASK-0093 完了条件・REQ-201 |
| TC-APP-002 | 🔵 | TASK-0093 完了条件・note.md テスト項目 |
| TC-APP-003 | 🟡 | TASK-0093 完了条件から妥当な推測 |
| 技術選択 | 🔵 | 既存テストパターンに準拠 |

- **総テストケース数**: 3件
- 🔵 **青信号**: 2件 (67%)
- 🟡 **黄信号**: 1件 (33%)
- 🔴 **赤信号**: 0件 (0%)
