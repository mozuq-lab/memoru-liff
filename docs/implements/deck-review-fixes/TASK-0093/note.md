# TASK-0093: App.tsx Provider ネスト順序修正 - 開発ノート

## タスク概要

`App.tsx` の Provider ネスト順序を設計文書に合わせて `AuthProvider > CardsProvider > DecksProvider` に修正する。
現状の Provider 順序が設計と不整合であり、レビュー指摘 M-2 に基づく修正。

### 関連要件
- REQ-201: `App.tsx` の Provider ネスト順序は `AuthProvider > CardsProvider > DecksProvider` の順であるべき

---

## 技術スタック

### フロントエンド
- React 18+ + TypeScript
- React Router v6（BrowserRouter）
- Context API（AuthProvider, CardsProvider, DecksProvider）
- Vite（開発サーバー）

### 参照元
- CLAUDE.md - フロントエンド技術スタック

---

## 開発ルール

### Provider 設計原則
参照元: `frontend/src/contexts/*.tsx` の実装スタイル

**AuthProvider**（最外層）
- ユーザー認証情報（access_token, profile）を提供
- API クライアントに access_token を注入
- すべてのページが認証情報を必要とするため最外層配置

**CardsProvider**（中層）
- カード関連のグローバルステート（cards[], dueCards[], isLoading等）を提供
- fetchCards(deckId?) / fetchDueCards(deckId?) メソッドを提供
- **重要**: DecksContext を参照しない設計（将来拡張時まで）

**DecksProvider**（内層）
- デッキ関連のグローバルステート（decks[], isLoading等）を提供
- fetchDecks() メソッドを提供
- CardsProvider より内側に配置（依存関係なし）

**Router/Layout/Routes**（最内層）
- 全 Provider の内側にネストして、すべての Context にアクセス可能にする

### ネスト順序の根拠
- **階層的依存**: 上位 Provider は下位 Provider に依存しない
- **初期化タイミング**: AuthProvider が最初に初期化され、access_token が設定された後に他の API 呼び出しが可能になる
- **スコープ**: Router/Layout は全 Context にアクセスする必要があるため最内層

---

## 関連実装

### 現在の App.tsx 実装
ファイル: `frontend/src/App.tsx`

```tsx
// 【現状】インデント不正・Provider順序確認が必要
<Router>
  <AuthProvider>
    <CardsProvider>
    <DecksProvider>
      <Layout>
        <Routes>...</Routes>
      </Layout>
    </DecksProvider>
    </CardsProvider>
  </AuthProvider>
</Router>

// 【修正後】正しいネスト順序・インデント
<Router>
  <AuthProvider>
    <CardsProvider>
      <DecksProvider>
        <Layout>
          <Routes>...</Routes>
        </Layout>
      </DecksProvider>
    </CardsProvider>
  </AuthProvider>
</Router>
```

### AuthProvider 実装パターン
ファイル: `frontend/src/contexts/AuthContext.tsx`

- createContext で AuthContext を定義
- useAuth() フック で認証ロジック（アウトソース）
- useMemo で value オブジェクトをメモ化
- useEffect で access_token を apiClient に注入

### CardsProvider 実装パターン
ファイル: `frontend/src/contexts/CardsContext.tsx`

- useState で cards[], dueCards[], isLoading, error を管理
- useCallback で fetchCards(deckId?) / fetchDueCards(deckId?) を定義（deckId パラメータは TASK-0091 で実装）
- useMemo で value オブジェクトをメモ化
- 依存配列に全プロパティを含める（メモ化最適化）

### DecksProvider 実装パターン
ファイル: `frontend/src/contexts/DecksContext.tsx`

- useState で decks[], isLoading, error を管理
- useCallback で fetchDecks(), createDeck(), updateDeck(), deleteDeck() を定義
- useMemo で value オブジェクトをメモ化
- createDeck/updateDeck/deleteDeck 後に fetchDecks() 呼び出し（状態同期）

### Context 利用パターン
ファイル: `frontend/src/pages/*.tsx` / `frontend/src/components/*.tsx`

```typescript
// 各ページ/コンポーネント内での利用
const { user, isAuthenticated } = useAuthContext();
const { cards, isLoading, fetchCards } = useCardsContext();
const { decks, fetchDecks } = useDecksContext();
```

---

## 設計文書

### アーキテクチャ設計（セクション7: Provider ネスト順序修正）
参照元: `docs/design/deck-review-fixes/architecture.md`（行290-309）

**修正内容**:
- 現状: `CardsProvider > DecksProvider`
- 修正: `AuthProvider > CardsProvider > DecksProvider`
- 根拠: 将来 DecksProvider が CardsContext を参照しない設計

**注記**: CardsProvider が DecksProvider より外側にあるのは、DecksProvider が CardsContext を参照しない設計に基づく。将来的に DecksProvider が card_count 取得のため CardsContext を参照する場合は順序変更が必要。

### 要件定義書
参照元: `docs/spec/deck-review-fixes/requirements.md`

- REQ-201（🟡黄）: `App.tsx` の Provider ネスト順序は `AuthProvider > CardsProvider > DecksProvider` の順であるべき
  - **信頼性**: 🟡 レビュー M-2・research.md から妥当な推測

### タスクファイル
参照元: `docs/tasks/deck-review-fixes/TASK-0093.md`

- **タスクタイプ**: TDD
- **推定工数**: 2時間
- **フェーズ**: Phase 3 - フロントエンド Medium/Low + 統合テスト
- **完了条件**:
  - [ ] Provider 順序が `AuthProvider > CardsProvider > DecksProvider` になっていること
  - [ ] 既存の全コンテキスト動作に影響がないこと
  - [ ] テスト: Provider 順序変更後も全ページが正常動作

---

## 注意事項

### 技術的制約

1. **React Router は Router の直下に配置**
   - Router は createBrowserHistory を使用するため、最外層に配置
   - ただし BrowserRouter をラップする形は避け、Router 内に Provider を配置

2. **Context メモ化の確認**
   - 各 Provider の useMemo が正しく依存配列を含んでいるか確認
   - Provider 再レンダリング時の不要な Context オブジェクト生成を防止

3. **useEffect の依存配列**
   - Layout / Routes 内のコンポーネント useEffect が、適切に Context 値を依存配列に含めているか確認
   - 特に useAuthContext().user / CardsContext 変更時の動作確認

### パフォーマンス考慮

- **Provider 再ネスト**: Provider ネスト順序を変更しても、各 Provider 自体の処理には影響なし（ネスト深度は1段階）
- **メモ化**: 既存実装で useMemo / useCallback が適用されているため、不要な再レンダリングは最小限
- **API 呼び出しタイミング**: App 初期化時に各 Provider が fetchDecks() 等を呼び出すかどうかはページ実装依存

### セキュリティ

- **認証フロー**: AuthProvider が最外層にあることで、API 呼び出し前に常に access_token が設定される
- **PKCE フロー**: Keycloak OIDC（PKCE）の既存フロー に影響なし

### エッジケース

1. **初期化順序**
   - AuthProvider → CardsProvider → DecksProvider の順で初期化される
   - 各 Provider 内で useEffect がある場合、初期化順序の影響を確認

2. **Context 未初期化エラー**
   - 各 useXxxContext() は Provider 内でのみ呼び出し可能
   - Routes 内のページは全 Provider 内にあるため問題なし

3. **複数 Router**
   - BrowserRouter は通常 1 つのみ
   - 複数 Router はネストさせない

---

## テスト項目（TASK-0093 完了条件）

### ユニットテスト（React Testing Library）

1. **Provider ネスト順序確認テスト**
   - AuthProvider が最外層に配置されている
   - CardsProvider が AuthProvider 内に配置されている
   - DecksProvider が CardsProvider 内に配置されている
   - Layout/Routes が DecksProvider 内に配置されている

2. **Context アクセステスト**
   - Routes 内のコンポーネントから useAuthContext() へのアクセス可能
   - Routes 内のコンポーネントから useCardsContext() へのアクセス可能
   - Routes 内のコンポーネントから useDecksContext() へのアクセス可能

3. **Provider エラーハンドリングテスト**
   - Provider 外での useAuthContext() 呼び出し時、エラー発生
   - Provider 外での useCardsContext() 呼び出し時、エラー発生
   - Provider 外での useDecksContext() 呼び出し時、エラー発生

### 統合テスト

1. **アプリケーション起動テスト**
   - App 起動時、全 Provider が正常に初期化される
   - 認証フロー（CallbackPage）が正常に動作
   - ホームページへのアクセスが正常に動作

2. **ページナビゲーションテスト**
   - "/" (ホーム) → "/decks" (デッキ一覧) へのナビゲーション
   - "/cards" (カード一覧) → "/review" (復習) へのナビゲーション
   - 各ページで Context に正常にアクセス可能

3. **Context 状態同期テスト**
   - ホームページで decks 一覧を表示
   - デッキ作成後、contexts の state が更新される
   - 複数ページ間で Context の state が同期される

### エラーケーステスト

- ネスト順序が間違っている場合、Provider 内でのみ useXxxContext() が機能
- Router が Provider 外にある場合、Routes 内で Context アクセス失敗

---

## 実装チェックリスト

### Phase 1: Provider ネスト順序修正
- [ ] `frontend/src/App.tsx` を開く
- [ ] Router 直下に AuthProvider を配置
- [ ] AuthProvider 直下に CardsProvider を配置
- [ ] CardsProvider 直下に DecksProvider を配置
- [ ] DecksProvider 直下に Layout を配置
- [ ] インデント・閉じタグを正確に修正
- [ ] ファイル保存

### Phase 2: 動作確認
- [ ] `npm run dev` で開発サーバー起動
- [ ] ブラウザで http://localhost:3000 にアクセス
- [ ] 認証フロー（Keycloak ログイン）が正常に動作
- [ ] ホームページ、デッキ一覧、カード一覧などが正常に表示
- [ ] コンソールエラーなし

### Phase 3: テスト実行
- [ ] `npm run test` で全テスト実行
- [ ] Provider ネスト関連テストすべて通過
- [ ] 既存テストすべて通過

---

## ファイルパス（相対パス）

### 対象ファイル
- `frontend/src/App.tsx` - Provider ネスト順序修正

### 参考ファイル
- `frontend/src/contexts/AuthContext.tsx` - AuthProvider 実装
- `frontend/src/contexts/CardsContext.tsx` - CardsProvider 実装
- `frontend/src/contexts/DecksContext.tsx` - DecksProvider 実装
- `frontend/src/contexts/index.ts` - Context エクスポート
- `frontend/src/components/common/Layout.tsx` - Layout コンポーネント
- `docs/design/deck-review-fixes/architecture.md` - 設計文書
- `docs/spec/deck-review-fixes/requirements.md` - 要件定義
- `docs/tasks/deck-review-fixes/TASK-0093.md` - タスク定義

---

## 信頼性レベルサマリー

- **REQ-201**: 🟡 黄信号（レビュー M-2・research.md から妥当な推測）

**品質評価**: ✅ 実装可能（設計文書・要件定義に基づく）

---

## 実装の流れ（TDD方式）

1. `/tsumiki:tdd-requirements TASK-0093` - 詳細要件定義
2. `/tsumiki:tdd-testcases` - テストケース作成
3. `/tsumiki:tdd-red` - テスト実装（失敗）
4. `/tsumiki:tdd-green` - 最小実装
5. `/tsumiki:tdd-refactor` - リファクタリング
6. `/tsumiki:tdd-verify-complete` - 品質確認
