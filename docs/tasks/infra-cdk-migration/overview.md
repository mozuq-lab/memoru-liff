# infra-cdk-migration タスク概要

**作成日**: 2026-03-02
**推定工数**: 32時間（4日）
**総タスク数**: 8件

## 関連文書

- **要件定義書**: [requirements.md](../../spec/infra-cdk-migration/requirements.md)
- **設計文書**: [architecture.md](../../design/infra-cdk-migration/architecture.md)
- **データフロー図**: [dataflow.md](../../design/infra-cdk-migration/dataflow.md)
- **コンテキストノート**: [note.md](../../spec/infra-cdk-migration/note.md)

## フェーズ構成

| フェーズ | 成果物 | タスク数 | 工数 | ファイル |
|---------|--------|----------|------|----------|
| Phase 1 | CDK プロジェクト完成・旧テンプレート削除 | 8件 | 32h | [TASK-0126~0133](#phase-1-cdk-移行実装) |

## タスク番号管理

**使用済みタスク番号**: TASK-0126 ~ TASK-0133
**次回開始番号**: TASK-0134

## 全体進捗

- [ ] Phase 1: CDK 移行実装

## マイルストーン

- **M1: CDK 基盤完成**: CDK プロジェクト初期化・3スタック実装完了
- **M2: 検証完了**: cdk synth 全スタック成功・ドキュメント更新完了
- **M3: クリーンアップ完了**: 旧テンプレート削除・最終整理完了

---

## Phase 1: CDK 移行実装

**目標**: 既存 CloudFormation テンプレートを CDK に完全移行し、旧テンプレートを削除する
**成果物**: CDK プロジェクト（3スタック）、Bedrock モデル更新、ドキュメント更新

### タスク一覧

- [ ] [TASK-0126: CDK プロジェクト初期化](TASK-0126.md) - 2h (DIRECT) 🔵
- [ ] [TASK-0127: Cognito スタック実装](TASK-0127.md) - 4h (DIRECT) 🔵
- [ ] [TASK-0128: LIFF Hosting スタック実装](TASK-0128.md) - 6h (DIRECT) 🔵
- [ ] [TASK-0129: Keycloak スタック実装](TASK-0129.md) - 8h (DIRECT) 🔵
- [ ] [TASK-0130: CDK App エントリポイント・環境設定](TASK-0130.md) - 4h (DIRECT) 🔵
- [ ] [TASK-0131: Backend Bedrock モデル ID 更新](TASK-0131.md) - 2h (DIRECT) 🔵
- [ ] [TASK-0132: cdk synth 検証・ドキュメント更新](TASK-0132.md) - 4h (DIRECT) 🔵
- [ ] [TASK-0133: 旧 CloudFormation テンプレート削除](TASK-0133.md) - 2h (DIRECT) 🔵

### 依存関係

```
TASK-0126 → TASK-0127
TASK-0126 → TASK-0128
TASK-0126 → TASK-0129
TASK-0127 → TASK-0130
TASK-0128 → TASK-0130
TASK-0129 → TASK-0130
TASK-0130 → TASK-0132
TASK-0131 → TASK-0132
TASK-0132 → TASK-0133
```

### 並行実行可能なタスク

- **グループ A** (TASK-0126 完了後): TASK-0127, TASK-0128, TASK-0129 は並行実装可能
- **グループ B** (独立): TASK-0131 は他タスクに依存せず単独実行可能

---

## 信頼性レベルサマリー

### 全タスク統計

- **総タスク数**: 8件
- 🔵 **青信号**: 8件 (100%)
- 🟡 **黄信号**: 0件 (0%)
- 🔴 **赤信号**: 0件 (0%)

### タスク内項目統計

| タスク | 🔵 青 | 🟡 黄 | 🔴 赤 | 合計 |
|--------|-------|-------|-------|------|
| TASK-0126 | 4 | 0 | 0 | 4 |
| TASK-0127 | 5 | 0 | 0 | 5 |
| TASK-0128 | 6 | 0 | 0 | 6 |
| TASK-0129 | 8 | 0 | 0 | 8 |
| TASK-0130 | 2 | 1 | 0 | 3 |
| TASK-0131 | 3 | 0 | 0 | 3 |
| TASK-0132 | 2 | 2 | 0 | 4 |
| TASK-0133 | 4 | 0 | 0 | 4 |
| **合計** | **34** | **3** | **0** | **37** |

- 🔵 **青信号**: 34項目 (92%)
- 🟡 **黄信号**: 3項目 (8%)
- 🔴 **赤信号**: 0項目 (0%)

**品質評価**: ✅ 高品質

## クリティカルパス

```
TASK-0126 → TASK-0129 → TASK-0130 → TASK-0132 → TASK-0133
```

**クリティカルパス工数**: 20時間
**並行作業可能工数**: 12時間（TASK-0127 + TASK-0128 + TASK-0131）

## 次のステップ

タスクを実装するには:
- 全タスク順番に実装: `/tsumiki:kairo-implement`
- 特定タスクを実装: `/tsumiki:kairo-implement TASK-0126`
