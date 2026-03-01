# コードレビュー: d3a30fe → 0f1df22

**レビュー日**: 2026-03-01
**レビュアー**: Claude Opus 4.6 + OpenAI Codex (MCP)
**対象コード**: 現在のコードベース（レビュー未実施区間の変更に関わる部分）

## レビュー対象の変更概要

| 機能領域 | タスク | 主な変更ファイル |
|----------|--------|------------------|
| ローカル開発環境 | TASK-0048〜0051 | Makefile, docker-compose.yaml, env.json |
| AI Strands Migration | TASK-0052〜0065 | ai_service.py, strands_service.py, bedrock.py, prompts/ |
| 復習フロー UI | TASK-0066〜0072 | FlipCard, GradeButtons, ReviewPage 等 |
| 復習取り消し (Undo) | TASK-0073〜0077 | review_service.py, ReviewResultItem |
| 復習間隔調整 | TASK-0078〜0080 | card_service.py, CardDetailPage |
| バグ修正 | - | total_due_count, TransactWriteItems 等 |

---

## サマリー

| 重大度 | 件数 |
|--------|------|
| Critical | 1 |
| High | 8 |
| Medium | 8 |
| Low | 6 |
| Info | 2 |
| **合計** | **25** |

---

## Critical

### CR-01: 開発環境 JWT フォールバックの署名未検証

**ファイル**: `backend/src/api/handler.py:70-78`, `backend/src/api/shared.py:45-53`
**発見者**: Claude, Codex（両者一致）

`ENVIRONMENT=dev` 時、JWT の署名検証を一切行わずに Base64 デコードのみで `sub` を抽出している。

```python
# handler.py:74-78
token = auth_header.split(" ", 1)[1]
payload = token.split(".")[1]
payload += "=" * (4 - len(payload) % 4)
decoded = json.loads(base64.urlsafe_b64decode(payload))
return decoded.get("sub")
```

**リスク**:
- 環境変数の誤設定やデプロイミスで本番環境に影響する可能性
- 任意の `sub` を埋め込んだトークンで認証バイパス可能
- `handler.py` と `shared.py` で同一ロジックが二重実装されており、片方の修正が漏れるリスク

**議論**:
- Codex: 「設定ミス時に認証バイパスリスク」として [High] に分類
- Claude: 同一ロジックの二重実装も指摘し、[Critical] に引き上げ
- **合意**: ローカル限定を意図しているが、本番流出時のインパクトが大きく [Critical] が妥当

**推奨対応**:
1. `handler.py` の `_get_user_id_from_event` から重複ロジックを削除し `shared.py` に統一
2. 環境変数チェックの強化（例: `AWS_SAM_LOCAL` 環境変数との組み合わせ）
3. ログに警告メッセージを出力して、dev フォールバックが発動したことを明示

---

## High

### H-01: get_due_cards の全件取得 + ページネーション未対応

**ファイル**: `backend/src/services/card_service.py:496-538`, `backend/src/services/review_service.py:422-430`
**発見者**: Claude, Codex（両者一致）

`deck_id` フィルタのために `limit=None` で全カードを取得しているが、DynamoDB Query は 1MB 上限がある。`LastEvaluatedKey` による後続ページの取得処理が実装されていないため、カード数が多い場合にデータ欠落が発生する。

```python
# review_service.py:428-430
all_due_cards = self.card_service.get_due_cards(
    user_id=user_id,
    limit=None,  # 全件取得を意図するがページネーションなし
)
```

**リスク**:
- `total_due_count` が実際のカード数より少なく表示される
- ユーザーのカード数が増えるとレイテンシ・コスト増大

**推奨対応**:
- `card_service.get_due_cards` にページネーションループを追加（`limit=None` 時）
- 長期的には `deck_id` に対応する GSI の追加を検討

---

### H-02: review_history の read-modify-write が非原子的

**ファイル**: `backend/src/services/review_service.py:305-312,330-351`（submit_review）、`205-256`（undo_review）
**発見者**: Claude, Codex（両者一致）

`review_history` の更新が「読み取り → 変更 → 書き戻し」の 3 ステップで行われており、並行リクエスト時にロストアップデートが発生する。

```python
# 1. review_historyを読み取り
response = self.cards_table.get_item(
    Key={"user_id": user_id, "card_id": card_id},
    ProjectionExpression="review_history",
)
existing_history = response.get("Item", {}).get("review_history", [])

# 2. メモリ上で変更
updated_history = add_review_history(existing_history, history_entry)

# 3. 書き戻し（この間に他のリクエストが割り込む可能性）
self.cards_table.update_item(
    UpdateExpression="SET review_history = :review_history",
    ...
)
```

**推奨対応**:
- DynamoDB の `list_append` を使ったアトミック追加に変更
- Undo 側は `ConditionExpression` で楽観的ロックを実装

---

### H-03: strands_service.py の例外ハンドリング重複

**ファイル**: `backend/src/services/strands_service.py:149-173, 303-327, 431-455`
**発見者**: Claude（Codex は未指摘）

3 つのメソッド（`generate_cards`, `grade_answer`, `get_learning_advice`）で同一の例外マッピングロジックが完全重複している。

**推奨対応**:
```python
from contextlib import contextmanager

@contextmanager
def _handle_agent_errors():
    try:
        yield
    except AIServiceError:
        raise
    except TimeoutError as e:
        raise AITimeoutError(f"Agent timed out: {e}") from e
    # ... 以下同様
```

---

### H-04: f-string によるロガー呼び出し（構造化ログ未活用）

**ファイル**: `backend/src/api/handler.py:115,148,157,173,187,201,211,234`、`backend/src/api/shared.py:43,55`、`backend/src/services/card_service.py:189`
**発見者**: Claude（Codex は未指摘）

AWS Lambda Powertools の Logger で構造化ログを使用せず f-string で文字列連結している。

```python
# NG: f-string
logger.info(f"Grade AI request: card_id={card_id}, user_id={user_id}")

# OK: 構造化ログ
logger.info("Grade AI request", extra={"card_id": card_id, "user_id": user_id})
```

**リスク**:
- ログインジェクション（user_id 等に制御文字が含まれる場合）
- CloudWatch Logs Insights での検索・フィルタリングが困難

---

### H-05: _record_review のサイレントエラー握りつぶし

**ファイル**: `backend/src/services/review_service.py:389-392`
**発見者**: Claude, Codex（両者一致、Codex は Undo が reviews_table を巻き戻さない問題と関連付け）

```python
except ClientError as e:
    # Log error but don't fail the review
    # Reviews table is for analytics, not critical
    pass  # ← ログ出力なし
```

**推奨対応**: `pass` を `logger.warning(...)` に変更。同様に `card_service.py:387-388` の reviews cleanup も。

---

### H-06: grade_answer で GRADING_SYSTEM_PROMPT が未設定

**ファイル**: `backend/src/services/strands_service.py:287`
**発見者**: Claude（Codex は未指摘）

`get_learning_advice` では `ADVICE_SYSTEM_PROMPT` を設定しているが、`grade_answer` では設定なし。

```python
# grade_answer 内
agent = Agent(model=self.model)  # system_prompt なし

# get_learning_advice 内（正しい）
agent = Agent(model=self.model, system_prompt=ADVICE_SYSTEM_PROMPT)
```

`generate_cards` も同様に `system_prompt` 未設定。採点精度・生成品質に影響する可能性がある。

---

### H-07: CardsContext の型不整合（DueCard → Card ダミー変換）

**ファイル**: `frontend/src/contexts/CardsContext.tsx:26-39`
**発見者**: Claude（Codex は未指摘）

`dueCardToCard` で `user_id: ''`, `interval: 0`, `ease_factor: 0` などのダミー値を持つ `Card` オブジェクトに変換している。

```typescript
const dueCardToCard = (due: DueCard): Card => ({
  card_id: due.card_id,
  user_id: '',     // ダミー
  interval: 0,     // ダミー
  ease_factor: 0,  // ダミー
  repetitions: 0,  // ダミー
  ...
});
```

**推奨対応**: `CardList` が `DueCard[]` も受け入れるよう型を調整するか、union 型を使用する。

---

### H-08: undo_review の二重読み込みと reviews_table 未巻き戻し

**ファイル**: `backend/src/services/review_service.py:200-211`（二重読み込み）、`237-256`（reviews_table 未対応）
**発見者**: Claude（二重読み込み）, Codex（reviews_table 未巻き戻し）

1. `get_card` と `get_item(review_history)` で同一カードを 2 回読み取り
2. Undo 時に `cards_table` のみ復元し、`reviews_table` のレコードは残存（学習統計に影響）

**推奨対応**:
- 1 回の GetItem で必要なデータを全て取得
- reviews_table からの対応レコード削除を追加（もしくは仕様として明文化）

---

## Medium

### M-01: 401 リフレッシュの無限再帰リスク

**ファイル**: `frontend/src/services/api.ts:50-66`
**発見者**: Claude, Codex（両者一致）

リフレッシュ成功後に `this.request<T>()` を再帰呼び出し。リフレッシュ後も 401 が返る場合（アカウント停止等）に無限再帰。

**推奨対応**: 再試行フラグ（`_retried`）を導入して 1 回のみ再試行に制限。

---

### M-02: ReviewPage でのレンダー中 setState

**ファイル**: `frontend/src/pages/ReviewPage.tsx:388-391`
**発見者**: Claude, Codex（両者一致）

```typescript
if (!regradeCard) {
  setRegradeCardIndex(null);  // レンダー中の setState
  setIsComplete(true);
  return null;
}
```

React のアンチパターン。`useEffect` に移動すべき。

---

### M-03: delete_card のレビュー削除にページネーションなし

**ファイル**: `backend/src/services/card_service.py:378-388`
**発見者**: Claude, Codex（両者一致）

DynamoDB Query は 1MB 上限があるが、ページネーション処理がない。大量レビューがあるカードで残骸が残る。

---

### M-04: get_review_summary の全件取得

**ファイル**: `backend/src/services/review_service.py:525-550`
**発見者**: Claude（Codex は未指摘）

ユーザーの全レビュー履歴と全カードを DynamoDB から取得。長期利用ユーザーでコスト・レイテンシ問題。

**推奨対応**: 直近 N 日分に絞り込むか、集計テーブルで事前計算。

---

### M-05: bedrock.py の重複データクラス定義

**ファイル**: `backend/src/services/bedrock.py:57-73`
**発見者**: Claude（Codex は未指摘）

`ai_service.py` に既に存在する `GeneratedCard`, `GenerationResult` と同名のデータクラスが `bedrock.py` にも定義されている。Protocol の型チェックで不整合が生じうる。

**推奨対応**: `bedrock.py` の重複定義を削除し、`ai_service.py` から import。

---

### M-06: _get_next_due_date が将来日のみを取得しない

**ファイル**: `backend/src/services/review_service.py:488-500`
**発見者**: Claude（Codex は未指摘）

```python
KeyConditionExpression="user_id = :user_id",  # next_review_at > now の条件なし
```

「次回復習日」を取得する目的だが、既に期限切れのカードを返す可能性がある。

**推奨対応**: `KeyConditionExpression` に `next_review_at > :now` 条件を追加。ただし、`get_due_cards` で due_cards が空だったから呼ばれるため、厳密には期限切れカードは存在しないはず。全カードが復習済みで将来日のカードのみ残っている前提であれば現状でも動作する。**確認推奨**。

---

### M-07: reconfirmQueue の依存によるコールバック再生成

**ファイル**: `frontend/src/pages/ReviewPage.tsx:105-179`
**発見者**: Claude（Codex は未指摘）

`handleGrade` が `reconfirmQueue` をクロージャでキャプチャしており、`useCallback` 依存配列に含まれるため、キュー更新のたびにコールバックが再生成される。

**推奨対応**: `useRef` でキューの最新値を参照するか、`setReconfirmQueue` の updater パターンを活用。

---

### M-08: link_line の check-then-update が非原子的

**ファイル**: `backend/src/services/user_service.py:149-176`
**発見者**: Codex（Claude は未指摘）
**補足**: この部分は対象コミット範囲での変更量は少ない（4行）が、既存コードの問題として指摘

`get_user_by_line_id` → `update_item` の間に別リクエストが割り込むと、同一 LINE ID が複数ユーザーに紐づく可能性がある。

**推奨対応**: `ConditionExpression` で原子的に更新するか、TransactWriteItems を使用。

---

## Low

### L-01: ReviewRequest の重複バリデーション

**ファイル**: `backend/src/models/review.py:12-19`
**発見者**: Claude（Codex は未指摘）

`Field(ge=0, le=5)` と `@field_validator` で同一のバリデーション。Pydantic の `ge`/`le` が先に評価されるため `@field_validator` は実質不到達。

---

### L-02: GradeButtons の onGrade が isReconfirmMode 時に未使用

**ファイル**: `frontend/src/components/GradeButtons.tsx:22-52`
**発見者**: Claude（Codex は未指摘）

`isReconfirmMode=true` 時に `onGrade` は使用されないが必須プロパティ。discriminated union 型の使用を推奨。

---

### L-03: ReviewResultItem の絵文字アクセシビリティ

**ファイル**: `frontend/src/components/ReviewResultItem.tsx:44,59`
**発見者**: Claude（Codex は未指摘）

`↩` や `✔` がスクリーンリーダーで意図しない読み上げになる。`aria-hidden="true"` + `sr-only` テキストを推奨。

---

### L-04: OllamaModel=None 時のエラーメッセージ不明瞭

**ファイル**: `backend/src/services/strands_service.py:20-23,84-87`
**発見者**: Claude（Codex は未指摘）

`ollama` パッケージ未インストール環境で `dev` モード実行時、`TypeError: 'NoneType' object is not callable` が発生。ユーザーフレンドリーなエラーメッセージを出すべき。

---

### L-05: ReviewComplete の displayCount フォールバックロジック

**ファイル**: `frontend/src/components/ReviewComplete.tsx:20-21`
**発見者**: Claude（Codex は未指摘）

`gradedCount` が 0 の場合に `reviewedCount` にフォールバックする意図が不明確。全スキップ時の表示が期待通りかの確認を推奨。

---

### L-06: Undo ボタンの並行発火

**ファイル**: `frontend/src/components/ReviewComplete.tsx:42`, `frontend/src/components/ReviewResultItem.tsx:75`
**発見者**: Codex（Claude は未指摘）

Undo 中の `disabled` が対象行のみに適用されるため、他行の Undo ボタンが押せる状態。並行 Undo API 呼び出しが発生しうる。

**推奨対応**: `isUndoing` を全ボタンに伝搬して、Undo 中は全てのボタンを無効化。

---

## Info

### I-01: runtime_checkable が未使用

**ファイル**: `backend/src/services/ai_service.py:109`
**発見者**: Claude（Codex は未指摘）

`@runtime_checkable` を付与しているが `isinstance(service, AIService)` の使用箇所がない。

---

### I-02: cards と dueCards のキャッシュ整合性

**ファイル**: `frontend/src/contexts/CardsContext.tsx`
**発見者**: Claude（Codex は未指摘）

`cards` と `dueCards` が独立 state で管理されており、片方の更新が他方に反映されない。現状は許容範囲だが、将来的に `useMemo` + フィルタリングパターンへの移行を検討。

---

## レビュアー間の合意・相違まとめ

### 両レビュアーが一致した指摘（7件）

| # | 指摘 | 重大度 |
|---|------|--------|
| CR-01 | JWT dev フォールバック | Critical |
| H-01 | get_due_cards ページネーション | High |
| H-02 | review_history 非原子的更新 | High |
| M-01 | 401 無限再帰 | Medium |
| M-02 | render 中 setState | Medium |
| M-03 | delete_card レビュー削除 | Medium |
| H-08 | undo reviews_table 未巻き戻し | High |

### Claude のみが指摘（14件）
H-03(例外重複), H-04(f-string), H-05(エラー握りつぶし), H-06(system_prompt), H-07(型不整合), M-04(全件取得), M-05(重複定義), M-06(_get_next_due_date), M-07(コールバック再生成), L-01〜L-05, I-01〜I-02

### Codex のみが指摘（2件）
M-08(link_line 非原子的), L-06(Undo 並行発火)

### 重大度の相違
| 指摘 | Claude | Codex | 採用 |
|------|--------|-------|------|
| JWT フォールバック | Critical | High | **Critical**（本番流出時の影響大） |
| get_due_cards 全件取得 | Critical | High | **High**（現状 MAX_CARDS_PER_USER=2000 で 1MB 超えは稀） |

---

## 対応優先度ガイド

### 即時対応推奨
1. **CR-01**: JWT フォールバックのログ出力追加 + 二重実装統合
2. **H-06**: `grade_answer`/`generate_cards` への system_prompt 追加（機能バグ）
3. **M-02**: レンダー中 setState の useEffect 移動

### 次スプリントで対応推奨
4. **H-03**: strands_service.py エラーハンドリング共通化
5. **H-05**: サイレントエラー握りつぶしへのログ追加
6. **H-01**: get_due_cards ページネーション追加
7. **M-01**: 401 リフレッシュ再試行制限
8. **M-05**: bedrock.py 重複データクラス削除

### 中期的に検討
9. **H-02**: review_history の原子的更新
10. **H-04**: 構造化ログへの移行
11. **H-07**: CardsContext 型整理
12. **M-04**: get_review_summary の効率化
