# review-undo アーキテクチャ設計

**作成日**: 2026-02-28
**関連要件定義**: [requirements.md](../../spec/review-undo/requirements.md)
**ヒアリング記録**: [design-interview.md](design-interview.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: EARS要件定義書・設計文書・ユーザヒアリングを参考にした確実な設計
- 🟡 **黄信号**: EARS要件定義書・設計文書・ユーザヒアリングから妥当な推測による設計
- 🔴 **赤信号**: EARS要件定義書・設計文書・ユーザヒアリングにない推測による設計

---

## システム概要 🔵

**信頼性**: 🔵 *要件定義書・ユーザヒアリングより*

復習完了画面を拡張し、セッション中に採点した全カードの結果一覧（表面テキスト・グレード・次回復習日）を表示する。各カードに取り消しボタンを設け、バックエンドUndo APIでSRSパラメータを復元後、同一ページ内でカード復習UIに切り替えて再採点できるようにする。

## アーキテクチャパターン 🔵

**信頼性**: 🔵 *既存review-flow設計・CLAUDE.md技術スタックより*

- **パターン**: 既存review-flowのレイヤードアーキテクチャを拡張
- **選択理由**: 既存のReviewPage（useState状態管理）+ ReviewCompleteコンポーネント構成を活かし、最小限の変更で機能追加する

### 変更方針

既存のreview-flowアーキテクチャを**拡張**する形で実装する。新規ファイルの追加は最小限とし、既存コンポーネントの修正を中心に行う。

## コンポーネント構成 🔵

**信頼性**: 🔵 *既存review-flow architecture.md・実装より*

### 変更対象コンポーネント

```
ReviewPage (既存・修正)
├── ReviewProgress (既存・変更なし)
├── FlipCard (既存・変更なし)
├── GradeButtons (既存・変更なし)
└── ReviewComplete (既存・大幅修正)
    └── ReviewResultItem (新規)
```

### フロントエンド 🔵

**信頼性**: 🔵 *CLAUDE.md・既存実装より*

- **フレームワーク**: React 19 + TypeScript
- **状態管理**: ReviewPage内のuseState（既存パターン維持）
- **UIライブラリ**: Tailwind CSS 4.x
- **ルーティング**: React Router（既存`/review`ルート内で状態切替）

### バックエンド 🔵

**信頼性**: 🔵 *CLAUDE.md・既存実装より*

- **フレームワーク**: Python 3.12 + AWS Lambda Powertools
- **認証方式**: Keycloak OIDC + JWT Bearer Token（既存パターン）
- **API設計**: REST（既存パターンの拡張）
- **データベース**: DynamoDB（既存テーブル使用）

## コンポーネント詳細

### ReviewPage（修正） 🔵

**信頼性**: 🔵 *既存ReviewPage実装・要件定義REQ-013より*

**変更内容**:
- セッション結果を保持する新しいstate `reviewResults` を追加
- 取り消し（undo）→再採点モード用の state を追加
- `handleGrade` で `ReviewResponse` を保存するよう修正
- `handleSkip` でスキップ情報を保存するよう修正

**新規state**:
```typescript
// セッション中の各カードの結果
const [reviewResults, setReviewResults] = useState<SessionCardResult[]>([]);
// 再採点モード: undoしたカードのindex
const [regradeCardIndex, setRegradeCardIndex] = useState<number | null>(null);
// undo処理中フラグ
const [isUndoing, setIsUndoing] = useState(false);
```

### ReviewComplete（大幅修正） 🔵

**信頼性**: 🔵 *要件定義REQ-001〜008・ユーザヒアリングより*

**変更内容**:
- `reviewedCount` のみのpropsから `SessionCardResult[]` を受け取るよう変更
- 結果一覧の表示（カード表面テキスト、グレード、次回復習日）
- スキップカードの表示（「スキップ」ステータス、取り消しボタンなし）
- 取り消しボタンの表示と処理

**Props変更**:
```typescript
interface ReviewCompleteProps {
  results: SessionCardResult[];
  onUndo: (index: number) => void;
  isUndoing: boolean;
  undoingIndex: number | null;
}
```

### ReviewResultItem（新規） 🟡

**信頼性**: 🟡 *要件定義REQ-001〜005から妥当な推測*

結果一覧の各カード行を表示するコンポーネント。

**責務**:
- カード表面テキスト（長文時は省略）
- グレード表示（色分け）
- 次回復習日（相対日付表示）
- 取り消しボタン（スキップ時は非表示）

### Undo API（バックエンド新規） 🔵

**信頼性**: 🔵 *要件定義REQ-009〜012・設計ヒアリングより*

**エンドポイント**: `POST /reviews/{cardId}/undo`

**処理フロー**:
1. カードの存在確認・所有権確認
2. review_historyの最新エントリからprevious状態を取得
3. カードのSRSパラメータ（ease_factor, interval, repetitions, next_review_at）を復元
4. review_historyの最新エントリを削除
5. reviews テーブルのレコードは保持
6. 復元後の状態をレスポンスとして返却

## システム構成図 🔵

**信頼性**: 🔵 *既存review-flow構成・要件定義より*

```mermaid
graph TB
    subgraph Frontend["フロントエンド (React)"]
        RP[ReviewPage]
        RC[ReviewComplete]
        RRI[ReviewResultItem]
        FC[FlipCard]
        GB[GradeButtons]
    end

    subgraph Backend["バックエンド (Lambda)"]
        H[API Handler]
        RS[ReviewService]
        SRS[SRS Service]
        CS[CardService]
    end

    subgraph DB["DynamoDB"]
        CT[(Cards Table)]
        RT[(Reviews Table)]
    end

    RP --> RC
    RC --> RRI
    RP --> FC
    RP --> GB

    RC -->|POST /reviews/{id}/undo| H
    GB -->|POST /reviews/{id}| H
    RP -->|GET /cards/due| H

    H --> RS
    RS --> SRS
    RS --> CS
    RS --> CT
    RS --> RT
```

## ディレクトリ構造（変更対象） 🔵

**信頼性**: 🔵 *既存プロジェクト構造より*

```
frontend/src/
├── components/
│   ├── ReviewComplete.tsx    # 大幅修正: 結果一覧・取り消しUI
│   └── ReviewResultItem.tsx  # 新規: 結果行コンポーネント
├── pages/
│   └── ReviewPage.tsx        # 修正: セッション結果保持・再採点モード
├── services/
│   └── api.ts                # 修正: undoReview API追加
└── types/
    └── card.ts               # 修正: SessionCardResult型追加

backend/src/
├── api/
│   └── handler.py            # 修正: POST /reviews/{cardId}/undo ルート追加
├── models/
│   └── review.py             # 修正: UndoReviewResponse モデル追加
└── services/
    └── review_service.py     # 修正: undo_review メソッド追加

backend/
└── template.yaml             # 修正: /reviews/{cardId}/undo ルート追加
```

## 非機能要件の実現方法

### パフォーマンス 🟡

**信頼性**: 🟡 *NFR-001, NFR-002から妥当な推測*

- **Undo APIレスポンス**: DynamoDB単一アイテム操作（GetItem + UpdateItem）で500ms以内を実現
- **結果一覧描画**: React仮想DOMにより50枚まで1秒以内に描画
- **最適化**: カード表面テキストの省略はCSSの`text-overflow: ellipsis`で処理

### セキュリティ 🔵

**信頼性**: 🔵 *NFR-101, NFR-102・既存API認証設計より*

- **認証**: 既存のJWT Bearer Token認証を適用（API Gateway Authorizer）
- **認可**: CardServiceの`get_card(user_id, card_id)`で所有権確認（既存パターン）
- **入力検証**: card_idのバリデーション（既存パターン）

### データ整合性 🟡

**信頼性**: 🟡 *要件定義REQ-010〜012から妥当な推測*

- **review_history**: 最新エントリの削除はリスト操作（pop）で実現
- **SRSパラメータ復元**: review_historyのprevious値（ease_factor_before, interval_before）を使用
- **reviews テーブル**: レコードは保持（削除しない）- 分析用途

## 技術的制約

### パフォーマンス制約 🔵

**信頼性**: 🔵 *CLAUDE.md・既存実装より*

- Lambda Cold Start: 初回呼び出し時の遅延を考慮
- DynamoDB操作: 1回のundo処理で GetItem + UpdateItem の2回操作

### データ制約 🔵

**信頼性**: 🔵 *既存srs.py実装より*

- review_historyは最大100件保持（既存制約）
- review_historyが空の場合はundo不可（400 Bad Request）
- ease_factorの最小値は1.3（SM-2アルゴリズム制約）

### UI制約 🔵

**信頼性**: 🔵 *既存review-flow NFR-201・CLAUDE.mdより*

- 最小タッチターゲット: 44x44px
- モバイルファースト: スマートフォンでの操作を前提
- Tailwind CSS 4.xの制約に従う

## 関連文書

- **データフロー**: [dataflow.md](dataflow.md)
- **型定義**: [interfaces.ts](interfaces.ts)
- **API仕様**: [api-endpoints.md](api-endpoints.md)
- **要件定義**: [requirements.md](../../spec/review-undo/requirements.md)
- **ユーザストーリー**: [user-stories.md](../../spec/review-undo/user-stories.md)
- **受け入れ基準**: [acceptance-criteria.md](../../spec/review-undo/acceptance-criteria.md)
- **既存review-flow設計**: [../review-flow/architecture.md](../review-flow/architecture.md)

## 信頼性レベルサマリー

- 🔵 青信号: 15件 (79%)
- 🟡 黄信号: 4件 (21%)
- 🔴 赤信号: 0件 (0%)

**品質評価**: ✅ 高品質
