# カード AI アシスト入力 データフロー図

**作成日**: 2026-03-03
**関連アーキテクチャ**: [architecture.md](architecture.md)
**関連要件定義**: [requirements.md](../../spec/card-back-ai-assist/requirements.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: EARS要件定義書・設計文書・ユーザヒアリングを参考にした確実なフロー
- 🟡 **黄信号**: EARS要件定義書・設計文書・ユーザヒアリングから妥当な推測によるフロー
- 🔴 **赤信号**: EARS要件定義書・設計文書・ユーザヒアリングにない推測によるフロー

---

## メインフロー: AI カード補足 🔵

**信頼性**: 🔵 *要件定義 REQ-001〜007・ユーザヒアリングより*

**関連要件**: REQ-001, REQ-002, REQ-003, REQ-004, REQ-006, REQ-007

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant CF as CardForm
    participant AC as ApiClient
    participant GW as API Gateway
    participant H as ai_handler
    participant S as StrandsAIService
    participant P as prompts/refine
    participant B as Bedrock (Claude Haiku)

    U->>CF: 表面・裏面を入力
    U->>CF: 「AI で補足」ボタン押下
    CF->>CF: ローディング状態 ON
    CF->>CF: ボタン無効化
    CF->>AC: refineCard({ front, back })
    AC->>GW: POST /cards/refine
    GW->>H: リクエスト受信
    H->>H: JWT 認証・バリデーション
    H->>S: refine_card(front, back)
    S->>P: get_refine_prompt(front, back)
    P-->>S: プロンプト文字列
    S->>B: Agent(system_prompt, user_prompt)
    B-->>S: JSON レスポンス
    S->>S: _parse_refine_result()
    S-->>H: RefineResult
    H-->>GW: RefineCardResponse
    GW-->>AC: JSON レスポンス
    AC-->>CF: { refined_front, refined_back }
    CF->>CF: 表面テキストエリア更新
    CF->>CF: 裏面テキストエリア更新
    CF->>CF: ローディング状態 OFF
    U->>CF: 結果を確認・必要に応じて編集
    U->>CF: 保存ボタン押下
```

**詳細ステップ**:
1. ユーザーが CardForm で表面・裏面にメモを入力する
2. 「AI で補足」ボタンを押下する
3. フロントエンドがローディング状態に遷移し、ボタンを無効化する
4. `POST /cards/refine` に表面・裏面テキストを送信する
5. バックエンドが JWT 認証とバリデーションを行う
6. AI サービスがプロンプトを構築し Bedrock に送信する
7. Claude Haiku が表面の表現を整理し、裏面を補足した JSON を返す
8. バックエンドがレスポンスをパースしてフロントエンドに返す
9. フロントエンドが表面・裏面のテキストエリアをインラインで更新する
10. ユーザーが結果を確認・編集し、保存する

## 部分入力フロー: 表面のみ 🟡

**信頼性**: 🟡 *要件定義 REQ-103 から妥当な推測*

**関連要件**: REQ-103

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant CF as CardForm
    participant S as StrandsAIService

    U->>CF: 表面のみ入力（裏面は空）
    U->>CF: 「AI で補足」ボタン押下
    CF->>S: refine_card(front="クロージャ", back="")
    S->>S: 表面のみプロンプト生成
    S-->>CF: { refined_front: "...", refined_back: "" }
    CF->>CF: 表面のみ更新（裏面は空のまま）
```

## 部分入力フロー: 裏面のみ 🟡

**信頼性**: 🟡 *要件定義 REQ-104 から妥当な推測*

**関連要件**: REQ-104

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant CF as CardForm
    participant S as StrandsAIService

    U->>CF: 裏面のみ入力（表面は空）
    U->>CF: 「AI で補足」ボタン押下
    CF->>S: refine_card(front="", back="変数を覚えてる関数")
    S->>S: 裏面のみプロンプト生成
    S-->>CF: { refined_front: "", refined_back: "..." }
    CF->>CF: 裏面のみ更新（表面は空のまま）
```

## エラーハンドリングフロー 🔵

**信頼性**: 🔵 *既存実装パターンより*

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant CF as CardForm
    participant AC as ApiClient
    participant H as ai_handler

    U->>CF: 「AI で補足」ボタン押下
    CF->>CF: ローディング状態 ON
    CF->>AC: refineCard({ front, back })

    alt タイムアウト (504)
        AC-->>CF: AITimeoutError
        CF->>CF: "AIの処理がタイムアウトしました" 表示
    else レート制限 (429)
        AC-->>CF: AIRateLimitError
        CF->>CF: "リクエスト制限に達しました" 表示
    else AI 障害 (503)
        AC-->>CF: AIProviderError
        CF->>CF: "AIサービスが一時的に利用できません" 表示
    else バリデーション (400)
        H-->>AC: Validation Error
        CF->>CF: "入力内容を確認してください" 表示
    end

    CF->>CF: 元のテキストを維持
    CF->>CF: ローディング状態 OFF
    U->>U: 再試行 or 手動で編集
```

## フロントエンド状態管理フロー 🔵

**信頼性**: 🔵 *既存 CardForm パターンより*

```mermaid
stateDiagram-v2
    [*] --> 入力待ち
    入力待ち --> AI処理中: 「AI で補足」押下
    AI処理中 --> AI結果反映: 成功
    AI処理中 --> エラー表示: 失敗
    AI結果反映 --> 入力待ち: ユーザーが編集開始
    エラー表示 --> 入力待ち: エラー消去

    state AI処理中 {
        [*] --> ローディング表示
        ローディング表示 --> ボタン無効化
    }

    state AI結果反映 {
        [*] --> 表面テキスト更新
        表面テキスト更新 --> 裏面テキスト更新
    }
```

**状態変数**:
- `isRefining: boolean` — AI 処理中フラグ
- `refineError: string | null` — エラーメッセージ

**ボタン有効条件**:
- `!isRefining && !isSaving && (front.trim() || back.trim())`

## 関連文書

- **アーキテクチャ**: [architecture.md](architecture.md)
- **要件定義**: [requirements.md](../../spec/card-back-ai-assist/requirements.md)

## 信頼性レベルサマリー

- 🔵 青信号: 4 件 (67%)
- 🟡 黄信号: 2 件 (33%)
- 🔴 赤信号: 0 件 (0%)

**品質評価**: ✅ 高品質
