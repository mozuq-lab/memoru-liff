# code-review-remediation タスク概要

**作成日**: 2026-02-15
**プロジェクト期間**: 2.5 週間（11.5 日）
**推定工数**: 92 時間
**総タスク数**: 19 件

## 関連文書

- **要件定義書**: [📋 requirements.md](../../spec/code-review-remediation/requirements.md)
- **設計文書**: [📐 architecture.md](../../design/code-review-remediation/architecture.md)
- **API仕様**: [🔌 api-endpoints.md](../../design/code-review-remediation/api-endpoints.md)
- **データフロー図**: [🔄 dataflow.md](../../design/code-review-remediation/dataflow.md)
- **コンテキストノート**: [📝 note.md](../../spec/code-review-remediation/note.md)
- **コードレビュー結果**: [📋 CODE_REVIEW_2026-02-15.md](../../CODE_REVIEW_2026-02-15.md)

## フェーズ構成

| フェーズ | 期間 | 成果物 | タスク数 | 工数 | ファイル |
|---------|------|--------|----------|------|----------|
| Phase 1 | 1 週間 | Critical 7 件修正完了 | 7 件 | 32h | [TASK-0023~0029](#phase-1-critical-修正) |
| Phase 2 | 1.5 週間 | High 12 件修正完了 | 12 件 | 60h | [TASK-0030~0041](#phase-2-high-修正) |

## タスク番号管理

**使用済みタスク番号**: TASK-0023 ~ TASK-0041
**次回開始番号**: TASK-0042

## 全体進捗

- [x] Phase 1: Critical 修正（7 タスク）
- [ ] Phase 2: High 修正（12 タスク）

## マイルストーン

- **M1: Critical 修正完了**: Phase 1 全タスク完了 — API 契約整合性・認証フロー・セキュリティ・IAM 権限修正
- **M2: High 修正完了**: Phase 2 全タスク完了 — データ整合性・パフォーマンス・インフラ最適化

---

## Phase 1: Critical 修正

**期間**: 1 週間（4.5 日）
**目標**: 本番デプロイ前に必須の Critical 7 件を修正
**成果物**: API 契約統一、認証フロー完成、セキュリティ修正、IAM 権限修正

### タスク一覧

| 状態 | タスク | 工数 | タイプ | 信頼性 |
|------|--------|------|--------|--------|
| [x] | [TASK-0023: C-01 APIルート統一](TASK-0023.md) | 4h | DIRECT | 🔵 |
| [x] | [TASK-0024: C-02 APIレスポンス契約統一](TASK-0024.md) | 8h | TDD | 🔵 |
| [x] | [TASK-0025: C-03 OIDCコールバック実装](TASK-0025.md) | 4h | TDD | 🔵 |
| [x] | [TASK-0026: C-04 DuePush IAM権限修正](TASK-0026.md) | 4h | DIRECT | 🔵 |
| [x] | [TASK-0027: C-05 204レスポンス処理修正](TASK-0027.md) | 4h | TDD | 🔵 |
| [x] | [TASK-0028: C-06 LINE署名タイミング攻撃対策](TASK-0028.md) | 4h | TDD | 🔵 |
| [x] | [TASK-0029: C-07 環境変数バリデーション有効化](TASK-0029.md) | 4h | TDD | 🔵 |

### Phase 1 完了条件

- [x] 全 7 タスクが完了
- [x] 全テストがパス（カバレッジ 80% 以上）
- [x] 回帰テストに問題なし

### 依存関係

```
TASK-0023 (C-01) → TASK-0024 (C-02)
TASK-0025 (C-03) → TASK-0037 (H-08), TASK-0038 (H-09)  [Phase 2]
TASK-0026 (C-04) → TASK-0034 (H-05)  [Phase 2]
TASK-0027 (C-05) → TASK-0037 (H-08)  [Phase 2]
TASK-0028 (C-06) — 独立
TASK-0029 (C-07) — 独立
```

**並行実行可能**: TASK-0025, TASK-0026, TASK-0027, TASK-0028, TASK-0029 は TASK-0023 と並行実行可能

---

## Phase 2: High 修正

**期間**: 1.5 週間（7 日）
**目標**: High 12 件の修正完了（データ整合性・パフォーマンス・インフラ最適化）
**成果物**: datetime 統一、トークンリフレッシュ、Race Condition 対策、インフラコスト最適化

### タスク一覧

| 状態 | タスク | 工数 | タイプ | 信頼性 |
|------|--------|------|--------|--------|
| [x] | [TASK-0030: H-01 datetime統一](TASK-0030.md) | 4h | TDD | 🔵 |
| [x] | [TASK-0031: H-02 CSP強化](TASK-0031.md) | 4h | DIRECT | 🔵 |
| [x] | [TASK-0032: H-03 Keycloak HTTPS強制](TASK-0032.md) | 4h | DIRECT | 🔵 |
| [x] | [TASK-0033: H-04 LINE連携解除API](TASK-0033.md) | 4h | TDD | 🔵 |
| [x] | [TASK-0034: H-05 通知cron修正](TASK-0034.md) | 4h | DIRECT | 🔵 |
| [x] | [TASK-0035: H-06 Race Condition対策](TASK-0035.md) | 4h | TDD | 🔵 |
| [x] | [TASK-0036: H-07 Bedrockリトライジッター](TASK-0036.md) | 4h | TDD | 🔵 |
| [x] | [TASK-0037: H-08 Tokenリフレッシュ](TASK-0037.md) | 8h | TDD | 🟡 |
| [x] | [TASK-0038: H-09 ProtectedRoute修正](TASK-0038.md) | 4h | TDD | 🔵 |
| [ ] | [TASK-0039: H-10 Contextメモ化](TASK-0039.md) | 4h | TDD | 🔵 |
| [ ] | [TASK-0040: H-11 NAT Gateway最適化](TASK-0040.md) | 4h | DIRECT | 🟡 |
| [ ] | [TASK-0041: H-12 CloudWatch Logs保存期間設定](TASK-0041.md) | 4h | DIRECT | 🟡 |

### Phase 2 完了条件

- [ ] 全 12 タスクが完了
- [ ] 全テストがパス（カバレッジ 80% 以上）
- [ ] 回帰テストに問題なし

### 依存関係

```
TASK-0025 (C-03) + TASK-0027 (C-05) → TASK-0037 (H-08)
TASK-0026 (C-04) → TASK-0034 (H-05)

その他は独立して実行可能:
TASK-0030 (H-01) — 独立
TASK-0031 (H-02) — 独立
TASK-0032 (H-03) — 独立
TASK-0033 (H-04) — 独立
TASK-0035 (H-06) — 独立
TASK-0036 (H-07) — 独立
TASK-0038 (H-09) — 独立 (TASK-0025 推奨)
TASK-0039 (H-10) — 独立
TASK-0040 (H-11) — 独立
TASK-0041 (H-12) — 独立
```

**並行実行可能**: 大部分のタスクが独立。TASK-0037 のみ Phase 1 の 2 タスクに依存。

---

## 信頼性レベルサマリー

### 全タスク統計

- **総タスク数**: 19 件
- 🔵 **青信号**: 16 件 (84%)
- 🟡 **黄信号**: 3 件 (16%)
- 🔴 **赤信号**: 0 件 (0%)

### フェーズ別信頼性

| フェーズ | 🔵 青 | 🟡 黄 | 🔴 赤 | 合計 |
|---------|-------|-------|-------|------|
| Phase 1 | 7 | 0 | 0 | 7 |
| Phase 2 | 9 | 3 | 0 | 12 |

**品質評価**: ✅ 高品質（青信号が 84%、赤信号なし）

### 🟡 黄信号タスクの詳細

| タスク | 理由 |
|--------|------|
| TASK-0037 (H-08) | Token リフレッシュは interceptor パターン確定済みだが、LIFF WebView での silentRenew 動作は実装時に検証必要 |
| TASK-0040 (H-11) | NAT Gateway の条件付き削除。リソース名・サブネット構成は実装時に確認が必要 |
| TASK-0041 (H-12) | CloudWatch Logs 保存期間。具体的な Lambda 関数名は実装時に template.yaml を確認 |

## クリティカルパス

```
TASK-0023 → TASK-0024 → Phase 1 完了
                                    ↘
TASK-0025 + TASK-0027 ────────────→ TASK-0037 → Phase 2 完了
```

**クリティカルパス工数**: 24 時間（TASK-0023 → TASK-0024 → TASK-0037）
**並行作業可能工数**: 68 時間

## タスクタイプ分布

| タイプ | 件数 | 割合 |
|--------|------|------|
| TDD | 13 件 | 68% |
| DIRECT | 6 件 | 32% |

## 次のステップ

タスクを実装するには:
- 全タスク順番に実装: `/tsumiki:kairo-implement`
- 特定タスクを実装: `/tsumiki:kairo-implement TASK-0023`
