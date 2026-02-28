# Quickstart: カード検索 (001-card-search)

## 前提条件

- Docker Desktop が起動している
- Node.js 20+ がインストールされている

## ローカル開発環境の起動

```bash
# 1. バックエンド（DynamoDB + Keycloak + SAM API）を起動
cd backend && make local-all
# → 初回は約20秒、Keycloak が起動するまで待つ

# 2. バックエンド API を起動（別ターミナル）
cd backend && make local-api
# → http://localhost:8080 でAPIが起動

# 3. フロントエンドを起動（別ターミナル）
cd frontend && npm run dev
# → http://localhost:3000 でアプリが起動
```

## テスト用ユーザーでログイン

- URL: http://localhost:3000
- ユーザー名: `test-user`
- パスワード: `test-password-123`

## 検索機能の動作確認

1. ログイン後、ナビゲーションから「カード一覧」へ遷移
2. 画面上部の検索バーにキーワードを入力
3. 入力に応じてカードがリアルタイムでフィルタリングされることを確認
4. マッチした文字列が黄色くハイライトされることを確認
5. フィルターチップ（すべて / 期日 / 学習中 / 新規）でステータスでフィルタリング
6. ソートドロップダウンでカードの並び順を変更
7. 検索バー右端の ✕ ボタンで検索をリセット

## テストの実行

```bash
cd frontend

# 全テスト実行
npm test

# 特定ファイルのみ
npx vitest run src/hooks/__tests__/useCardSearch.test.ts
npx vitest run src/components/__tests__/SearchBar.test.tsx
npx vitest run src/components/__tests__/FilterChips.test.tsx
npx vitest run src/components/__tests__/SortSelect.test.tsx
npx vitest run src/components/__tests__/HighlightText.test.tsx
npx vitest run src/pages/__tests__/CardsPage.test.tsx

# カバレッジ確認
npx vitest run --coverage
```

## 新規ファイル一覧

| ファイル                                                   | 役割                                   |
| ---------------------------------------------------------- | -------------------------------------- |
| `frontend/src/hooks/useCardSearch.ts`                      | 検索・フィルター・ソート状態管理フック |
| `frontend/src/hooks/__tests__/useCardSearch.test.ts`       | フックのユニットテスト                 |
| `frontend/src/components/SearchBar.tsx`                    | 検索バー + クリアボタン                |
| `frontend/src/components/FilterChips.tsx`                  | 復習状態フィルターチップ               |
| `frontend/src/components/SortSelect.tsx`                   | ソート順ドロップダウン                 |
| `frontend/src/components/HighlightText.tsx`                | キーワードハイライトテキスト           |
| `frontend/src/components/__tests__/SearchBar.test.tsx`     | SearchBar テスト                       |
| `frontend/src/components/__tests__/FilterChips.test.tsx`   | FilterChips テスト                     |
| `frontend/src/components/__tests__/SortSelect.test.tsx`    | SortSelect テスト                      |
| `frontend/src/components/__tests__/HighlightText.test.tsx` | HighlightText テスト                   |

## 変更ファイル一覧

| ファイル                                          | 変更内容                                                                      |
| ------------------------------------------------- | ----------------------------------------------------------------------------- |
| `frontend/src/types/card.ts`                      | `ReviewStatusFilter`, `SortByOption`, `SortOrder`, `CardFilterState` 型を追加 |
| `frontend/src/components/CardList.tsx`            | `highlightQuery?: string` props を追加、`HighlightText` を適用                |
| `frontend/src/pages/CardsPage.tsx`                | 検索・フィルター・ソート UI を追加                                            |
| `frontend/src/pages/__tests__/CardsPage.test.tsx` | 新機能のテストケースを追加                                                    |

## 停止

```bash
cd backend && make local-all-stop
```
