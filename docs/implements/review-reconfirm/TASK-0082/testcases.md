# TASK-0082: UIコンポーネント実装 - テストケース定義書

**タスクID**: TASK-0082
**機能名**: reconfirm loop UI components
**要件名**: review-reconfirm
**作成日**: 2026-02-28

---

## 開発言語・フレームワーク

- **プログラミング言語**: TypeScript (React 18.x)
  - **言語選択の理由**: プロジェクト全体が TypeScript で統一されており、フロントエンドは React + Vite で構築されている
  - **テストに適した機能**: JSX のレンダリングテスト、型安全なモック作成が可能
- **テストフレームワーク**: Vitest + React Testing Library + @testing-library/user-event
  - **フレームワーク選択の理由**: プロジェクト既存のテスト環境（GradeButtons.test.tsx, ReviewComplete.test.tsx 等）と一貫性を保つ
  - **テスト実行環境**: `cd frontend && npx vitest run` で実行、jsdom 環境
- 🔵 既存プロジェクトの設定を踏襲

---

## テストファイルと実装ファイルの対応

| テストファイル | 実装ファイル | テスト種別 |
|---------------|-------------|-----------|
| `frontend/src/components/__tests__/GradeButtons.test.tsx` | `frontend/src/components/GradeButtons.tsx` | 既存テストに追加 |
| `frontend/src/components/__tests__/ReconfirmBadge.test.tsx` | `frontend/src/components/ReconfirmBadge.tsx` | 新規テスト |
| `frontend/src/components/__tests__/ReviewResultItem.test.tsx` | `frontend/src/components/ReviewResultItem.tsx` | 新規テスト |
| `frontend/src/components/__tests__/ReviewComplete.test.tsx` | `frontend/src/components/ReviewComplete.tsx` | 既存テストに追加 |

---

## 1. GradeButtons 再確認モード - 正常系テストケース

### TC-GB-001: isReconfirmMode=true で「覚えた」「覚えていない」の2択ボタンが表示される 🔵

- **テスト名**: 再確認モードで2択ボタンが表示される
  - **何をテストするか**: `isReconfirmMode=true` 時に「覚えた」「覚えていない」ボタンが DOM に存在すること
  - **期待される動作**: 2つのボタンがそれぞれ正しいテキストでレンダリングされる
- **入力値**: `isReconfirmMode=true`, `onReconfirmRemembered=vi.fn()`, `onReconfirmForgotten=vi.fn()`, `disabled=false`
  - **入力データの意味**: 再確認モードが有効な状態で、ハンドラが設定されている標準的なケース
- **期待される結果**: `screen.getByRole('button', { name: '覚えた' })` と `screen.getByRole('button', { name: '覚えていない' })` が DOM に存在する
  - **期待結果の理由**: 要件定義書 REQ-002「再確認カード表示時に覚えた/覚えていないの2択を表示」に合致
- **テストの目的**: 再確認モードUIの基本表示を確認
  - **確認ポイント**: ボタンテキストが正確に「覚えた」「覚えていない」であること
- 🔵 *GradeButtons.tsx 既存実装（20-46行目）で確認済み、受け入れ基準 TC-002-01 に対応*

### TC-GB-002: isReconfirmMode=true で6段階評価ボタン（0-5）が非表示 🔵

- **テスト名**: 再確認モードで6段階評価ボタンが非表示になる
  - **何をテストするか**: `isReconfirmMode=true` 時に grade 0-5 の評価ボタンが表示されないこと
  - **期待される動作**: 早期リターンパターンにより、6段階UIブロックがレンダリングされない
- **入力値**: `isReconfirmMode=true`, `onReconfirmRemembered=vi.fn()`, `onReconfirmForgotten=vi.fn()`, `disabled=false`
  - **入力データの意味**: 再確認モードが有効な状態
- **期待される結果**: `screen.queryByRole('button', { name: /^0/ })` ～ `screen.queryByRole('button', { name: /^5/ })` が全て null
  - **期待結果の理由**: GradeButtons.tsx の早期リターン（20行目 `if (isReconfirmMode)`）により、6段階UIブロック（49-82行目）は到達しない
- **テストの目的**: 再確認モードで不要な評価ボタンが混在しないことを確認
  - **確認ポイント**: 6つの grade ボタン全てが非表示であること（0から5まで全数チェック）
- 🔵 *GradeButtons.tsx の早期リターンパターンで確認済み*

### TC-GB-003: isReconfirmMode=true でスキップボタンが非表示 🔵

- **テスト名**: 再確認モードでスキップボタンが非表示になる
  - **何をテストするか**: `isReconfirmMode=true` 時にスキップボタンが表示されないこと
  - **期待される動作**: 早期リターンにより、スキップボタン部分がレンダリングされない
- **入力値**: `isReconfirmMode=true`, `onSkip=vi.fn()`, `onReconfirmRemembered=vi.fn()`, `onReconfirmForgotten=vi.fn()`, `disabled=false`
  - **入力データの意味**: onSkip が渡されていても、再確認モードではスキップボタンが出ないことを検証
- **期待される結果**: `screen.queryByRole('button', { name: /スキップ/ })` が null
  - **期待結果の理由**: 要件定義書 REQ-102「再確認モードでスキップボタン非表示」に合致。早期リターンによりスキップボタンは到達不能
- **テストの目的**: 再確認モードでスキップ操作が利用不可であることを確認
  - **確認ポイント**: onSkip が渡されていてもスキップボタンが表示されないこと
- 🔵 *要件定義書 REQ-102、受け入れ基準 TC-102-01 に対応*

### TC-GB-004: isReconfirmMode=false で従来通りの6段階評価UI（リグレッション防止） 🔵

- **テスト名**: 通常モードで6段階評価ボタンとスキップボタンが従来通り表示される
  - **何をテストするか**: `isReconfirmMode=false`（またはデフォルト未指定）で従来UIが変わらないこと
  - **期待される動作**: grade 0-5 の6ボタン + スキップボタンが表示される
- **入力値**: `isReconfirmMode=false`（または prop 未設定）, `onGrade=vi.fn()`, `onSkip=vi.fn()`, `disabled=false`
  - **入力データの意味**: 従来の通常モード（再確認モード無効）
- **期待される結果**: grade 0-5 のボタン6つ + スキップボタン1つが表示される。「覚えた」「覚えていない」ボタンは表示されない
  - **期待結果の理由**: 要件定義書 REQ-103「quality 3-5 は再確認ループに入らない → 通常モード非破壊」に合致
- **テストの目的**: 再確認モード追加による既存UIへのリグレッションがないことを確認
  - **確認ポイント**: 既存テスト（GradeButtons.test.tsx 8件）との互換性
- 🔵 *既存テストパターン（GradeButtons.test.tsx 18-28行目）の拡張*

### TC-GB-005: 「覚えた」ボタンクリックで onReconfirmRemembered が呼ばれる 🔵

- **テスト名**: 覚えたボタンのクリックでコールバックが発火する
  - **何をテストするか**: 「覚えた」ボタンをクリックした際に `onReconfirmRemembered` ハンドラが1回だけ呼ばれること
  - **期待される動作**: userEvent.click 後に onReconfirmRemembered が calledOnce
- **入力値**: `isReconfirmMode=true`, `onReconfirmRemembered=vi.fn()`, `disabled=false`
  - **入力データの意味**: 再確認モードで有効な状態
- **期待される結果**: `expect(onReconfirmRemembered).toHaveBeenCalledOnce()`
  - **期待結果の理由**: GradeButtons.tsx 26行目 `onClick={onReconfirmRemembered}` の動作確認
- **テストの目的**: ボタンとハンドラの正しい接続を確認
  - **確認ポイント**: 呼び出し回数が1回であること
- 🔵 *GradeButtons.tsx 実装（26行目）で確認済み*

### TC-GB-006: 「覚えていない」ボタンクリックで onReconfirmForgotten が呼ばれる 🔵

- **テスト名**: 覚えていないボタンのクリックでコールバックが発火する
  - **何をテストするか**: 「覚えていない」ボタンをクリックした際に `onReconfirmForgotten` ハンドラが1回だけ呼ばれること
  - **期待される動作**: userEvent.click 後に onReconfirmForgotten が calledOnce
- **入力値**: `isReconfirmMode=true`, `onReconfirmForgotten=vi.fn()`, `disabled=false`
  - **入力データの意味**: 再確認モードで有効な状態
- **期待される結果**: `expect(onReconfirmForgotten).toHaveBeenCalledOnce()`
  - **期待結果の理由**: GradeButtons.tsx 36行目 `onClick={onReconfirmForgotten}` の動作確認
- **テストの目的**: ボタンとハンドラの正しい接続を確認
  - **確認ポイント**: 呼び出し回数が1回であること
- 🔵 *GradeButtons.tsx 実装（36行目）で確認済み*

---

## 2. GradeButtons 再確認モード - 異常系テストケース

### TC-GB-007: disabled=true で再確認モード両ボタンが disabled 状態になる 🔵

- **テスト名**: disabled 状態で覚えた・覚えていないボタンが無効化される
  - **エラーケースの概要**: 送信中（isSubmitting=true）にボタン連打を防止する
  - **エラー処理の重要性**: 二重送信やレースコンディションの防止に必要
- **入力値**: `isReconfirmMode=true`, `disabled=true`, `onReconfirmRemembered=vi.fn()`, `onReconfirmForgotten=vi.fn()`
  - **不正な理由**: disabled 状態での操作
  - **実際の発生シナリオ**: ReviewPage で isSubmitting=true（API応答待ち中）に該当
- **期待される結果**: 両ボタンが `disabled` 属性を持つ（`toBeDisabled()`）
  - **エラーメッセージの内容**: N/A（UIの無効化表示のみ）
  - **システムの安全性**: ボタンが無効化されることで不正操作を防止
- **テストの目的**: disabled prop の再確認モードでの正しい伝播を確認
  - **品質保証の観点**: UX品質（二重送信防止）
- 🔵 *GradeButtons.tsx 実装（27-29行目, 37-39行目）で confirmed*

### TC-GB-008: disabled=true でクリックしても onReconfirmRemembered が呼ばれない 🔵

- **テスト名**: disabled 状態で覚えたボタンクリックしてもハンドラが発火しない
  - **エラーケースの概要**: disabled ボタンのクリックイベントが無視されること
  - **エラー処理の重要性**: HTML button の disabled 属性によりイベントが自動的にブロックされることを確認
- **入力値**: `isReconfirmMode=true`, `disabled=true`, `onReconfirmRemembered=vi.fn()`
  - **不正な理由**: disabled 状態での操作試行
  - **実際の発生シナリオ**: 高速タップでの連打シナリオ
- **期待される結果**: `expect(onReconfirmRemembered).not.toHaveBeenCalled()`
  - **エラーメッセージの内容**: N/A
  - **システムの安全性**: ハンドラが呼ばれないことで不正な状態遷移を防止
- **テストの目的**: disabled 状態でのイベントブロックを確認
  - **品質保証の観点**: 既存テスト（GradeButtons.test.tsx 88-96行目）と同じパターン
- 🔵 *既存テストパターン（disabled クリック防止）の再確認モード版*

### TC-GB-009: disabled=true でクリックしても onReconfirmForgotten が呼ばれない 🔵

- **テスト名**: disabled 状態で覚えていないボタンクリックしてもハンドラが発火しない
  - **エラーケースの概要**: disabled ボタンのクリックイベントが無視されること
  - **エラー処理の重要性**: 「覚えていない」側でも同様の保護が必要
- **入力値**: `isReconfirmMode=true`, `disabled=true`, `onReconfirmForgotten=vi.fn()`
  - **不正な理由**: disabled 状態での操作試行
  - **実際の発生シナリオ**: 高速タップでの連打シナリオ
- **期待される結果**: `expect(onReconfirmForgotten).not.toHaveBeenCalled()`
  - **エラーメッセージの内容**: N/A
  - **システムの安全性**: ハンドラが呼ばれないことで不正な状態遷移を防止
- **テストの目的**: 「覚えていない」ボタンでも disabled が正しく機能することを確認
  - **品質保証の観点**: 両ボタンの対称的な動作保証
- 🔵 *GradeButtons.tsx 実装（37行目 disabled={disabled}）で確認済み*

---

## 3. GradeButtons 再確認モード - 境界値テストケース

### TC-GB-010: isReconfirmMode 未指定（undefined）で従来モードが表示される 🔵

- **テスト名**: isReconfirmMode が未指定の場合に従来モードで表示される
  - **境界値の意味**: Props のオプショナルパラメータが undefined の場合のデフォルト動作
  - **境界値での動作保証**: `if (isReconfirmMode)` は undefined を falsy として扱い、通常UIをレンダリングする
- **入力値**: `isReconfirmMode` を prop として渡さない（`undefined`）
  - **境界値選択の根拠**: TypeScript で `isReconfirmMode?: boolean` と定義されているため、undefined が自然な境界
  - **実際の使用場面**: 既存コードで GradeButtons を使用している箇所では isReconfirmMode を渡していない
- **期待される結果**: 6段階評価ボタン + スキップボタンが表示される。「覚えた」「覚えていない」は非表示
  - **境界での正確性**: undefined は falsy であるため通常ブランチに入る
  - **一貫した動作**: `false` と `undefined` で同じ動作
- **テストの目的**: デフォルト動作が通常モードであることの保証
  - **堅牢性の確認**: 既存コードとの後方互換性
- 🔵 *GradeButtons.tsx Props 定義（5行目 `isReconfirmMode?: boolean`）と早期リターン条件より確認*

### TC-GB-011: 再確認ボタンの44px以上タップ領域保証 🟡

- **テスト名**: 再確認ボタンに min-h-[44px] クラスが適用されている
  - **境界値の意味**: WCAG 2.1 Level AAA のタップ領域最小値（44px x 44px）
  - **境界値での動作保証**: モバイルデバイスでの操作性を保証
- **入力値**: `isReconfirmMode=true`, `disabled=false`
  - **境界値選択の根拠**: NFR-201「44px 以上のタップ領域」
  - **実際の使用場面**: LINE LIFF アプリのモバイルユーザーが指でタップする場面
- **期待される結果**: 「覚えた」「覚えていない」両ボタンの className に `min-h-[44px]` が含まれる
  - **境界での正確性**: CSS クラスの存在確認
  - **一貫した動作**: 通常モードの採点ボタン（59行目）と同等のタップ領域を保証
- **テストの目的**: アクセシビリティ要件の充足を確認
  - **堅牢性の確認**: LIFF モバイル環境での操作性
- 🟡 *NFR-201 から妥当な推測。CSSクラスの存在チェックで検証（ピクセルサイズの実測はユニットテスト外）*

---

## 4. ReconfirmBadge - 正常系テストケース

### TC-RB-001: 「再確認」テキストが表示される 🔵

- **テスト名**: ReconfirmBadge が「再確認」テキストを表示する
  - **何をテストするか**: コンポーネントをレンダリングした際に「再確認」テキストが DOM に存在すること
  - **期待される動作**: span 要素として「再確認」テキストがレンダリングされる
- **入力値**: なし（パラメータ不要のプレゼンテーションコンポーネント）
  - **入力データの意味**: 常に同じ表示をする静的コンポーネント
- **期待される結果**: `screen.getByText('再確認')` が DOM に存在する
  - **期待結果の理由**: 要件定義書 REQ-101「再確認モードで再確認バッジ表示」に合致
- **テストの目的**: コンポーネントの基本レンダリングを確認
  - **確認ポイント**: テキスト内容が正確に「再確認」であること
- 🔵 *要件定義書 REQ-101、受け入れ基準 TC-101-01 に対応*

### TC-RB-002: 背景色スタイリングが適用されている 🔵

- **テスト名**: ReconfirmBadge に bg-blue-100 背景色クラスが適用されている
  - **何をテストするか**: バッジが視覚的に目立つ背景色を持つこと
  - **期待される動作**: className に `bg-blue-100` が含まれる
- **入力値**: なし
  - **入力データの意味**: 静的コンポーネントの見た目確認
- **期待される結果**: `screen.getByText('再確認')` の要素に `bg-blue-100` クラスが含まれる
  - **期待結果の理由**: 要件定義書 reconfirm-ui-requirements.md セクション2.2「背景色: bg-blue-100」に合致
- **テストの目的**: 視覚的な区別が実装されていることを確認
  - **確認ポイント**: 背景色クラスの存在（通常復習と区別するためのUIデザイン）
- 🔵 *reconfirm-ui-requirements.md セクション2.2 の仕様通り*

### TC-RB-003: テキスト色スタイリングが適用されている 🔵

- **テスト名**: ReconfirmBadge に text-blue-700 テキスト色クラスが適用されている
  - **何をテストするか**: バッジのテキスト色が仕様通りであること
  - **期待される動作**: className に `text-blue-700` が含まれる
- **入力値**: なし
  - **入力データの意味**: 静的コンポーネントの見た目確認
- **期待される結果**: `screen.getByText('再確認')` の要素に `text-blue-700` クラスが含まれる
  - **期待結果の理由**: reconfirm-ui-requirements.md セクション2.2「テキスト色: text-blue-700」
- **テストの目的**: テキスト色のカラーコントラスト要件を確認
  - **確認ポイント**: bg-blue-100 + text-blue-700 の組み合わせ
- 🔵 *reconfirm-ui-requirements.md セクション2.2 の仕様通り*

### TC-RB-004: バッジ形状が rounded-full（ピル型）である 🔵

- **テスト名**: ReconfirmBadge に rounded-full クラスが適用されている
  - **何をテストするか**: バッジの形状がピル型であること
  - **期待される動作**: className に `rounded-full` が含まれる
- **入力値**: なし
  - **入力データの意味**: 静的コンポーネントの形状確認
- **期待される結果**: `screen.getByText('再確認')` の要素に `rounded-full` クラスが含まれる
  - **期待結果の理由**: reconfirm-ui-requirements.md セクション2.2「形状: rounded-full（ピル型）」
- **テストの目的**: デザイン仕様通りの形状が実装されていることを確認
  - **確認ポイント**: ピル型バッジとして視覚的に認識できるデザイン
- 🔵 *reconfirm-ui-requirements.md セクション2.2 の仕様通り*

### TC-RB-005: コンポーネントが正しくエクスポートされている 🔵

- **テスト名**: ReconfirmBadge が named export でインポートできる
  - **何をテストするか**: `import { ReconfirmBadge } from '../ReconfirmBadge'` が成功すること
  - **期待される動作**: コンポーネントが function/component として存在する
- **入力値**: なし
  - **入力データの意味**: モジュールシステムの正しい動作
- **期待される結果**: `ReconfirmBadge` が truthy（undefined でない）かつ、レンダリング可能
  - **期待結果の理由**: 既存コンポーネントと同じ named export パターン
- **テストの目的**: モジュールエクスポートが正しいことを確認
  - **確認ポイント**: import が成功し、render() でエラーが出ないこと
- 🔵 *既存コンポーネントパターン（GradeButtons.tsx の `export const GradeButtons`）に合致*

---

## 5. ReviewResultItem 再確認表示 - 正常系テストケース

### TC-RRI-001: type='reconfirmed' で元の評価バッジが表示される 🔵

- **テスト名**: 再確認結果で元の評価グレードバッジが表示される
  - **何をテストするか**: `type='reconfirmed'` かつ `grade=2` のカードで、GRADE_DISPLAY_CONFIGS[2] に基づくバッジが表示されること
  - **期待される動作**: amber 色の `2` ラベルバッジがレンダリングされる
- **入力値**: `{ cardId: 'card-1', front: 'テスト問題', grade: 2, type: 'reconfirmed' }`
  - **入力データの意味**: quality 2 で評価された後、再確認で「覚えた」と回答したカード
- **期待される結果**: テキスト `2` を含むバッジ要素が DOM に存在し、`bg-amber-100` と `text-amber-700` クラスが適用されている
  - **期待結果の理由**: 要件定義書 REQ-501「元の評価（2）と再確認結果が両方表示される」に合致。GRADE_DISPLAY_CONFIGS[2] = `{ label: '2', bgClass: 'bg-amber-100', textClass: 'text-amber-700' }`
- **テストの目的**: 再確認カードの元評価が視覚的に確認できることを検証
  - **確認ポイント**: グレードバッジの label テキストとカラークラス
- 🔵 *要件定義書 REQ-501、受け入れ基準 TC-501-01 に対応*

### TC-RRI-002: type='reconfirmed' で「覚えた✔」サブラベルが表示される 🔵

- **テスト名**: 再確認結果で「覚えた✔」サブラベルが表示される
  - **何をテストするか**: `type='reconfirmed'` のカードで、「覚えた✔」テキストの `<p>` 要素が表示されること
  - **期待される動作**: 緑色テキスト（text-green-600）の「覚えた✔」サブラベルがレンダリングされる
- **入力値**: `{ cardId: 'card-1', front: 'テスト問題', grade: 1, type: 'reconfirmed' }`
  - **入力データの意味**: 再確認で「覚えた」として確認済みのカード
- **期待される結果**: `screen.getByText('覚えた✔')` が DOM に存在する
  - **期待結果の理由**: reconfirm-ui-requirements.md セクション2.4「サブラベル: 覚えた✔, text-xs text-green-600」
- **テストの目的**: 再確認結果の視覚表示を確認
  - **確認ポイント**: テキスト内容が「覚えた✔」（チェックマーク付き）であること
- 🔵 *reconfirm-ui-requirements.md セクション2.4 の仕様通り*

### TC-RRI-003: type='reconfirmed' で「次回: {date}」が表示されないこと 🔵

- **テスト名**: 再確認結果で次回復習日が表示されない
  - **何をテストするか**: `type='reconfirmed'` のカードで、通常 graded カードに表示される「次回:」テキストが存在しないこと
  - **期待される動作**: 再確認カードは「覚えた✔」のみで、次回日付は表示されない
- **入力値**: `{ cardId: 'card-1', front: 'テスト問題', grade: 2, type: 'reconfirmed', nextReviewDate: '2026-03-01' }`
  - **入力データの意味**: nextReviewDate が設定されていても、type='reconfirmed' では非表示
- **期待される結果**: `screen.queryByText(/次回/)` が null
  - **期待結果の理由**: ReviewResultItem.tsx の条件分岐で `result.type === 'graded' && result.nextReviewDate` のみ次回日付を表示する（53行目）
- **テストの目的**: 通常 graded と reconfirmed の表示が区別されることを確認
  - **確認ポイント**: type='reconfirmed' では次回日付が非表示であること
- 🔵 *ReviewResultItem.tsx 既存実装（53行目）の条件分岐を確認済み*

### TC-RRI-004: type='graded'（grade 3-5）で従来通りのバッジと次回復習日が表示される 🔵

- **テスト名**: 通常評価カードで従来通りの表示（リグレッション防止）
  - **何をテストするか**: `type='graded'` かつ `grade=4` のカードで、評価バッジと次回復習日が表示されること
  - **期待される動作**: lime 色の `4` バッジ + 「次回: 2026-03-01」が表示される
- **入力値**: `{ cardId: 'card-1', front: 'テスト問題', grade: 4, type: 'graded', nextReviewDate: '2026-03-01' }`
  - **入力データの意味**: quality 4 で採点された通常の復習カード
- **期待される結果**: テキスト `4` のバッジが存在し、`次回: 2026-03-01` テキストが表示される。「覚えた✔」は非表示
  - **期待結果の理由**: 要件定義書 REQ-103「通常カードの表示は変更なし」、受け入れ基準 TC-501-02
- **テストの目的**: 再確認機能追加による通常カード表示のリグレッションがないことを確認
  - **確認ポイント**: グレードバッジ、次回日付、「覚えた✔」の非存在
- 🔵 *ReviewResultItem.tsx 既存実装（31-37行目, 53-56行目）で確認済み*

### TC-RRI-005: type='graded'（grade 0-2）で従来通りの表示 🔵

- **テスト名**: 低評価カードで従来通りの表示（再確認対象でも graded のまま表示されるケース）
  - **何をテストするか**: `type='graded'` かつ `grade=1` のカードで、評価バッジと次回復習日が表示されること
  - **期待される動作**: orange 色の `1` バッジ + 次回復習日が表示される
- **入力値**: `{ cardId: 'card-1', front: 'テスト問題', grade: 1, type: 'graded', nextReviewDate: '2026-03-01' }`
  - **入力データの意味**: quality 1 で採点されたが、まだ再確認が完了していないカード
- **期待される結果**: テキスト `1` のバッジ + 「次回: 2026-03-01」が表示される
  - **期待結果の理由**: type='graded' のままであれば従来通りの表示
- **テストの目的**: grade 0-2 でも type='graded' なら従来通りの表示であることを確認
  - **確認ポイント**: type が表示分岐の主キーであること
- 🔵 *ReviewResultItem.tsx 31行目 `result.type === 'graded' && gradeConfig` 条件*

### TC-RRI-006: type='reconfirmed' で Undo ボタンが表示される 🔵

- **テスト名**: 再確認結果カードに Undo ボタンが表示される
  - **何をテストするか**: `type='reconfirmed'` かつ `onUndo` が渡されている場合に「取消」ボタンが表示されること
  - **期待される動作**: 「取消」テキストのボタンがレンダリングされる
- **入力値**: `{ result: { cardId: 'card-1', front: 'テスト問題', grade: 2, type: 'reconfirmed' }, index: 0, onUndo: vi.fn() }`
  - **入力データの意味**: 再確認カードに Undo 機能が有効なケース
- **期待される結果**: `screen.getByRole('button', { name: /取り消す/ })` または `screen.getByText('取消')` が DOM に存在する
  - **期待結果の理由**: ReviewResultItem.tsx 68行目 `(result.type === 'graded' || result.type === 'reconfirmed') && onUndo` の条件
- **テストの目的**: 要件定義書 REQ-404「Undo 機能は再確認カードにも使用可能」の検証
  - **確認ポイント**: type='reconfirmed' が Undo 対象に含まれていること
- 🔵 *ReviewResultItem.tsx 既存実装（68行目）で確認済み、要件定義書 REQ-404 に対応*

### TC-RRI-007: type='reconfirmed' で Undo ボタンクリックが動作する 🔵

- **テスト名**: 再確認カードの Undo ボタンクリックで onUndo(index) が呼ばれる
  - **何をテストするか**: Undo ボタンをクリックした際に `onUndo` ハンドラに正しい index が渡されること
  - **期待される動作**: userEvent.click 後に `onUndo(0)` が呼ばれる
- **入力値**: `{ result: { cardId: 'card-1', front: 'テスト問題', grade: 2, type: 'reconfirmed' }, index: 0, onUndo: vi.fn() }`
  - **入力データの意味**: 再確認カードの Undo 操作
- **期待される結果**: `expect(onUndo).toHaveBeenCalledWith(0)`
  - **期待結果の理由**: ReviewResultItem.tsx 71行目 `onClick={() => onUndo(index)}`
- **テストの目的**: Undo ボタンとハンドラの正しい接続を確認
  - **確認ポイント**: index パラメータが正しく伝播されること
- 🔵 *ReviewResultItem.tsx 既存実装（71行目）で確認済み*

### TC-RRI-008: type='skipped' で従来通りの表示 🔵

- **テスト名**: スキップカードで従来通りの表示（リグレッション防止）
  - **何をテストするか**: `type='skipped'` のカードで、グレーバッジ（—）+ 「スキップ」サブラベルが表示されること
  - **期待される動作**: 従来通りの skipped 表示
- **入力値**: `{ cardId: 'card-1', front: 'テスト問題', type: 'skipped' }`
  - **入力データの意味**: スキップされたカードの結果表示
- **期待される結果**: テキスト `—` のバッジ + 「スキップ」テキストが表示される。Undo ボタンは非表示
  - **期待結果の理由**: ReviewResultItem.tsx 38-41行目、58-60行目の既存条件
- **テストの目的**: skipped 表示のリグレッション防止
  - **確認ポイント**: type='skipped' の表示が変わっていないこと
- 🔵 *ReviewResultItem.tsx 既存実装で確認済み*

### TC-RRI-009: type='undone' で従来通りの表示 🔵

- **テスト名**: 取り消しカードで従来通りの表示（リグレッション防止）
  - **何をテストするか**: `type='undone'` のカードで、青バッジ（↩）+ 「取り消し済み」サブラベルが表示されること
  - **期待される動作**: 従来通りの undone 表示
- **入力値**: `{ cardId: 'card-1', front: 'テスト問題', type: 'undone' }`
  - **入力データの意味**: 取り消されたカードの結果表示
- **期待される結果**: テキスト `↩` のバッジ + 「取り消し済み」テキストが表示される。Undo ボタンは非表示
  - **期待結果の理由**: ReviewResultItem.tsx 43-46行目、61-63行目の既存条件
- **テストの目的**: undone 表示のリグレッション防止
  - **確認ポイント**: type='undone' の表示が変わっていないこと
- 🔵 *ReviewResultItem.tsx 既存実装で確認済み*

### TC-RRI-010: type='reconfirmed' でカード表面テキストが表示される 🔵

- **テスト名**: 再確認カードのカード表面テキストが表示される
  - **何をテストするか**: `type='reconfirmed'` のカードで、front テキストが表示されること
  - **期待される動作**: front テキストが truncate で表示される
- **入力値**: `{ cardId: 'card-1', front: '日本語の単語テスト', grade: 0, type: 'reconfirmed' }`
  - **入力データの意味**: カードの表面テキストが正しくレンダリングされるか
- **期待される結果**: `screen.getByText('日本語の単語テスト')` が DOM に存在する
  - **期待結果の理由**: reconfirm-ui-requirements.md「カード表面テキスト: result.front（truncate）」
- **テストの目的**: カードの識別情報が適切に表示されることを確認
  - **確認ポイント**: front テキストの完全一致
- 🔵 *ReviewResultItem.tsx 52行目 `<p>{result.front}</p>` で確認済み*

---

## 6. ReviewResultItem 再確認表示 - 境界値テストケース

### TC-RRI-011: type='reconfirmed' かつ grade=undefined でグレードバッジが非表示 🟡

- **テスト名**: 再確認カードでグレードが未定義の場合にバッジが非表示になる
  - **境界値の意味**: SessionCardResult の grade はオプショナル（`grade?: number`）であるため、undefined の場合の動作
  - **境界値での動作保証**: gradeConfig が null となり、バッジがレンダリングされない
- **入力値**: `{ cardId: 'card-1', front: 'テスト問題', type: 'reconfirmed' }`（grade 未設定）
  - **境界値選択の根拠**: card.ts で `grade?: number` と定義されており、undefined は合法な値
  - **実際の使用場面**: 型安全性のエッジケース（実運用では grade は必ず設定されるはず）
- **期待される結果**: バッジ領域にグレード数値が表示されない。「覚えた✔」サブラベルのみ表示される
  - **境界での正確性**: `gradeConfig = result.grade !== undefined ? GRADE_DISPLAY_CONFIGS[result.grade] : null` で null になる
  - **一貫した動作**: グレースフルデグラデーション（バッジなしでも破綻しない）
- **テストの目的**: 不完全なデータでもコンポーネントがクラッシュしないことを確認
  - **堅牢性の確認**: 防御的プログラミングの確認
- 🟡 *reconfirm-ui-requirements.md EDGE-003 の記載に基づくが、実装はこれから追加するため妥当な推測*

### TC-RRI-012: type='reconfirmed' かつ grade=0 で正しいバッジが表示される 🔵

- **テスト名**: 再確認カードで grade=0（最低評価）のバッジが正しく表示される
  - **境界値の意味**: grade の最小値（0）での表示確認
  - **境界値での動作保証**: GRADE_DISPLAY_CONFIGS[0] が正しく参照される
- **入力値**: `{ cardId: 'card-1', front: 'テスト問題', grade: 0, type: 'reconfirmed' }`
  - **境界値選択の根拠**: grade=0 は「全く覚えていない」を意味し、再確認対象の最低値
  - **実際の使用場面**: quality 0 で評価して再確認ループに入ったカード
- **期待される結果**: テキスト `0` のバッジが `bg-red-100 text-red-700` で表示される + 「覚えた✔」
  - **境界での正確性**: GRADE_DISPLAY_CONFIGS[0] = `{ label: '0', bgClass: 'bg-red-100', textClass: 'text-red-700' }`
  - **一貫した動作**: grade=1, grade=2 と同じ表示パターン
- **テストの目的**: grade 最小値での正しい表示を確認
  - **堅牢性の確認**: GRADE_DISPLAY_CONFIGS のインデックスアクセスが正しいこと
- 🔵 *ReviewResultItem.tsx GRADE_DISPLAY_CONFIGS 定義（11行目）で確認済み*

---

## 7. ReviewComplete 再確認カウント - 正常系テストケース

### TC-RC-001: type='reconfirmed' のカードが gradedCount に含まれる 🔵

- **テスト名**: 再確認カードが復習枚数カウントに含まれる
  - **何をテストするか**: results に type='reconfirmed' のカードが含まれている場合、gradedCount に計上されること
  - **期待される動作**: displayCount に reconfirmed カードの枚数が含まれる
- **入力値**: `results = [{ cardId: 'c1', front: 'Q1', grade: 4, type: 'graded' }, { cardId: 'c2', front: 'Q2', grade: 1, type: 'reconfirmed' }]`, `reviewedCount: 2`
  - **入力データの意味**: graded 1枚 + reconfirmed 1枚 = 合計2枚
- **期待される結果**: `screen.getByText(/2枚/)` が表示される
  - **期待結果の理由**: ReviewComplete.tsx 20行目 `results.filter((r) => r.type === 'graded' || r.type === 'reconfirmed').length` = 2
- **テストの目的**: reconfirmed が gradedCount に正しく含まれることを確認
  - **確認ポイント**: 表示される枚数が graded + reconfirmed の合計
- 🔵 *ReviewComplete.tsx 既存実装（20行目）で確認済み*

### TC-RC-002: graded + reconfirmed + skipped 混在時の正しい枚数表示 🔵

- **テスト名**: 各 type 混在時の復習枚数が正しく計算される
  - **何をテストするか**: 複数の type が混在した results での gradedCount 計算
  - **期待される動作**: graded と reconfirmed のみがカウントされ、skipped と undone は除外される
- **入力値**: `results = [{ type: 'graded', grade: 4 }, { type: 'reconfirmed', grade: 1 }, { type: 'skipped' }, { type: 'undone' }]`, `reviewedCount: 4`
  - **入力データの意味**: 全4種類の type が混在するシナリオ
- **期待される結果**: `screen.getByText(/2枚/)` が表示される（graded:1 + reconfirmed:1 = 2）
  - **期待結果の理由**: gradedCount のフィルタ条件で skipped, undone は除外される
- **テストの目的**: 異なる type の混在時に正しい計算が行われることを確認
  - **確認ポイント**: skipped と undone が枚数に含まれないこと
- 🔵 *ReviewComplete.tsx 20行目のフィルタ条件で確認済み*

### TC-RC-003: reconfirmed のみの results で正しい枚数表示 🟡

- **テスト名**: 全カードが再確認結果の場合の枚数表示
  - **何をテストするか**: results が全て type='reconfirmed' の場合の gradedCount 計算
  - **期待される動作**: reconfirmed の枚数が正しく表示される
- **入力値**: `results = [{ type: 'reconfirmed', grade: 0 }, { type: 'reconfirmed', grade: 2 }]`, `reviewedCount: 2`
  - **入力データの意味**: 全カードが quality 0-2 で再確認ループに入り、全て「覚えた」で完了したケース
- **期待される結果**: `screen.getByText(/2枚/)` が表示される
  - **期待結果の理由**: gradedCount = 2（reconfirmed 2枚）
- **テストの目的**: reconfirmed のみの極端なケースでも正しく動作することを確認
  - **確認ポイント**: reconfirmed が確実にカウント対象であること
- 🟡 *ReviewComplete.tsx のフィルタ条件から妥当な推測（全カード再確認は実運用でも起こりうる）*

### TC-RC-004: results に reconfirmed カードが含まれる場合の結果リスト表示 🔵

- **テスト名**: 再確認カードが結果リストに ReviewResultItem として表示される
  - **何をテストするか**: results に type='reconfirmed' のカードがある場合、ReviewResultItem としてリスト内にレンダリングされること
  - **期待される動作**: results.map で全カードが ReviewResultItem にマップされる
- **入力値**: `results = [{ cardId: 'c1', front: '問題1', grade: 4, type: 'graded', nextReviewDate: '2026-03-01' }, { cardId: 'c2', front: '問題2', grade: 1, type: 'reconfirmed' }]`, `reviewedCount: 2`
  - **入力データの意味**: graded + reconfirmed の混在リスト
- **期待される結果**: `screen.getByText('問題1')` と `screen.getByText('問題2')` が両方 DOM に存在する
  - **期待結果の理由**: ReviewComplete.tsx 36-44行目の results.map で全カードがレンダリングされる
- **テストの目的**: results 配列の全要素が結果リストに表示されることを確認
  - **確認ポイント**: reconfirmed カードがリストからフィルタされず表示されること
- 🔵 *ReviewComplete.tsx 36-44行目の results.map で確認済み*

### TC-RC-005: results が空で reviewedCount のみ表示される（既存動作維持） 🔵

- **テスト名**: results が空の場合に reviewedCount が表示される
  - **何をテストするか**: `results=[]` の場合に `displayCount = reviewedCount` のフォールバック動作
  - **期待される動作**: reviewedCount の値が枚数として表示される
- **入力値**: `results=[]`, `reviewedCount: 3`
  - **入力データの意味**: results が未提供（旧コードとの互換性）
- **期待される結果**: `screen.getByText(/3枚/)` が表示される
  - **期待結果の理由**: ReviewComplete.tsx 21行目 `gradedCount > 0 ? gradedCount : reviewedCount` で gradedCount=0 → reviewedCount=3
- **テストの目的**: 既存の reviewedCount フォールバック動作が維持されていることを確認
  - **確認ポイント**: 後方互換性
- 🔵 *ReviewComplete.tsx 21行目の条件分岐で確認済み。既存テスト（ReviewComplete.test.tsx）との互換*

---

## 8. ReviewComplete 再確認カウント - 境界値テストケース

### TC-RC-006: gradedCount=0、reviewedCount=0 で 0枚表示 🔵

- **テスト名**: 全スキップで0枚表示
  - **境界値の意味**: カウントの最小値（0枚）
  - **境界値での動作保証**: gradedCount=0 かつ reviewedCount=0 でも正しく「0枚」と表示される
- **入力値**: `results=[{ type: 'skipped', cardId: 'c1', front: 'Q1' }]`, `reviewedCount: 0`
  - **境界値選択の根拠**: 全カードをスキップした場合、gradedCount=0
  - **実際の使用場面**: ユーザーが全カードをスキップして完了した場合
- **期待される結果**: `screen.getByText(/0枚/)` が表示される
  - **境界での正確性**: gradedCount=0 → displayCount = reviewedCount = 0
  - **一貫した動作**: 既存テスト（ReviewComplete.test.tsx 28-31行目）と同じ
- **テストの目的**: ゼロ枚表示の動作確認
  - **堅牢性の確認**: 既存テストとの互換性
- 🔵 *既存テスト（ReviewComplete.test.tsx 28-31行目）で確認済み*

---

## 9. テストケース実装時の日本語コメント指針

### セットアップコメント

```typescript
beforeEach(() => {
  // 【テスト前準備】: 各テスト実行前に vi.fn() のモック状態をリセット
  // 【環境初期化】: 前のテストのモック呼び出し回数をクリアし、独立したテスト環境を保証
  vi.clearAllMocks();
});
```

### GradeButtons テストコメント例

```typescript
describe('GradeButtons - 再確認モード', () => {
  // 【テスト目的】: 再確認モード（isReconfirmMode=true）で正しいUIが表示されることを確認
  // 【テスト内容】: 2択ボタン表示、6段階ボタン非表示、スキップボタン非表示
  // 【期待される動作】: 早期リターンパターンにより再確認専用UIがレンダリングされる
  // 🔵 受け入れ基準 TC-002-01, TC-102-01 に対応

  // 【テストデータ準備】: 再確認モード用の共通 Props
  const reconfirmProps = {
    onGrade: vi.fn(),
    disabled: false,
    isReconfirmMode: true as const,
    onReconfirmRemembered: vi.fn(),
    onReconfirmForgotten: vi.fn(),
  };

  it('isReconfirmMode=true で「覚えた」「覚えていない」ボタンが表示される', () => {
    // 【実際の処理実行】: 再確認モード Props で GradeButtons をレンダリング
    render(<GradeButtons {...reconfirmProps} />);

    // 【結果検証】: 2択ボタンの存在確認
    // 【検証項目】: 「覚えた」ボタンがDOMに存在すること 🔵
    expect(screen.getByRole('button', { name: '覚えた' })).toBeInTheDocument();
    // 【検証項目】: 「覚えていない」ボタンがDOMに存在すること 🔵
    expect(screen.getByRole('button', { name: '覚えていない' })).toBeInTheDocument();
  });
});
```

### ReviewResultItem テストコメント例

```typescript
describe('ReviewResultItem - 再確認結果表示', () => {
  // 【テスト目的】: type='reconfirmed' のカードが正しい表示で結果リストに表示されることを確認
  // 【テスト内容】: 元の評価バッジ、「覚えた✔」サブラベル、Undoボタンの表示
  // 【期待される動作】: 通常 graded とは異なるサブラベルで再確認結果が区別できる
  // 🔵 受け入れ基準 TC-501-01, TC-501-02 に対応

  // 【テストデータ準備】: 再確認済みカードの SessionCardResult
  const reconfirmedResult: SessionCardResult = {
    cardId: 'card-1',
    front: 'テスト問題',
    grade: 2,
    type: 'reconfirmed',
    reconfirmResult: 'remembered',
  };

  it('type="reconfirmed" で元の評価バッジが表示される', () => {
    // 【実際の処理実行】: 再確認結果のカードをレンダリング
    render(<ReviewResultItem result={reconfirmedResult} index={0} />);

    // 【結果検証】: 元の評価値「2」のバッジが表示されること
    // 【検証項目】: grade=2 のラベルテキストがDOM内に存在すること 🔵
    expect(screen.getByText('2')).toBeInTheDocument();
    // 【確認内容】: バッジの色が amber であること（GRADE_DISPLAY_CONFIGS[2]）
  });
});
```

### ReconfirmBadge テストコメント例

```typescript
describe('ReconfirmBadge', () => {
  // 【テスト目的】: ReconfirmBadge が「再確認」テキストのバッジを正しく表示することを確認
  // 【テスト内容】: テキスト内容、背景色、テキスト色、形状のスタイリング検証
  // 【期待される動作】: パラメータ不要のプレゼンテーションコンポーネントとして正しくレンダリング
  // 🔵 要件定義書 REQ-101 に対応

  it('「再確認」テキストが表示される', () => {
    // 【実際の処理実行】: ReconfirmBadge をレンダリング
    render(<ReconfirmBadge />);

    // 【結果検証】: テキスト「再確認」がDOMに存在すること
    // 【検証項目】: バッジのテキスト内容が正確に「再確認」であること 🔵
    expect(screen.getByText('再確認')).toBeInTheDocument();
  });
});
```

---

## 10. 要件定義との対応関係

### 参照した機能概要

| 要件 | テストケース | セクション |
|------|-------------|-----------|
| REQ-002: 再確認カード表示時に2択を表示 | TC-GB-001, TC-GB-002, TC-GB-003 | requirements.md REQ-002 |
| REQ-101: 再確認バッジ表示 | TC-RB-001 ~ TC-RB-005 | requirements.md REQ-101 |
| REQ-102: スキップボタン非表示 | TC-GB-003 | requirements.md REQ-102 |
| REQ-103: 通常モード非破壊 | TC-GB-004, TC-GB-010, TC-RRI-004, TC-RRI-005, TC-RRI-008, TC-RRI-009, TC-RC-005 | requirements.md REQ-103 |
| REQ-404: Undo 再確認カード対応 | TC-RRI-006, TC-RRI-007 | requirements.md REQ-404 |
| REQ-501: 復習完了画面 元評価+再確認結果 | TC-RRI-001, TC-RRI-002, TC-RRI-003, TC-RC-001, TC-RC-004 | requirements.md REQ-501 |

### 参照した入力・出力仕様

- reconfirm-ui-requirements.md セクション2.1: GradeButtonsProps インターフェース
- reconfirm-ui-requirements.md セクション2.2: ReconfirmBadge 仕様
- reconfirm-ui-requirements.md セクション2.4: ReviewResultItem 拡張仕様
- reconfirm-ui-requirements.md セクション2.5: ReviewComplete 拡張仕様

### 参照した制約条件

- NFR-201: 44px タップ領域 → TC-GB-011
- REQ-103: 通常モード非破壊 → TC-GB-004, TC-GB-010, TC-RRI-004, TC-RRI-005, TC-RRI-008, TC-RRI-009

### 参照した受け入れ基準

| 受け入れ基準 | テストケース | 対応状況 |
|-------------|-------------|---------|
| TC-002-01 | TC-GB-001, TC-GB-002, TC-GB-003 | 完全対応 |
| TC-101-01 | TC-RB-001, TC-RB-002, TC-RB-003, TC-RB-004 | 完全対応 |
| TC-101-02 | TC-RB-005（ReviewPage テスト側で条件表示を確認） | 対応 |
| TC-102-01 | TC-GB-003 | 完全対応 |
| TC-501-01 | TC-RRI-001, TC-RRI-002, TC-RC-001 | 完全対応 |
| TC-501-02 | TC-RRI-004, TC-RRI-005, TC-RC-005 | 完全対応 |

---

## 11. テストケースサマリー

### コンポーネント別テストケース数

| コンポーネント | テストファイル | 正常系 | 異常系 | 境界値 | 合計 |
|-------------|--------------|--------|--------|--------|------|
| GradeButtons（再確認モード） | GradeButtons.test.tsx | 6 | 3 | 2 | 11 |
| ReconfirmBadge | ReconfirmBadge.test.tsx | 5 | 0 | 0 | 5 |
| ReviewResultItem | ReviewResultItem.test.tsx | 7 | 0 | 2 | 9 (*) |
| ReviewComplete | ReviewComplete.test.tsx | 5 | 0 | 1 | 6 |
| **合計** | | **23** | **3** | **5** | **31** |

(*) ReviewResultItem のうち TC-RRI-008, TC-RRI-009 はリグレッション防止テスト。TC-RRI-010 はカードテキスト表示テスト。

### 信頼性レベル分布

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 28 | 90% |
| 🟡 黄信号 | 3 | 10% |
| 🔴 赤信号 | 0 | 0% |

### 🟡 黄信号のテストケース一覧

| テストケースID | 内容 | 黄信号の理由 |
|-------------|------|------------|
| TC-GB-011 | 44px タップ領域確認 | CSSクラスの存在チェックでの検証（実ピクセルサイズの実測はユニットテスト外） |
| TC-RRI-011 | grade=undefined でバッジ非表示 | 型定義上の可能性で実運用では発生しにくい |
| TC-RC-003 | 全カード reconfirmed | 実運用で起こりうるが要件定義書に明示的記載なし |

---

## 12. テスト実行コマンド

```bash
# 全テスト実行
cd frontend && npx vitest run

# 対象ファイルのみ実行
cd frontend && npx vitest run GradeButtons.test.tsx
cd frontend && npx vitest run ReconfirmBadge.test.tsx
cd frontend && npx vitest run ReviewResultItem.test.tsx
cd frontend && npx vitest run ReviewComplete.test.tsx

# カバレッジ確認
cd frontend && npx vitest run --coverage
```

---

**作成者**: Claude Code
**最終更新**: 2026-02-28
