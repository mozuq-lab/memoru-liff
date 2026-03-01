# TASK-0093: App.tsx Provider ネスト順序修正 - 要件定義書

## TDD用要件整理

機能名: provider-nesting-order
タスクID: TASK-0093
要件名: deck-review-fixes
出力ファイル名: provider-nesting-order-requirements.md

---

### 1. 機能の概要

- 🔵 **何をする機能か**: `App.tsx` の React Context Provider ネスト順序を `AuthProvider > CardsProvider > DecksProvider` に修正する。現状は `CardsProvider` と `DecksProvider` が正しくネストされておらず（インデント不正・階層不整合）、設計文書と不一致。
- 🔵 **どのような問題を解決するか**: Provider の階層構造を設計文書に準拠させることで、将来的な Context 間依存関係の追加（例: DecksProvider が CardsContext を参照する場合）に備え、正しい初期化順序を保証する。
- 🟡 **想定されるユーザー**: 開発者（Provider 構造の保守性向上）。エンドユーザーには直接的な影響なし。
- 🔵 **システム内での位置づけ**: フロントエンドアプリケーションのルート構成（`App.tsx`）。全ページコンポーネントが Provider ツリー内にネストされる。
- **参照した EARS 要件**: REQ-201
- **参照した設計文書**: architecture.md セクション7「Provider ネスト順序修正」

---

### 2. 入力・出力の仕様

- 🔵 **入力**: なし（コード構造の変更であり、ランタイム入力は変わらない）
- 🔵 **出力**: なし（Provider 順序変更後も各ページの Context アクセスパターンは同一）
- 🔵 **変更対象ファイル**: `frontend/src/App.tsx`

#### 現在の Provider 構造（誤）

```tsx
<Router>
  <AuthProvider>
    <CardsProvider>
    <DecksProvider>      {/* CardsProvider の子ではなく兄弟になっている */}
      <Layout>
        <Routes>...</Routes>
      </Layout>
    </DecksProvider>
    </CardsProvider>
  </AuthProvider>
</Router>
```

#### 修正後の Provider 構造（正）

```tsx
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

- **参照した EARS 要件**: REQ-201
- **参照した設計文書**: architecture.md セクション7、note.md「関連実装」セクション

---

### 3. 制約条件

- 🔵 **互換性要件**: 既存の全ページコンポーネントが `useAuthContext()`, `useCardsContext()`, `useDecksContext()` に引き続きアクセスできること。
- 🔵 **アーキテクチャ制約**: Provider ネスト順序は `AuthProvider > CardsProvider > DecksProvider`。DecksProvider は CardsContext を参照しない設計に基づく（architecture.md セクション7）。
- 🟡 **パフォーマンス要件**: Provider 再ネストによるパフォーマンス影響なし。各 Provider は useMemo/useCallback でメモ化済み。
- 🔵 **セキュリティ要件**: AuthProvider が最外層にあることで、API 呼び出し前に常に access_token が設定される既存動作を維持。
- **参照した EARS 要件**: REQ-201
- **参照した設計文書**: architecture.md セクション7、note.md「注意事項」セクション

---

### 4. 想定される使用例

#### 4.1 基本的な使用パターン 🔵

- **正常ケース**: App 起動時に `AuthProvider > CardsProvider > DecksProvider` の順で初期化され、Routes 内の全ページから全 Context にアクセス可能。

#### 4.2 エッジケース 🟡

- **初期化順序**: AuthProvider が最初に初期化され、access_token 設定後に CardsProvider / DecksProvider が API 呼び出し可能になる。
- **Context 未初期化**: 各 `useXxxContext()` は対応する Provider 内でのみ呼び出し可能。Routes は全 Provider 内にあるため問題なし。

#### 4.3 エラーケース 🟡

- **Provider 外からの Context アクセス**: Provider ツリー外から `useXxxContext()` を呼ぶとエラー発生。修正後もこの動作は変わらない。

- **参照した EARS 要件**: REQ-201
- **参照した設計文書**: note.md「エッジケース」セクション

---

### 5. EARS 要件・設計文書との対応関係

- **参照したユーザストーリー**: なし（内部リファクタリング）
- **参照した機能要件**: REQ-201
- **参照した非機能要件**: なし
- **参照した Edge ケース**: なし
- **参照した受け入れ基準**: TASK-0093 完了条件（Provider 順序、既存動作維持、テスト通過）
- **参照した設計文書**:
  - **アーキテクチャ**: architecture.md セクション7「Provider ネスト順序修正（REQ-201 / M-2）」
  - **型定義**: なし（JSX 構造変更のみ）
  - **データベース**: なし
  - **API 仕様**: なし

---

## 信頼性レベルサマリー

| 項目 | レベル | 根拠 |
|------|--------|------|
| 機能概要 | 🔵 | REQ-201・architecture.md セクション7 |
| 入出力仕様 | 🔵 | 現在の App.tsx 実装から確認 |
| 互換性制約 | 🔵 | TASK-0093 完了条件 |
| パフォーマンス | 🟡 | note.md から妥当な推測 |
| 基本使用パターン | 🔵 | 設計文書準拠 |
| エッジケース | 🟡 | note.md から妥当な推測 |

- **総項目数**: 6項目
- 🔵 **青信号**: 4項目 (67%)
- 🟡 **黄信号**: 2項目 (33%)
- 🔴 **赤信号**: 0項目 (0%)
