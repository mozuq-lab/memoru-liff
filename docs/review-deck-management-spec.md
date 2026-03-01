# `feature/deck-management-spec` ブランチ 統合レビュー

> **レビュワー**: Claude (claude-4.6-opus), Codex
> **レビュー日**: 2026-02-28
> **ブランチ**: `feature/deck-management-spec` (10 commits, 77 files, +8,903 lines)

---

## 総合評価

スペック策定（requirements → research → design → tasks）から実装・テストまで一貫したプロセスで進められており、既存アーキテクチャとの整合性も高い。ただし **ビルド不能のバグ（Critical）**と**機能要件未達の問題（High）**が複数あるため、マージ前に必ず修正が必要。

---

## 指摘一覧（重大度順）

### Critical

#### C-1: フロントエンドがビルド不能 — `DecksProvider` の未エクスポート

| 項目 | 内容 |
|------|------|
| 発見者 | Codex |
| 対象 | `frontend/src/contexts/index.ts` |
| 影響 | `tsc` / ビルド時にインポートエラーでビルド不能 |

**問題**: `App.tsx` で `@/contexts` から `DecksProvider` をインポートしているが、`contexts/index.ts` に再エクスポートが存在しない。

```typescript
// frontend/src/contexts/index.ts — 現状
export { AuthProvider, useAuthContext } from './AuthContext';
export { CardsProvider, useCardsContext } from './CardsContext';
// ← DecksProvider, useDecksContext の export が欠落
```

```typescript
// frontend/src/App.tsx — インポート側
import { AuthProvider, CardsProvider, DecksProvider } from '@/contexts';
```

**修正案**: `contexts/index.ts` に以下を追加:

```typescript
export { DecksProvider, useDecksContext } from './DecksContext';
```

---

### High

#### H-1: デッキカードからの遷移で `deck_id` フィルタが機能しない

| 項目 | 内容 |
|------|------|
| 発見者 | Codex |
| 対象 | `frontend/src/pages/CardsPage.tsx` |
| 影響 | 要件 4.3「デッキタップでカード一覧遷移」が実質的に機能しない |

**問題**: `DecksPage` / `DeckSummary` は `/cards?deck_id=xxx` に遷移するが、`CardsPage` 側で `deck_id` クエリパラメータを読み取っておらず、`fetchCards()` もデッキ指定なしで実行される。結果として全カードが表示され、デッキ別一覧にならない。

```typescript
// DecksPage.tsx — 遷移元
navigate(`/cards?deck_id=${deck.deck_id}`)

// CardsPage.tsx — 遷移先（deck_id を参照していない）
useEffect(() => {
  if (activeTab === 'due') {
    fetchDueCards();
  } else {
    fetchCards();  // ← deck_id フィルタなし
  }
}, [activeTab, fetchCards, fetchDueCards]);
```

**修正案**: `CardsPage` で `searchParams.get('deck_id')` を取得し、`fetchCards(deckId)` でフィルタリングされたカード一覧を取得する。バックエンドの `GET /cards?deck_id=xxx` は既に対応済み。

---

#### H-2: カードを「未分類」に戻せない — `deck_id` の null 解除が不可能

| 項目 | 内容 |
|------|------|
| 発見者 | Codex（Claude も関連指摘あり — 後述 M-3） |
| 対象 | `frontend/src/pages/CardDetailPage.tsx`, `backend/src/services/card_service.py` |
| 影響 | 一度デッキに割り当てたカードを「未分類」に戻せない |

**問題**: フロントエンドからバックエンドまでの3段階で `null` が消失する。

1. **フロントエンド (`CardDetailPage`)**: `deckId ?? undefined` で `null` → `undefined` に変換
2. **型定義 (`UpdateCardRequest`)**: `deck_id?: string`（`null` を許容しない）
3. **バックエンド (`card_service.py`)**: `if deck_id is not None` のため、`deck_id` が渡されない場合は更新されない

```typescript
// CardDetailPage.tsx
const updatedCard = await cardsApi.updateCard(id, { deck_id: deckId ?? undefined });
// ↑ deckId が null のとき undefined になり、JSON.stringify で deck_id キー自体が消える
```

```python
# card_service.py
if deck_id is not None:  # ← deck_id が渡されないと更新されない
    update_parts.append("deck_id = :deck_id")
```

**修正案**:
1. `UpdateCardRequest` の型を `deck_id?: string | null` に変更
2. `CardDetailPage` で `null` をそのまま渡す（`?? undefined` を削除）
3. バックエンドで `deck_id` が `null` の場合は `REMOVE deck_id` を実行する

---

### Medium

#### M-1: `GET /cards/due?deck_id=xxx` の `total_due_count` が過少になる

| 項目 | 内容 |
|------|------|
| 発見者 | Codex, Claude（同一指摘） |
| 対象 | `backend/src/services/review_service.py` |
| 影響 | フロントエンドに表示される復習対象カード総数が正確でない |

**問題**: `get_due_cards()` は先に `limit` 付きで全 due カードを取得してから `deck_id` でフィルタリングする。`total_due_count` はフィルタ後の `len(due_card_infos)` で計算されるため、`limit` によってカットされた分が含まれず、実際の総件数より少なくなる。

```python
# 1. limit 付きで全 due カードを取得
due_cards = self.card_service.get_due_cards(user_id=user_id, limit=limit, ...)

# 2. deck_id でフィルタ（limit 後のリストから絞り込み）
if deck_id is not None:
    due_cards = [c for c in due_cards if c.deck_id == deck_id]

# 3. total_due_count がフィルタ後のリスト長 = 不正確
if deck_id is not None:
    total_due_count = len(due_card_infos)  # ← limit で切られた後の数
```

**修正案**: `deck_id` 指定時は `limit` なしで全 due カードを取得してからフィルタリングし、その後で `limit` を適用する。または、Cards テーブルに対して `deck_id` 付きの `Select=COUNT` クエリを別途実行する。

---

#### M-2: `App.tsx` の Provider ネスト順序が設計と不整合

| 項目 | 内容 |
|------|------|
| 発見者 | Claude |
| 対象 | `frontend/src/App.tsx` |
| 影響 | 動作に問題はないが、設計意図との乖離 |

**問題**: `research.md` に「`CardsProvider` と同階層に配置」と記載があるが、実際のコードでは `DecksProvider` が `CardsProvider` の内側にネストされている。また、閉じタグのインデントも不統一。

```tsx
<CardsProvider>
<DecksProvider>     {/* ← CardsProvider の内側 */}
  ...
</DecksProvider>
</CardsProvider>    {/* ← インデント不統一 */}
```

**修正案**: 設計通り並列にするか、依存関係を考慮して意図的にネストするならその旨を設計ドキュメントに反映する。

---

#### M-3: `UpdateDeckRequest` の description/color フィールドのクリア操作が曖昧

| 項目 | 内容 |
|------|------|
| 発見者 | Claude |
| 対象 | `backend/src/models/deck.py`, `backend/src/services/deck_service.py` |
| 影響 | 「説明を削除したい」「カラーをリセットしたい」操作の意図が伝わらない |

**問題**: `UpdateDeckRequest` の `description` / `color` は `Optional[str]` だが、`None`（未指定 = 更新しない）と空文字列（クリアしたい）の区別がつかない。`DeckService.update_deck` は `if description is not None` で判定し、`Deck.to_dynamodb_item` は `if self.description:` で falsy チェックするため、空文字列を送ると保存されず次回読み出し時に `None` になる。動作はするが意図が不明瞭。

**修正案**: API 設計として「`null` を送ったらフィールドをクリアする」というセマンティクスを明示的に定義し、ドキュメントに記載する。

---

#### M-4: `DeckFormModal` の edit モードで不要な更新が発生する可能性

| 項目 | 内容 |
|------|------|
| 発見者 | Claude |
| 対象 | `frontend/src/components/DeckFormModal.tsx` |
| 影響 | 変更していないフィールドもサーバーに送信される可能性 |

**問題**: edit モードの差分チェックで:
- `description`: 元が `null` の場合、`'' !== (null ?? '')` → `'' !== ''` → false（OK だが、空文字が入力された場合の挙動が M-3 と絡む）
- `color`: `undefined !== (null ?? undefined)` → `undefined !== undefined` → false（OK）

ただし、`color` が元々 `undefined`（API から `null` で返却）の場合、`deck?.color ?? undefined` は `undefined` だが、ユーザーがカラーパレットで何も選択しなくても `color` state が `undefined` のままなので、差分なしと判定される。**現状では問題ないが**、カラーを一度選択してから「なし」に戻す操作をした場合、`color` が `undefined` になり差分ありと判定されて空の更新リクエストが送られる。

---

#### M-5: `get_deck_card_counts` / `get_deck_due_counts` が全カードをスキャン

| 項目 | 内容 |
|------|------|
| 発見者 | Claude |
| 対象 | `backend/src/services/deck_service.py` |
| 影響 | カード数が多い場合にレスポンス時間が増加 |

**問題**: ユーザーの全カード（最大 2000 枚）を `ProjectionExpression: "deck_id"` で取得してメモリ上でカウントしている。`design.md` で「パフォーマンスが問題になった場合は Decks テーブルに `card_count` カラムを追加」と言及済み。

**現状の評価**: MVP としては許容範囲内。デッキ数最大 50 に対してカード総数最大 2000 の Scan は DynamoDB の 1MB 読み取り制限内に収まる。ただし、将来的にはデッキ別の `Select=COUNT` + `FilterExpression` の並列実行、またはカウンタカラムの導入を検討すべき。

---

### Low

#### L-1: `DeckSelector` / `DeckSummary` の `'unassigned'` フィルタリングが不要

| 項目 | 内容 |
|------|------|
| 発見者 | Claude |
| 対象 | `frontend/src/components/DeckSelector.tsx`, `DeckSummary.tsx` |
| 影響 | なし（防御的コーディング） |

**問題**: `decks.filter((d) => d.deck_id !== 'unassigned')` というフィルタがあるが、バックエンドから `deck_id: 'unassigned'` のデッキが返される実装は存在しない。混乱を招く可能性がある。

---

#### L-2: `handler.py` の肥大化

| 項目 | 内容 |
|------|------|
| 発見者 | Claude |
| 対象 | `backend/src/api/handler.py` |
| 影響 | 保守性の低下（約 950 行） |

**問題**: `research.md` でも言及されているが、デッキ CRUD の追加で約 150 行増加し約 950 行に。`design.md` で「プロジェクト規約に完全準拠」とされているが、将来的にはドメイン別ファイル分割を検討すべき。

---

#### L-3: コメントスタイルの不統一

| 項目 | 内容 |
|------|------|
| 発見者 | Claude |
| 対象 | フロントエンドコンポーネント全般 |
| 影響 | コードの統一感 |

**問題**: `DeckSelector.tsx` / `DeckSummary.tsx` には `【機能概要】`・`【実装方針】` の JSDoc コメントがあるが、`DeckFormModal.tsx` / `DecksPage.tsx` にはない。

---

#### L-4: `CardDetailPage` のデッキ変更後にコンテキストが陳腐化

| 項目 | 内容 |
|------|------|
| 発見者 | Claude |
| 対象 | `frontend/src/pages/CardDetailPage.tsx` |
| 影響 | デッキの `card_count` / `due_count` が古いまま |

**問題**: カードのデッキ変更後に `DecksContext.fetchDecks()` を呼んでいないため、`card_count` / `due_count` が更新されない。別画面に遷移すれば再取得されるため実用上の問題は小さい。

---

## 良い点

### 設計・プロセス
- **スペック駆動の開発**: EARS 形式の Acceptance Criteria、要件トレーサビリティマトリクスが完備
- **調査の文書化**: `research.md` で既存コードベースの調査結果と設計判断の根拠を丁寧に記録
- **設計判断の透明性**: `design.md` に Alternatives Considered / Trade-offs を明記

### バックエンド
- **既存パターンとの一貫性**: handler → service → model のレイヤード構造を忠実に踏襲
- **DI 対応**: `DeckService` は `dynamodb_resource` を外部注入可能でテスタブル
- **ベストエフォートの設計**: `_reset_cards_deck_id` がカード単位のエラーハンドリング（ログ記録付き）を実施
- **DynamoDB の予約語対応**: `name` を `ExpressionAttributeNames` で適切にエスケープ
- **Pydantic バリデーション**: 名前長制限、HEX カラーコード正規表現、大文字正規化

### フロントエンド
- **UX の配慮**: プリセットカラーパレット、文字数カウンター、送信中の disabled 制御
- **アクセシビリティ**: `aria-label`、`aria-hidden`、`min-w-[44px] min-h-[44px]` のタッチターゲット
- **状態管理**: `useCallback` / `useMemo` による適切なメモ化パターン
- **デッキ別復習**: `ReviewPage` の `deck_id` クエリパラメータ対応が自然に統合

### テスト
- **バックエンド**: モデル 27 テスト、サービス 25 テスト（moto モック）、ハンドラー 14 テスト
- **フロントエンド**: Context 11 テスト、コンポーネント 17 テスト、ページ 14 テスト
- **テスト設計**: バリデーション境界値、エラーケース、空状態を網羅

### インフラ
- **template.yaml**: 既存テーブルと同じセキュリティ設定（PITR, SSE/KMS, DeletionProtection）
- **docker-compose.yaml**: ローカル開発用テーブル作成コマンドの追加
- **IAM ポリシー**: `DynamoDBCrudPolicy` を適切に追加

---

## 修正優先度まとめ

| 優先度 | ID | 概要 | マージブロック |
|--------|-----|------|:-----------:|
| Critical | C-1 | `DecksProvider` 未エクスポート（ビルド不能） | Yes |
| High | H-1 | `CardsPage` で `deck_id` フィルタ未対応 | Yes |
| High | H-2 | カードを「未分類」に戻せない | Yes |
| Medium | M-1 | `total_due_count` が過少 | Recommended |
| Medium | M-2 | Provider ネスト順序の不整合 | No |
| Medium | M-3 | フィールドクリア操作の曖昧さ | No |
| Medium | M-4 | edit モードの不要な更新 | No |
| Medium | M-5 | 全カードスキャンのパフォーマンス | No |
| Low | L-1〜L-4 | スタイル・保守性の改善 | No |

**結論**: C-1, H-1, H-2 の修正が必須。M-1 も可能であれば対応推奨。それ以外は後続タスクとして対応可。
