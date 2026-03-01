# Claude Code 固有ガイドライン

> 共通ルールは `AGENTS.md` を参照。このファイルは Claude Code 固有の追加ルールのみ記載。

## Tsumiki ワークフロー

Claude Code では Tsumiki プラグインの Kairo ワークフローも使用できる。

### タスク実装の流れ

1. **タスクファイルの確認**: `docs/tasks/{要件名}/TASK-XXXX.md` を読む
2. **タスクタイプに応じた実装**:
   - **TDD タスク**: `/tsumiki:tdd-red` → `/tsumiki:tdd-green` → `/tsumiki:tdd-refactor`
   - **DIRECT タスク**: `/tsumiki:direct-setup` → `/tsumiki:direct-verify`
3. **タスクファイルの更新**: 完了条件のチェックボックスを `[x]` に更新
4. **タスク完了後にコミット**

### コミットメッセージ形式

```
TASK-XXXX: タスク名

- 実装内容1
- 実装内容2

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```
