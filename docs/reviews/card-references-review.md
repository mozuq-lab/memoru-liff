# feature/card-references ブランチ コードレビュー

**レビュー日**: 2026-03-05
**レビュアー**: Claude (Opus 4.6) + Codex (OpenAI)
**対象ブランチ**: `feature/card-references` (6 commits, 23 files, +2589/-9 lines)

---

## レビューサマリー

| 重大度 | 件数 | 概要 |
|--------|------|------|
| Critical | 1 | API ハンドラで references がサービス層に渡されていない |
| High | 2 | Review API に references 未対応 / URL セキュリティ |
| Medium | 2 | maxItems 不一致 / label フィールド不整合 |
| Low | 1 | JSON.stringify による変更検知 |

---

## Critical

### C-1: API ハンドラで `references` がサービス層に渡されていない

**レビュアー**: Codex (Claude も検証・同意)

`backend/src/api/handlers/cards_handler.py` の `create_card` (L84-90) と `update_card` (L150-168) で、`request.references` がサービス層に渡されていない。Pydantic モデルとサービス層は対応しているが、ハンドラの受け渡し部分が未実装のため、**API 経由で references が保存されない**。

**該当箇所**:
- `cards_handler.py:84-90` — `create_card` で `references=request.references` がない
- `cards_handler.py:150-157` — `update_card` の `update_kwargs` に `references` がない

**修正方針**: 両ハンドラで `references` を引き渡す。create_card は引数追加、update_card は `update_kwargs` に追加。

---

## High

### H-1: Review API (`DueCardInfo`) に `references` フィールドがない

**レビュアー**: Codex (Claude も検証・同意)

フロントエンド ReviewPage は `currentCard.references` を参照して `ReferenceDisplay` を表示するが、バックエンドの `DueCardInfo` モデル (`backend/src/models/review.py:68`) には `references` フィールドが存在しない。そのため、実際の API レスポンスには `references` が含まれず、フロントでは常に `undefined` → `[]` となり参考情報が表示されない。

**該当箇所**:
- `backend/src/models/review.py:68-76` — `DueCardInfo` に `references` がない
- `frontend/src/pages/ReviewPage.tsx:542,608,677` — `references` を参照

**修正方針**: `DueCardInfo` に `references` フィールドを追加し、`review_service.py` の変換処理で Card の references を含めるようにする。

### H-2: URL タイプの参考情報で危険なスキーム (`javascript:` 等) を許容している

**レビュアー**: Codex (Claude も同意)

バックエンドの `Reference` モデルは `type="url"` の場合でも `value` の文字列長しか検証しない。フロントエンドの `ReferenceDisplay` は `value` をそのまま `<a href={value}>` に設定する。これにより `javascript:alert(1)` のような値が保存・表示されると XSS のリスクがある。

**該当箇所**:
- `backend/src/models/card.py:14-18` — `Reference` モデルに URL スキーム検証なし
- `frontend/src/components/ReferenceDisplay.tsx:47-54` — `href={ref.value}` を無検証で設定

**修正方針**: 以下のいずれか（または両方）を実施:
1. **フロントエンド**: `ReferenceDisplay` で `type="url"` の場合に `http://` または `https://` で始まるもののみリンク化。それ以外はテキスト表示にフォールバック
2. **バックエンド**: `Reference` モデルに `type="url"` の場合の URL バリデーション（`http(s)://` プレフィックス必須）を追加

---

## Medium

### M-1: `maxItems` のフロント/バックエンド不一致 (10 vs 5)

**レビュアー**: Codex + Claude (共通指摘)

`ReferenceEditor` のデフォルト `maxItems` は **10** (`ReferenceEditor.tsx:25`) だが、バックエンドのバリデーションは **最大5件** (`card.py:38,67`)。ユーザが UI で 6 件以上追加すると API で 400 エラーになる。

**該当箇所**:
- `frontend/src/components/ReferenceEditor.tsx:25` — `maxItems = 10`
- `backend/src/models/card.py:38` — `len(v) > 5` で拒否

**修正方針**: `ReferenceEditor` のデフォルト `maxItems` を **5** に変更する。または CardForm 側で `maxItems={5}` を明示的に渡す。

### M-2: フロントエンドの `label` フィールドがバックエンドに存在しない

**レビュアー**: Codex + Claude (共通指摘)

フロントエンドの `Reference` 型 (`frontend/src/types/card.ts:7`) には `label?: string` があり、`ReferenceDisplay` で `ref.label || ref.value` として使用されている。しかし、バックエンドの `Reference` モデル (`backend/src/models/card.py:14-18`) には `label` フィールドがない。

現状の実装ではタスク定義書 (TASK-0157) に `label` フィールドの記載があったが、実際の Pydantic モデルには含まれなかった。フロントから `label` を送信しても Pydantic の `model_dump()` で捨てられる。

**影響**:
- 現時点では `label` は UI 上で設定する手段がない（ReferenceEditor に label 入力欄がない）ため、実害なし
- ただしコードとして dead path が存在する

**修正方針**: 以下のいずれか:
1. フロントの `Reference` 型から `label` を削除（現時点で使わないなら）
2. バックエンドにも `label: Optional[str] = None` を追加して整合を取る

---

## Low

### L-1: `JSON.stringify` による変更検知

**レビュアー**: Codex + Claude (共通指摘)

`CardForm.tsx:50` で `JSON.stringify(references) !== JSON.stringify(initialReferences)` を使用して変更検知している。

**問題点**:
- 毎レンダーでシリアライズが走る（現状の最大 5 件では実質問題なし）
- オブジェクトのキー順序に依存する（Reference の構造は単純なので実質問題なし）

**修正方針**: 現時点では許容可能。パフォーマンス問題が発生した場合は dirty flag パターンに変更。

---

## 良い点

両レビュアーとも以下の点を評価:

1. **後方互換性**: 既存カード（references フィールドなし）の取り扱いが適切。`from_dynamodb_item()` で `item.get("references", [])` としており、既存データが壊れない
2. **テストカバレッジ**: モデル・サービス・コンポーネント・ページ統合まで幅広くテストが書かれている
3. **既存パターンの踏襲**: `tags` フィールドと同様のパターンで実装されており、一貫性がある
4. **DynamoDB 最適化**: 空リストを保存しない (`to_dynamodb_item` で `if self.references:` チェック)
5. **アクセシビリティ**: `aria-label` の使用、`target="_blank"` + `rel="noopener noreferrer"` の適用

---

## テストカバレッジのギャップ

| ギャップ | 詳細 |
|---------|------|
| API ハンドラ層 | `cards_handler.py` の references 受け渡しをテストするハンドラ統合テストがない（C-1 の原因） |
| Review API | `DueCardInfo` に references を含める変換のテストがない（H-1 の原因） |
| URL セキュリティ | `javascript:` 等の危険スキームを拒否するテストがない（H-2 の原因） |
| バリデーション上限 | フロント maxItems とバックエンド上限の整合性テストがない（M-1 の原因） |

---

## 修正優先度

1. **C-1**: API ハンドラの references 引き渡し（これがないと機能が動かない）
2. **H-1**: Review API への references 追加
3. **H-2**: URL セキュリティ対策
4. **M-1**: maxItems 不一致の修正
5. **M-2**: label フィールドの整理
6. **L-1**: 必要に応じて変更検知の改善
