# review-flow アーキテクチャ設計

**作成日**: 2026-02-25
**関連要件定義**: [requirements.md](../../spec/review-flow/requirements.md)
**ヒアリング記録**: [design-interview.md](design-interview.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: EARS要件定義書・設計文書・ユーザヒアリングを参考にした確実な設計
- 🟡 **黄信号**: EARS要件定義書・設計文書・ユーザヒアリングから妥当な推測による設計
- 🔴 **赤信号**: EARS要件定義書・設計文書・ユーザヒアリングにない推測による設計

---

## システム概要 🔵

**信頼性**: 🔵 *要件定義書・ユーザヒアリングより*

LIFF アプリ内に復習専用画面（`/review`）を追加する。復習対象カードを1枚ずつフリップ形式で表示し、SM-2 アルゴリズムに基づく6段階（0-5）採点で復習を行う。バックエンド API（`GET /cards/due`, `POST /reviews/{card_id}`）は実装済みのため、フロントエンドの UI 実装が対象。

## アーキテクチャパターン 🔵

**信頼性**: 🔵 *既存プロジェクトアーキテクチャ・ヒアリングより*

- **パターン**: コンポーネントベースアーキテクチャ（既存パターン踏襲）
- **状態管理**: ReviewPage ローカル状態（useState）で完結
- **選択理由**: 復習セッションは他ページとの状態共有が不要。シンプルでテストしやすい

## コンポーネント構成 🔵

**信頼性**: 🔵 *既存プロジェクト構造・ユーザヒアリングより*

### 新規コンポーネント

```
frontend/src/
├── pages/
│   ├── ReviewPage.tsx          # 復習ページ（メインコンポーネント）
│   └── __tests__/
│       └── ReviewPage.test.tsx # 復習ページテスト
├── components/
│   ├── FlipCard.tsx            # フリップカードコンポーネント
│   ├── GradeButtons.tsx        # 採点ボタンコンポーネント
│   ├── ReviewProgress.tsx      # 進捗バーコンポーネント
│   ├── ReviewComplete.tsx      # 復習完了画面コンポーネント
│   └── __tests__/
│       ├── FlipCard.test.tsx
│       ├── GradeButtons.test.tsx
│       ├── ReviewProgress.test.tsx
│       └── ReviewComplete.test.tsx
└── styles/
    └── flip-card.css           # フリップアニメーション CSS
```

### 変更対象の既存コンポーネント

- `frontend/src/pages/HomePage.tsx`: 「復習を始める」リンク先を `/review` に変更
- `frontend/src/pages/CardsPage.tsx`: 復習対象タブに「復習開始」ボタン追加
- `frontend/src/App.tsx`（またはルーター設定）: `/review` ルート追加

## コンポーネント詳細設計

### ReviewPage（メインコンテナ） 🔵

**信頼性**: 🔵 *要件定義REQ-RV-001〜005・ユーザヒアリングより*

**責務**:
- 復習セッション全体のライフサイクル管理
- `GET /cards/due` でカード取得
- 現在のカードインデックス、フリップ状態、セッション状態の管理
- 採点結果の API 送信
- 完了判定と完了画面への切り替え

**ローカル状態**:

```typescript
// セッション状態
const [cards, setCards] = useState<DueCard[]>([]);       // 復習対象カード配列
const [currentIndex, setCurrentIndex] = useState(0);     // 現在のカードインデックス
const [isFlipped, setIsFlipped] = useState(false);       // フリップ状態
const [isSubmitting, setIsSubmitting] = useState(false);  // API送信中フラグ
const [reviewedCount, setReviewedCount] = useState(0);    // 採点済みカード数
const [isComplete, setIsComplete] = useState(false);      // 復習完了フラグ
const [isLoading, setIsLoading] = useState(true);         // 初期読み込み中
const [error, setError] = useState<string | null>(null);  // エラー
```

### FlipCard 🔵

**信頼性**: 🔵 *要件定義REQ-RV-002・ユーザヒアリングより*

**責務**:
- カードの表面/裏面の表示
- CSS transform によるフリップアニメーション
- タップ/クリックイベントの処理

**Props**:

```typescript
interface FlipCardProps {
  front: string;        // 表面テキスト
  back: string;         // 裏面テキスト
  isFlipped: boolean;   // フリップ状態
  onFlip: () => void;   // フリップハンドラ
}
```

**CSS 実装方針** 🔵:

```css
.flip-card {
  perspective: 1000px;
}
.flip-card-inner {
  transition: transform 0.4s;
  transform-style: preserve-3d;
}
.flip-card-inner.flipped {
  transform: rotateY(180deg);
}
.flip-card-front,
.flip-card-back {
  backface-visibility: hidden;
}
.flip-card-back {
  transform: rotateY(180deg);
}

/* アクセシビリティ対応 */
@media (prefers-reduced-motion: reduce) {
  .flip-card-inner {
    transition: none;
  }
}
```

### GradeButtons 🔵

**信頼性**: 🔵 *要件定義REQ-RV-003・ユーザヒアリングより*

**責務**:
- 0-5 の6段階採点ボタン表示
- スキップボタン表示
- 採点中のボタン無効化

**Props**:

```typescript
interface GradeButtonsProps {
  onGrade: (grade: number) => void;  // 採点ハンドラ
  onSkip: () => void;                // スキップハンドラ
  disabled: boolean;                  // 送信中の無効化
}
```

**ボタンデザイン** 🟡:

| Grade | ラベル | 色 | SM-2 の意味 |
|-------|--------|-----|------------|
| 0 | 0 | 赤 (red-600) | 全く覚えていない |
| 1 | 1 | 赤橙 (orange-600) | 間違えた |
| 2 | 2 | 橙 (amber-500) | 間違えたが見覚えあり |
| 3 | 3 | 黄 (yellow-500) | 難しかったが正解 |
| 4 | 4 | 黄緑 (lime-500) | やや迷ったが正解 |
| 5 | 5 | 緑 (green-600) | 完璧 |

### ReviewProgress 🔵

**信頼性**: 🔵 *要件定義REQ-RV-005・ユーザヒアリングより*

**責務**:
- 進捗バーの表示（現在のカード番号 / 全体枚数）
- 視覚的なプログレスバー

**Props**:

```typescript
interface ReviewProgressProps {
  current: number;  // 現在のカード番号（1始まり）
  total: number;    // 全体枚数
}
```

### ReviewComplete 🔵

**信頼性**: 🔵 *要件定義REQ-RV-010〜011・ユーザヒアリングより*

**責務**:
- 復習完了メッセージの表示
- 復習枚数（採点済みカード数）の表示
- 「ホームに戻る」ボタン

**Props**:

```typescript
interface ReviewCompleteProps {
  reviewedCount: number;  // 採点済みカード数
}
```

## ルーティング 🔵

**信頼性**: 🔵 *要件定義REQ-RV-004・既存ルーター設計より*

```typescript
// App.tsx のルート追加
<Route path="/review" element={<ReviewPage />} />
```

## 既存コンポーネントへの変更

### HomePage.tsx 🔵

**信頼性**: 🔵 *要件定義REQ-RV-030・ユーザヒアリングより*

```diff
- <Link to="/cards?tab=due">復習を始める</Link>
+ <Link to="/review">復習を始める</Link>
```

### CardsPage.tsx 🔵

**信頼性**: 🔵 *要件定義REQ-RV-031・ユーザヒアリングより*

復習対象タブの空状態ではなく、カードがある場合に「復習開始」ボタンを追加:

```typescript
{activeTab === 'due' && displayCards.length > 0 && (
  <Link to="/review" className="...">復習開始</Link>
)}
```

## 非機能要件の実現方法

### パフォーマンス 🟡

**信頼性**: 🟡 *NFR要件から妥当な推測*

- **フリップアニメーション**: CSS transform は GPU アクセラレーション対象。400ms 以内で完了
- **採点→次カード遷移**: ローカル状態更新のみ（API 送信は非同期）。300ms 以内
- **初期読み込み**: `GET /cards/due` のレスポンス待ち。ローディング表示で対応

### ユーザビリティ 🔵

**信頼性**: 🔵 *要件定義NFR-RV-101〜102・既存実装パターンより*

- **タッチターゲット**: 全ボタン最小 44px（既存パターン踏襲）
- **モバイルファースト**: カードエリアは画面幅いっぱい、ボタンは横並び
- **フィードバック**: 採点ボタンタップ時に視覚的フィードバック（active 状態）

### アクセシビリティ 🟡

**信頼性**: 🟡 *NFR要件から妥当な推測*

- **prefers-reduced-motion**: アニメーションなしで即座切り替え
- **ARIA ラベル**: カードエリアに `aria-label`、ボタンに意味のあるラベル
- **キーボード操作**: Space/Enter でフリップ、数字キーで採点（将来対応可）

## 技術的制約 🔵

**信頼性**: 🔵 *CLAUDE.md・既存実装より*

- React 18 + TypeScript
- Tailwind CSS でスタイリング（フリップアニメーションのみ別 CSS ファイル）
- 新規 npm パッケージ追加なし
- 既存の API クライアント（`reviewsApi`, `cardsApi`）を利用
- 既存の共通コンポーネント（`Loading`, `Error`）を再利用

## 関連文書

- **データフロー**: [dataflow.md](dataflow.md)
- **型定義**: [interfaces.ts](interfaces.ts)
- **要件定義**: [requirements.md](../../spec/review-flow/requirements.md)
- **ユーザストーリー**: [user-stories.md](../../spec/review-flow/user-stories.md)
- **受け入れ基準**: [acceptance-criteria.md](../../spec/review-flow/acceptance-criteria.md)

## 信頼性レベルサマリー

- 🔵 青信号: 16件 (80%)
- 🟡 黄信号: 4件 (20%)
- 🔴 赤信号: 0件 (0%)

**品質評価**: ✅ 高品質（青信号が80%。黄信号はボタンデザイン・パフォーマンス目標・アクセシビリティの詳細のみ）
