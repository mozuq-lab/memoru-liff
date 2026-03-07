# Feature Ideas

機能アイデア文書の入口。

このディレクトリでは、アイデアを次の 4 層で管理する。

- `backlog.md`
  - 近い将来に仕様化・優先度付けを検討する候補
  - 実装イメージや依存関係まである程度具体化されているもの
- `incubator.md`
  - 現実的だが、まだ優先順位や仕様が固まっていない構想
  - 複数のブレスト文書から重複テーマを統合した整理メモ
- `wild.md`
  - 実験色・挑発性・演出性が強いアイデア置き場
  - そのまま実装前提ではなく、発想のストックとして扱う
- `archive/`
  - 過去のブレスト原文や提案メモの保存場所
  - 履歴や発想の文脈を残すため、要約ではなく原文を保管する

## 運用ルール

- 新しいアイデアをまず残すときは `incubator.md` か `wild.md`
- 実装候補として現実味が出たら `backlog.md` へ昇格
- 実際に着手するときは `docs/spec/<slug>/`, `docs/design/<slug>/`, `docs/tasks/<slug>/` へ移す
- 会話ログや単発の提案原文は `archive/` に置く

## 整理元

今回の整理では、以下のトップレベル文書を集約対象とした。

- `docs/feature-backlog.md`
- `docs/feature-ideas-advanced.md`
- `docs/feature-ideas-claude-proposals.md`
- `docs/feature-ideas-brainstorm-2026-03-07.md`
- `docs/feature-ideas-wild.md`
