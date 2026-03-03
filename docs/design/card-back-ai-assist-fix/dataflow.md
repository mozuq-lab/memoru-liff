# カード AI 補足機能 レビュー修正 データフロー図

**作成日**: 2026-03-03
**関連アーキテクチャ**: [architecture.md](architecture.md)
**関連要件定義**: [requirements.md](../../spec/card-back-ai-assist-fix/requirements.md)
**元機能データフロー**: [card-back-ai-assist/dataflow.md](../card-back-ai-assist/dataflow.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: コードレビュー・既存実装を参考にした確実なフロー
- 🟡 **黄信号**: 既存実装パターンから妥当な推測によるフロー

---

## 修正 1: language 対応プロンプト生成フロー 🔵

**信頼性**: 🔵 *レビュー指摘 #1・既存 `generate.py` パターンより*
**関連要件**: REQ-FIX-001, REQ-FIX-002

元のフローからの変更点: プロンプト生成で `language` パラメータによる分岐が追加される。

```mermaid
sequenceDiagram
    participant H as ai_handler
    participant S as Service (Bedrock/Strands)
    participant P as prompts/refine.py

    H->>S: refine_card(front, back, language="en")

    S->>P: get_refine_system_prompt(language="en")
    P-->>S: _REFINE_SYSTEM_PROMPT_EN

    S->>P: get_refine_user_prompt(front, back, language="en")

    alt has_front AND has_back
        P-->>S: _get_both_prompt_en(front, back)
    else has_front only
        P-->>S: _get_front_only_prompt_en(front)
    else has_back only
        P-->>S: _get_back_only_prompt_en(back)
    end

    S->>S: AI 呼び出し (英語プロンプト)
    S-->>H: RefineResult
```

### language フロー比較

```mermaid
flowchart TD
    START[refine_card 呼び出し] --> CHECK_LANG{language?}

    CHECK_LANG -->|ja| JA_SYS["system: _REFINE_SYSTEM_PROMPT_JA"]
    CHECK_LANG -->|en| EN_SYS["system: _REFINE_SYSTEM_PROMPT_EN"]

    JA_SYS --> CHECK_INPUT_JA{入力パターン?}
    EN_SYS --> CHECK_INPUT_EN{入力パターン?}

    CHECK_INPUT_JA -->|both| JA_BOTH["_get_both_prompt_ja()"]
    CHECK_INPUT_JA -->|front only| JA_FRONT["_get_front_only_prompt_ja()"]
    CHECK_INPUT_JA -->|back only| JA_BACK["_get_back_only_prompt_ja()"]

    CHECK_INPUT_EN -->|both| EN_BOTH["_get_both_prompt_en()"]
    CHECK_INPUT_EN -->|front only| EN_FRONT["_get_front_only_prompt_en()"]
    CHECK_INPUT_EN -->|back only| EN_BACK["_get_back_only_prompt_en()"]

    JA_BOTH --> INVOKE[AI 呼び出し]
    JA_FRONT --> INVOKE
    JA_BACK --> INVOKE
    EN_BOTH --> INVOKE
    EN_FRONT --> INVOKE
    EN_BACK --> INVOKE
```

---

## 修正 2: body=null ハンドリングフロー 🔵

**信頼性**: 🔵 *レビュー指摘 #2・Codex Powertools v3.23.0 検証より*
**関連要件**: REQ-FIX-003, REQ-FIX-004

元のフローからの変更点: `json_body` 取得後に `isinstance(body, dict)` チェックが追加される。

```mermaid
sequenceDiagram
    participant C as Client
    participant GW as API Gateway
    participant H as ai_handler

    C->>GW: POST /cards/refine (body: "null")
    GW->>H: リクエスト受信

    H->>H: body = json_body → None

    alt body is dict ✅
        H->>H: RefineCardRequest(**body)
        H->>H: 通常処理続行
    else body is NOT dict ❌ (None, list, str, int)
        H-->>GW: 400 "Request body must be a JSON object"
        GW-->>C: HTTP 400
    end
```

### 不正ボディの分類

```mermaid
flowchart TD
    BODY[json_body] --> CHECK{isinstance(body, dict)?}

    CHECK -->|Yes| VALID[Pydantic バリデーション]
    CHECK -->|No| INVALID[400 エラー]

    VALID -->|pass| PROCESS[サービス呼び出し]
    VALID -->|fail| VALIDATION_ERR[400 ValidationError]

    subgraph "body=null のケース"
        NULL_BODY["body: 'null'<br/>json_body → None"]
        ARRAY_BODY["body: '[1,2]'<br/>json_body → [1,2]"]
        STRING_BODY["body: '\"hello\"'<br/>json_body → 'hello'"]
        NUM_BODY["body: '42'<br/>json_body → 42"]
    end

    NULL_BODY --> CHECK
    ARRAY_BODY --> CHECK
    STRING_BODY --> CHECK
    NUM_BODY --> CHECK
```

---

## 修正 3: CardForm アンマウント時キャンセルフロー 🔵

**信頼性**: 🔵 *レビュー指摘 #4・React ベストプラクティスより*
**関連要件**: REQ-FIX-005

元のフローからの変更点: コンポーネントのアンマウント時に `abort()` が呼ばれる。

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant CF as CardForm
    participant AC as ApiClient
    participant API as Backend

    U->>CF: 「AI で補足」ボタン押下
    CF->>CF: AbortController 作成
    CF->>AC: refineCard({ signal })
    AC->>API: POST /cards/refine

    Note over U,CF: ユーザーが別ページに遷移

    CF->>CF: useEffect cleanup 実行
    CF->>CF: abortControllerRef.current.abort()
    AC--xAPI: リクエストキャンセル

    Note over CF: コンポーネントアンマウント<br/>state 更新なし（メモリリーク防止）
```

### 修正前後の比較

```mermaid
flowchart LR
    subgraph Before["修正前"]
        B1[AI 処理中] --> B2[ページ遷移]
        B2 --> B3[通信継続]
        B3 --> B4[レスポンス到着]
        B4 --> B5["signal.aborted チェック<br/>(state更新スキップ)"]
    end

    subgraph After["修正後"]
        A1[AI 処理中] --> A2[ページ遷移]
        A2 --> A3["useEffect cleanup<br/>abort() 実行"]
        A3 --> A4[通信キャンセル]
        A4 --> A5[AbortError → 無視]
    end
```

---

## 関連文書

- **アーキテクチャ**: [architecture.md](architecture.md)
- **元機能データフロー**: [card-back-ai-assist/dataflow.md](../card-back-ai-assist/dataflow.md)
- **要件定義**: [requirements.md](../../spec/card-back-ai-assist-fix/requirements.md)

## 信頼性レベルサマリー

- 🔵 青信号: 5 件 (100%)
- 🟡 黄信号: 0 件 (0%)
- 🔴 赤信号: 0 件 (0%)

**品質評価**: ✅ 高品質
