# AI Strands Migration API エンドポイント仕様

**作成日**: 2026-02-23
**関連設計**: [architecture.md](architecture.md)
**関連要件定義**: [requirements.md](../../spec/ai-strands-migration/requirements.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: EARS要件定義書・設計文書・既存API仕様を参考にした確実な定義
- 🟡 **黄信号**: EARS要件定義書・設計文書・既存API仕様から妥当な推測による定義
- 🔴 **赤信号**: EARS要件定義書・設計文書・既存API仕様にない推測による定義

---

## 共通仕様

### ベースURL 🔵

**信頼性**: 🔵 *既存 API 仕様（`template.yaml` HttpApi）より*

```
https://{api-id}.execute-api.{region}.amazonaws.com/
```

ローカル開発:
```
http://localhost:8080/
```

### 認証 🔵

**信頼性**: 🔵 *既存 API 仕様・Keycloak OIDC 設計より*

すべてのエンドポイントは JWT 認証が必要です。

```http
Authorization: Bearer {keycloak_access_token}
```

### エラーレスポンス共通フォーマット 🔵

**信頼性**: 🔵 *既存 `handler.py` のエラーハンドリングパターンより*

```json
{
  "error": "ERROR_MESSAGE",
  "details": {}
}
```

---

## エンドポイント一覧

### 既存エンドポイント（移行対象）

#### POST /cards/generate 🔵

**信頼性**: 🔵 *既存実装 `handler.py:241`・`GenerateCardsRequest`/`GenerateCardsResponse` より*

**関連要件**: REQ-SM-002, REQ-SM-402

**説明**: AI を使用してテキストからフラッシュカードを生成する。Strands 移行後も API 形式は完全互換。

**リクエスト**:
```json
{
  "input_text": "光合成は植物が太陽光エネルギーを使って...",
  "card_count": 5,
  "difficulty": "medium",
  "language": "ja"
}
```

| フィールド | 型 | 必須 | バリデーション | 説明 |
|-----------|------|------|--------------|------|
| `input_text` | string | ✅ | 10-2000文字、空白のみ不可 | 生成元テキスト |
| `card_count` | integer | - | 1-10、デフォルト5 | 生成カード数 |
| `difficulty` | string | - | "easy"/"medium"/"hard"、デフォルト"medium" | 難易度 |
| `language` | string | - | "ja"/"en"、デフォルト"ja" | 出力言語 |

**レスポンス（成功 200）**:
```json
{
  "generated_cards": [
    {
      "front": "光合成とは何か？",
      "back": "植物が太陽光エネルギーを使って二酸化炭素と水から有機物を合成する過程",
      "suggested_tags": ["生物学", "光合成", "AI生成"]
    }
  ],
  "generation_info": {
    "input_length": 150,
    "model_used": "anthropic.claude-3-haiku-20240307-v1:0",
    "processing_time_ms": 3500
  }
}
```

**エラーコード**:
- `400`: バリデーションエラー（入力テキスト不正）
- `429`: AI レート制限超過
- `500`: AI レスポンス解析エラー / 内部エラー
- `504`: AI タイムアウト（30秒超過）

**変更点（移行後）**:
- 内部的に `AIServiceFactory` が `USE_STRANDS` に応じた実装を選択
- レスポンス形式は完全互換（`GenerateCardsResponse` を維持）
- `model_used` フィールドに Strands Agent 使用モデル名が入る

---

### 新規エンドポイント

#### POST /reviews/{card_id}/grade-ai 🔵

**信頼性**: 🔵 *要件 REQ-SM-003・ユーザーストーリー 2.1・設計ヒアリング Q4 より*

**関連要件**: REQ-SM-003

**説明**: AI がユーザーの回答を採点し、SRS グレード（0-5）と採点理由を返す。

**パスパラメータ**:
- `card_id`: カード ID（UUID 形式）

**リクエスト**:
```json
{
  "user_answer": "東京"
}
```

| フィールド | 型 | 必須 | バリデーション | 説明 |
|-----------|------|------|--------------|------|
| `user_answer` | string | ✅ | 1-2000文字、空白のみ不可 | ユーザーの回答 |

**レスポンス（成功 200）**:
```json
{
  "grade": 4,
  "reasoning": "正確な回答です。日本の首都は東京で、回答と一致しています。",
  "card_front": "日本の首都は？",
  "card_back": "東京",
  "grading_info": {
    "model_used": "anthropic.claude-3-haiku-20240307-v1:0",
    "processing_time_ms": 2100
  }
}
```

| フィールド | 型 | 説明 |
|-----------|------|------|
| `grade` | integer (0-5) | SRS グレード（0=完全忘却, 5=完璧） |
| `reasoning` | string | AI による採点理由 |
| `card_front` | string | カードの問題（参考表示用） |
| `card_back` | string | カードの正解（参考表示用） |
| `grading_info` | object | 採点メタ情報 |

**SRS グレード定義** 🔵:

| グレード | 意味 | AI 判定基準 |
|---------|------|------------|
| 0 | Complete blackout | 回答なし、または完全に無関係 |
| 1 | Incorrect; correct answer remembered | 不正解だが関連する知識あり |
| 2 | Incorrect; correct answer seemed easy | 不正解だが正解を聞けば容易に思い出す |
| 3 | Correct with serious difficulty | 正解だが大きな困難あり |
| 4 | Correct with some hesitation | 正解、軽微な不備あり |
| 5 | Perfect response | 完璧な回答 |

**エラーコード**:
- `400`: バリデーションエラー（回答が空、形式不正）
- `404`: カードが見つからない / 他ユーザーのカード
- `429`: AI レート制限超過
- `500`: AI レスポンス解析エラー / 内部エラー
- `504`: AI タイムアウト（60秒超過）

---

#### GET /advice 🔵

**信頼性**: 🔵 *要件 REQ-SM-004・ユーザーストーリー 3.1・設計ヒアリング Q5 より*

**関連要件**: REQ-SM-004

**説明**: ユーザーの学習履歴を AI が分析し、学習改善アドバイスを提供する。

**クエリパラメータ**:

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|-----------|------|------|----------|------|
| `language` | string | - | "ja" | 出力言語（"ja"/"en"） |

**レスポンス（成功 200）**:
```json
{
  "advice_text": "あなたの学習傾向を分析しました。以下のポイントに注目してください。",
  "weak_areas": [
    "有機化学",
    "英文法（関係代名詞）"
  ],
  "recommendations": [
    "有機化学のカードを重点的に復習してください。正答率が45%と低い傾向です。",
    "毎日の復習数を15枚に増やすと、記憶の定着率が向上します。",
    "学習時間帯を午前中に変更すると効果的かもしれません。"
  ],
  "study_stats": {
    "total_reviews": 234,
    "average_grade": 3.2,
    "streak_days": 12,
    "cards_due_today": 8
  },
  "advice_info": {
    "model_used": "anthropic.claude-3-haiku-20240307-v1:0",
    "processing_time_ms": 5200
  }
}
```

| フィールド | 型 | 説明 |
|-----------|------|------|
| `advice_text` | string | AI による学習アドバイス本文 |
| `weak_areas` | string[] | 弱点分野のリスト |
| `recommendations` | string[] | 具体的な改善推奨事項 |
| `study_stats` | object | 学習統計サマリー（事前集計データ） |
| `advice_info` | object | アドバイス生成メタ情報 |

**エラーコード**:
- `401`: 認証エラー
- `429`: AI レート制限超過
- `500`: DynamoDB アクセスエラー / AI エラー
- `504`: AI タイムアウト（60秒超過）

**備考**:
- 復習履歴が 0 件の場合は一般的な学習のコツを返す
- データ集計は Python で事前実行し、集計結果をプロンプトに埋め込む

---

## Lambda タイムアウト設定 🔵

**信頼性**: 🔵 *REQ-SM-401・設計ヒアリング Q2 より*

| エンドポイント | レスポンス目標 | Lambda タイムアウト |
|--------------|--------------|-------------------|
| POST /cards/generate | 30 秒以内 | 60 秒（共通） |
| POST /reviews/{card_id}/grade-ai | 10 秒以内 | 60 秒（共通） |
| GET /advice | 15 秒以内 | 60 秒（共通） |

**設計判断**: 既存 Lambda 統合のため、タイムアウトは全エンドポイント共通で 60 秒に設定。レスポンス目標は AI サービス側で制御。

`template.yaml` 変更:
```yaml
Globals:
  Function:
    Timeout: 60  # 30 → 60 に変更
```

---

## template.yaml 追加設定 🔵

**信頼性**: 🔵 *既存 `template.yaml` パターン・設計ヒアリングより*

### 新規環境変数

```yaml
Globals:
  Function:
    Environment:
      Variables:
        # 既存
        ENVIRONMENT: !Ref Environment
        BEDROCK_MODEL_ID: !Ref BedrockModelId
        # 新規追加
        USE_STRANDS: !Ref UseStrands
        OLLAMA_HOST: !If [IsDev, "http://ollama:11434", ""]
        OLLAMA_MODEL: !If [IsDev, "llama3.2", ""]

Parameters:
  UseStrands:
    Type: String
    Default: "false"
    AllowedValues:
      - "true"
      - "false"
    Description: Feature flag to enable Strands Agents SDK
```

### 新規 API ルート 🔵

```yaml
Events:
  # 既存ルート維持
  GenerateCards:
    Type: HttpApi
    Properties:
      Path: /cards/generate
      Method: POST

  # 新規追加
  GradeAnswer:
    Type: HttpApi
    Properties:
      Path: /reviews/{card_id}/grade-ai
      Method: POST

  GetAdvice:
    Type: HttpApi
    Properties:
      Path: /advice
      Method: GET
```

---

## CORS設定 🔵

**信頼性**: 🔵 *既存 template.yaml CORS 設定より*

既存の CORS 設定を維持。新規エンドポイントも同じ CORS ポリシーが適用される。

---

## 関連文書

- **アーキテクチャ**: [architecture.md](architecture.md)
- **データフロー**: [dataflow.md](dataflow.md)
- **要件定義**: [requirements.md](../../spec/ai-strands-migration/requirements.md)

## 信頼性レベルサマリー

- 🔵 青信号: 12件 (92%)
- 🟡 黄信号: 1件 (8%)
- 🔴 赤信号: 0件 (0%)

**品質評価**: ✅ 高品質（青信号 92%、赤信号なし。黄信号はレスポンスフォーマットの一部詳細のみ）
