# Cognito LINE Login 外部 IdP 統合 タスク概要

**作成日**: 2026-03-03
**推定工数**: 5時間
**総タスク数**: 2件

## 関連文書

- **要件定義書**: [requirements.md](../../spec/cognito-line-login/requirements.md)
- **設計文書**: [architecture.md](../../design/cognito-line-login/architecture.md)
- **データフロー図**: [dataflow.md](../../design/cognito-line-login/dataflow.md)
- **コンテキストノート**: [note.md](../../spec/cognito-line-login/note.md)
- **デプロイ手順書**: [deployment-guide-dev.md](../../deployment-guide-dev.md)

## フェーズ構成

| フェーズ | 成果物 | タスク数 | 工数 | ファイル |
|---------|--------|----------|------|----------|
| Phase 1 - CDK 実装 | LINE Login 外部 IdP の CDK 設定 | 2件 | 5h | [TASK-0146~0147](#phase-1-cdk-実装) |

## タスク番号管理

**使用済みタスク番号**: TASK-0146 ~ TASK-0147
**次回開始番号**: TASK-0148

## 全体進捗

- [ ] Phase 1: CDK 実装

## マイルストーン

- **M1: CDK 実装完了**: CognitoStack に LINE Login 外部 IdP が登録可能になる

---

## Phase 1: CDK 実装

**目標**: Cognito UserPool に LINE Login を外部 OIDC IdP として CDK で登録可能にする
**成果物**: `cognito-stack.ts` + `app.ts` の更新、テスト追加

### タスク一覧

| 状態 | タスク | 工数 | タイプ | 信頼性 |
|------|--------|------|--------|--------|
| [ ] | [TASK-0146: CognitoStack LINE Login 外部 IdP 実装](TASK-0146.md) | 4h | TDD | 🔵 |
| [ ] | [TASK-0147: app.ts LINE Login 環境変数設定](TASK-0147.md) | 1h | DIRECT | 🔵 |

### 依存関係

```
TASK-0146 → TASK-0147
```

---

## 信頼性レベルサマリー

### 全タスク統計

- **総タスク数**: 2件
- 🔵 **青信号**: 2件 (100%)
- 🟡 **黄信号**: 0件 (0%)
- 🔴 **赤信号**: 0件 (0%)

### タスク内項目統計

- **総項目数**: 11項目
- 🔵 **青信号**: 10項目 (91%)
- 🟡 **黄信号**: 1項目 (9%) — LINE OIDC エンドポイント URL
- 🔴 **赤信号**: 0項目 (0%)

**品質評価**: ✅ 高品質

## クリティカルパス

```
TASK-0146 → TASK-0147
```

**クリティカルパス工数**: 5時間

## 次のステップ

タスクを実装するには:
- 全タスク順番に実装: `/tsumiki:kairo-implement`
- 特定タスクを実装: `/tsumiki:kairo-implement TASK-0146`
