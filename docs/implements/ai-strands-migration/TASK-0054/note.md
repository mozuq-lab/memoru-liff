# TASK-0054: プロンプトモジュールディレクトリ化 - タスクノート

## 技術スタック

- **言語**: Python 3.12
- **フレームワーク**: AWS SAM (Lambda)
- **テスト**: pytest
- **型チェック**: typing.Literal, dataclass
- **データ検証**: Pydantic v2 (API モデル層)
- **AI サービス**: AIService Protocol (ai_service.py)

## 開発ルール

- TDD (Red -> Green -> Refactor)
- テストカバレッジ 80% 以上
- 既存 260+ テストを破壊しない (REQ-SM-405)
- Pydantic v2 使用 (API モデル層)
- コミットメッセージ: `TASK-XXXX: タスク名`

## 関連実装

### 既存ファイル

- `backend/src/services/prompts.py` - 現行のカード生成プロンプト (96行)
  - `DifficultyLevel` 型エイリアス
  - `Language` 型エイリアス
  - `DIFFICULTY_GUIDELINES` 辞書
  - `get_card_generation_prompt()` 関数
- `backend/src/services/ai_service.py` - AIService Protocol + 共通型 + 例外階層 (TASK-0053 で作成)
  - `ReviewSummary` dataclass (advice.py で使用)
  - `GradingResult` dataclass (grading.py で使用)
- `backend/src/services/bedrock.py` - 既存 BedrockService
- `backend/tests/unit/test_bedrock.py` - `from services.prompts import get_card_generation_prompt` (唯一の import)

### import 依存関係

- `backend/tests/unit/test_bedrock.py:16` で `from services.prompts import get_card_generation_prompt` を使用
- `backend/src` 内では `services.prompts` の直接 import はなし
  (bedrock.py では prompts の関数を内部的に使っている可能性あり - 要確認)

## 設計文書

- **アーキテクチャ**: `docs/design/ai-strands-migration/architecture.md` - プロンプト管理セクション
- **インターフェース**: `docs/design/ai-strands-migration/interfaces.py` - 型定義
- **データフロー**: `docs/design/ai-strands-migration/dataflow.md` - フロー図
- **API 仕様**: `docs/design/ai-strands-migration/api-endpoints.md`
- **設計ヒアリング**: `docs/design/ai-strands-migration/design-interview.md` - Q3 (プロンプト管理), Q4 (SRS グレード), Q5 (学習アドバイスデータ)

## 注意事項

- `prompts.py` の削除は import パス更新完了後
- `grading.py` と `advice.py` は新規実装
- SM-2 グレード定義 (0-5) は `grading.py` に埋め込み
- `advice.py` のプロンプトは事前集計データ (ReviewSummary) を埋め込む方式
- `__init__.py` で全シンボルを再エクスポートし、既存 import パスの後方互換性を維持
