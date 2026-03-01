# day-boundary-fix コンテキストノート

**作成日**: 2026-03-01

## 技術スタック

- **バックエンド**: Python 3.12 / AWS SAM (Lambda, API Gateway, DynamoDB)
- **フロントエンド**: React 19 + TypeScript 5.x / Vite 7 / Tailwind CSS 4
- **認証**: Keycloak (OIDC + PKCE)
- **SRS**: SM-2 アルゴリズム

## 概要

`feature/day-boundary-spec` ブランチのコードレビュー（Claude + Codex）で発見された指摘事項を修正する。

## 関連文書

- **コードレビュー結果**: [CODE_REVIEW_day-boundary.md](../../reviews/CODE_REVIEW_day-boundary.md)
- **元要件定義**: [day-boundary requirements.md](../day-boundary/requirements.md)
- **元設計文書**: [day-boundary architecture.md](../../design/day-boundary/architecture.md)

## 修正対象ファイル

### バックエンド
| ファイル | 修正内容 |
|---------|---------|
| `backend/src/services/srs.py` | `calculate_next_review_boundary` に Decimal → int 変換と範囲チェック追加。`zoneinfo` import をモジュールレベルに移動。ZoneInfo 失敗時フォールバック追加 |
| `backend/src/models/user.py` | `validate_timezone` に ZoneInfo 実在検証追加。`from_dynamodb_item` のデフォルト settings に `day_start_hour` 追加 |
| `backend/tests/unit/test_srs.py` | Decimal 入力テスト、不正 timezone テスト追加 |
| `backend/tests/unit/test_review_service.py` | 弱い `assert A or B` の修正 |
| `backend/tests/unit/test_user_models.py` | 不正 timezone のバリデーションテスト追加 |

### ドキュメント
| ファイル | 修正内容 |
|---------|---------|
| `docs/spec/day-boundary/interview-record.md` | Q4 の選択肢範囲を 0-23 に更新 |

## 既存パターン

- DynamoDB は Number 型を Python `Decimal` として返す
- `User.from_dynamodb_item()` は settings dict をそのまま受け取る
- `UserSettingsRequest` で Pydantic バリデーション
- `zoneinfo.ZoneInfo` による TZ 変換は通知サービスで既存パターンあり

## 注意事項

- moto テストでは DynamoDB が Python int を返すため、Decimal 問題はテストでは再現しにくい
- timezone の ZoneInfo 検証は `ZoneInfoNotFoundError` と `KeyError` の両方を catch する必要がある
- `due_date` の UTC vs ローカル日付問題は今回のスコープ外（後続タスク）
