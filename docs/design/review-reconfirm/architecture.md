# review-reconfirm アーキテクチャ設計

**作成日**: 2026-02-28
**関連要件定義**: [requirements.md](../../spec/review-reconfirm/requirements.md)
**ヒアリング記録**: [design-interview.md](design-interview.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: EARS要件定義書・設計文書・ユーザヒアリングを参考にした確実な設計
- 🟡 **黄信号**: EARS要件定義書・設計文書・ユーザヒアリングから妥当な推測による設計
- 🔴 **赤信号**: EARS要件定義書・設計文書・ユーザヒアリングにない推測による設計

---

## システム概要 🔵

**信頼性**: 🔵 *要件定義書 REQ-001~005, REQ-201, REQ-403より*

復習セッション中にquality 0-2（想起失敗）で評価されたカードを、セッション内の再確認ループに追加する機能。フロントエンドのみの変更で実装し、バックエンドAPI・データベース・SM-2アルゴリズムは変更しない。

**変更スコープ**:
- バックエンド: 変更なし 🔵
- データベース: 変更なし 🔵
- API: 変更なし 🔵
- フロントエンド: ReviewPage.tsx + GradeButtons.tsx + ReviewComplete.tsx + ReviewResultItem.tsx + 型定義 🔵

## アーキテクチャパターン 🔵

**信頼性**: 🔵 *既存review-flow設計・ヒアリング回答より*

- **パターン**: 既存のuseStateフラットパターンを維持
- **選択理由**: 既存ReviewPageの状態管理パターンと統一。再確認キュー状態の追加は2-3個のuseStateで済むため、useReducerへの移行は不要

## コンポーネント構成 🔵

**信頼性**: 🔵 *既存review-flow/architecture.md・要件定義書より*

### 変更対象コンポーネント

```
ReviewPage (状態管理の拡張)
├── ReviewProgress (変更なし)
├── ReconfirmBadge (新規: 「再確認」バッジ表示)
├── FlipCard (変更なし)
├── GradeButtons (条件分岐追加: 通常6択 vs 再確認2択)
│   ├── 通常モード: 6段階評価 + スキップ
│   └── 再確認モード: 「覚えた」「覚えていない」のみ
└── ReviewComplete (結果表示の拡張)
    └── ReviewResultItem (再確認結果の表示追加)
```

### 新規コンポーネント

#### ReconfirmBadge 🔵

**信頼性**: 🔵 *要件定義書 REQ-101より*

- **役割**: 再確認カード表示時に「再確認」バッジを表示
- **実装**: シンプルなTailwindスタイルのバッジコンポーネント
- **表示条件**: 現在のカードが再確認キュー由来の場合のみ表示

## 状態管理設計 🔵

**信頼性**: 🔵 *要件定義書 REQ-001~004, REQ-201・ヒアリング回答より*

### 追加するstate

```typescript
// 再確認キュー: quality 0-2で評価されたカード情報
const [reconfirmQueue, setReconfirmQueue] = useState<ReconfirmCard[]>([]);

// 現在のカードが再確認モードかどうか
const [isReconfirmMode, setIsReconfirmMode] = useState<boolean>(false);
```

### ReconfirmCard型 🔵

**信頼性**: 🔵 *要件定義書 REQ-001, REQ-501より*

```typescript
interface ReconfirmCard {
  cardId: string;
  front: string;
  back: string;
  originalGrade: number;  // 最初のquality値 (0, 1, or 2)
}
```

### SessionCardResult型の拡張 🔵

**信頼性**: 🔵 *要件定義書 REQ-501より*

```typescript
// 既存のSessionCardResultTypeに追加
type SessionCardResultType = 'graded' | 'skipped' | 'undone' | 'reconfirmed';

// SessionCardResultに再確認結果を追加
interface SessionCardResult {
  cardId: string;
  front: string;
  grade?: number;
  nextReviewDate?: string;
  type: SessionCardResultType;
  reconfirmResult?: 'remembered';  // 「覚えた」を選択した場合
}
```

### カード進行ロジック 🔵

**信頼性**: 🔵 *要件定義書 REQ-001~004, REQ-502より*

```
通常カード表示
  ↓
ユーザーが評価（grade 0-5）
  ↓
grade 0-2の場合:
  → SM-2 API呼び出し（interval=1, next_review_at=翌日）
  → reviewResultsに追加
  → reconfirmQueueの末尾にカードを追加
  → 次のカードへ

grade 3-5の場合:
  → SM-2 API呼び出し（通常のSM-2計算）
  → reviewResultsに追加
  → 次のカードへ（再確認キューには追加しない）

次のカード決定（moveToNext拡張）:
  → 通常カードが残っている → 次の通常カード
  → 通常カードなし & reconfirmQueue非空 → reconfirmQueueから先頭を取り出し
  → 両方なし → セッション完了
```

**重要**: 通常カードと再確認カードは同一キューで流れる（REQ-502）。実装上は通常カードを先に消化し、なくなったら再確認キューから取り出す。

### 再確認モードのハンドラ 🔵

**信頼性**: 🔵 *要件定義書 REQ-003, REQ-004より*

```typescript
// 「覚えた」ハンドラ
handleReconfirmRemembered():
  → reconfirmQueueから現在のカードを除外
  → reviewResultsの該当カードのtypeを'reconfirmed'に更新
  → reconfirmResult: 'remembered'を設定
  → API呼び出しなし
  → 次のカードへ

// 「覚えていない」ハンドラ
handleReconfirmForgotten():
  → 現在のカードをreconfirmQueueの末尾に再追加
  → API呼び出しなし
  → 次のカードへ
```

## Undo連携設計 🔵

**信頼性**: 🔵 *要件定義書 REQ-404・ヒアリングQ4回答より*

### Undoの対象

既存のUndo機能は、ReviewComplete画面でgraded結果の取り消しに使用される。再確認機能との連携:

1. **quality 0-2で評価済み → 再確認ループに入ったカード**: Undo可能
   - `undoReview` API呼び出しでSM-2を復元
   - `reviewResults`から該当結果を'undone'に変更
   - `reconfirmQueue`から該当カードを除去
   - regradeモードで再評価可能

2. **Undo後の再評価**:
   - quality 0-2で再評価 → 再び再確認キューに追加
   - quality 3-5で再評価 → 再確認キューには追加されない

### 実装方針 🟡

**信頼性**: 🟡 *既存Undo実装パターンから妥当な推測*

既存のhandleUndoをそのまま利用し、reconfirmQueueからの除去ロジックを追加する。handleGrade（regradeモード）での再確認キュー追加判定も既存ロジックの拡張で対応。

## ReviewProgress表示 🟡

**信頼性**: 🟡 *既存実装パターンから妥当な推測*

再確認カードを含めた進捗表示の方針:
- プログレスバーは**通常カードのみ**を分母とする（再確認カードは分母に含めない）
- 再確認カード表示中は「再確認」バッジで区別する
- 再確認キュー残数の表示は不要（REQ-502: フェーズ分離メッセージ不要）

## ディレクトリ構造 🔵

**信頼性**: 🔵 *既存プロジェクト構造より*

```
frontend/src/
├── pages/
│   └── ReviewPage.tsx          # 状態管理拡張（reconfirmQueue追加）
├── components/
│   ├── GradeButtons.tsx        # 再確認モード対応（2択表示）
│   ├── ReconfirmBadge.tsx      # 新規: 「再確認」バッジ
│   ├── ReviewComplete.tsx      # 再確認結果表示対応
│   └── ReviewResultItem.tsx    # 再確認結果アイコン追加
└── types/
    └── card.ts                 # SessionCardResultType拡張、ReconfirmCard追加
```

## 非機能要件の実現方法

### パフォーマンス 🔵

**信頼性**: 🔵 *要件定義書 NFR-001, NFR-002より*

- 再確認キューはフロントエンドメモリ内で完結（API呼び出しなし）
- 配列操作（push/shift）のみで状態更新するため、通常カードと同等の応答速度

### ユーザビリティ 🟡

**信頼性**: 🟡 *要件定義書 NFR-201, NFR-202から妥当な推測*

- 「覚えた」「覚えていない」ボタンは既存GradeButtonsと同様の44px以上タップ領域
- 再確認バッジはカード上部に表示し、通常復習と明確に区別

## 技術的制約 🔵

**信頼性**: 🔵 *要件定義書 REQ-401~403より*

- SM-2アルゴリズムの計算ロジックを変更しない
- バックエンドAPIの変更を行わない
- 再確認ループの回数に上限を設けない

## 関連文書

- **データフロー**: [dataflow.md](dataflow.md)
- **要件定義**: [requirements.md](../../spec/review-reconfirm/requirements.md)
- **ユーザストーリー**: [user-stories.md](../../spec/review-reconfirm/user-stories.md)
- **受け入れ基準**: [acceptance-criteria.md](../../spec/review-reconfirm/acceptance-criteria.md)
- **既存設計**: [review-flow/architecture.md](../review-flow/architecture.md)
- **既存Undo設計**: [review-undo/architecture.md](../review-undo/architecture.md)

## 信頼性レベルサマリー

- 🔵 青信号: 14件 (82%)
- 🟡 黄信号: 3件 (18%)
- 🔴 赤信号: 0件 (0%)

**品質評価**: ✅ 高品質
