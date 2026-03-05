# 001-card-speech バグ修正 要件定義書（軽量版）

## 概要

`001-card-speech` ブランチのコードレビュー（Claude Code + Codex 共同レビュー）で発見された不具合・改善点を修正する。対象は Critical 1件、High 1件、Medium 3件の計5件。

## 関連文書

- **ヒアリング記録**: [interview-record.md](interview-record.md)
- **レビュー文書**: [../../review/001-card-speech-review.md](../../review/001-card-speech-review.md)
- **元仕様**: [../../../specs/001-card-speech/spec.md](../../../specs/001-card-speech/spec.md)
- **Hook契約**: [../../../specs/001-card-speech/contracts/hooks.md](../../../specs/001-card-speech/contracts/hooks.md)
- **Component契約**: [../../../specs/001-card-speech/contracts/components.md](../../../specs/001-card-speech/contracts/components.md)

**【信頼性レベル凡例】**:

- 🔵 **青信号**: 仕様書・レビュー文書・ユーザヒアリングを参考にした確実な要件
- 🟡 **黄信号**: 仕様書・レビュー文書から妥当な推測による要件
- 🔴 **赤信号**: 仕様書・レビュー文書にない推測による要件

## 主要機能要件

### 必須機能（Must Have）

- REQ-001: 読み上げ中に SpeechButton をタップした場合、システムは再生を停止しなければならない（トグル動作）。現在は再度 speak() が呼ばれ再生が再開される不具合がある 🔵 *spec.md US1 Acceptance Scenario 3「再度読み上げボタンをタップする → 再生が停止される（トグル動作）」より*
- REQ-002: useSpeechSettings は userId が undefined から有効値に変化した場合、localStorage から設定を再読み込みしなければならない。現在は useState 初期化時の1回のみ loadSettings を呼ぶため、認証完了後の設定が反映されない 🔵 *contracts/hooks.md useSpeechSettings Contract + レビュー H-1 より*

### 改善機能（Should Have）

- REQ-101: SettingsPage の自動読み上げトグルスイッチ（`role="switch"`）は、スクリーンリーダーが認識できるアクセシブル名を持たなければならない 🔵 *レビュー M-1 + WAI-ARIA switch パターンより*
- REQ-102: useSpeechSettings の updateSettings 内の localStorage.setItem は、Safari Private Mode や容量超過時の例外を安全に処理しなければならない 🟡 *レビュー M-2 + loadSettings 側の try/catch パターンからの妥当な推測*
- REQ-103: 以下の統合テストを追加しなければならない: (a) 停止トグル動作、(b) userId 遅延確定時の設定再読み込み 🔵 *レビュー M-4 + REQ-001/REQ-002 の不具合検出に必要*

### 基本的な制約

- REQ-401: 既存のテストケースを破壊してはならない 🔵 *CLAUDE.md テストカバレッジ 80% 以上ルールより*
- REQ-402: FlipCard の speechProps は引き続きオプショナルとし、後方互換を維持する 🔵 *contracts/components.md「speechProps が未指定の場合、既存の動作と完全に同じ」より*

## 簡易ユーザーストーリー

### ストーリー 1: 停止トグル修正（REQ-001）

**私は** 復習中のユーザー **として**
**読み上げ中にボタンを再タップして音声を停止したい**
**そうすることで** 必要なときだけ音声を聞くことができる

**関連要件**: REQ-001, REQ-103(a)

### ストーリー 2: 設定の確実な読み込み（REQ-002）

**私は** ログイン後に復習を始めるユーザー **として**
**以前保存した音声設定（自動読み上げ ON、速度 1.5x 等）が正しく反映されてほしい**
**そうすることで** 毎回設定し直す手間なく快適に学習できる

**関連要件**: REQ-002, REQ-103(b)

### ストーリー 3: アクセシビリティ改善（REQ-101）

**私は** スクリーンリーダーを使用するユーザー **として**
**自動読み上げスイッチが何のコントロールか音声で把握したい**
**そうすることで** 設定画面を問題なく操作できる

**関連要件**: REQ-101

## 基本的な受け入れ基準

### REQ-001: 停止トグル修正

**Given**: 復習画面でカードの読み上げが再生中である
**When**: ユーザーが同じ読み上げボタンを再タップする
**Then**: 再生が停止され、ボタンが再生アイコン（▶）に戻る

**テストケース**:

- [ ] 正常系: 表面読み上げ中にボタンタップ → 停止
- [ ] 正常系: 裏面読み上げ中にボタンタップ → 停止
- [ ] 正常系: 停止後に再タップ → 再度読み上げ開始

### REQ-002: userId 遅延確定時の設定再読み込み

**Given**: ユーザーが autoPlay=true, rate=1.5 を保存済みで、認証が非同期で完了する
**When**: userId が undefined → 有効値に変化する
**Then**: localStorage から保存済み設定が読み込まれ、settings が更新される

**テストケース**:

- [ ] 正常系: userId undefined → 有効値変化時に loadSettings が実行される
- [ ] 正常系: userId が最初から有効な場合は初期化時に正しく読み込まれる（既存動作維持）
- [ ] 異常系: userId が undefined のまま変化しない場合はデフォルト設定のまま

### REQ-101: aria-label 追加

**Given**: SettingsPage の音声設定セクションが表示されている
**When**: スクリーンリーダーが自動読み上げスイッチにフォーカスする
**Then**: 「自動読み上げ」というアクセシブル名が読み上げられる

**テストケース**:

- [ ] 正常系: switch ボタンに aria-label="自動読み上げ" が設定されている

### REQ-102: localStorage.setItem の例外処理

**Given**: localStorage への書き込みが例外を投げる環境（Safari Private Mode 等）
**When**: ユーザーが音声設定を変更する
**Then**: state は正常に更新され、アプリがクラッシュしない

**テストケース**:

- [ ] 異常系: setItem が throw しても state が更新される
- [ ] 異常系: setItem が throw してもエラーがユーザーに表示されない

## 最小限の非機能要件

- **パフォーマンス**: 停止トグルのレスポンスは即座（100ms以内）であること 🟡 *Web Speech API の cancel() は同期的に動作するため*
- **後方互換**: FlipCard の speechProps なし利用パターンが引き続き動作すること 🔵 *contracts/components.md より*
