# Frontend コードレビュー 統合レポート

- **日付**: 2026-03-08
- **対象**: `frontend/src/` 全体（Components、Pages、Hooks、Contexts、Services、Utils、Types）
- **レビュー方式**: Agent Teams による3並列レビュー

## 全体評価

全体的に**高品質なコードベース**。型安全性への配慮、`useCallback`/`useMemo` によるメモ化、アクセシビリティ属性（`aria-label`, `aria-hidden`, `data-testid`）の整備、ドメイン別の Context 分割など、丁寧に実装されている。以下、優先度別に指摘事項を統合する。

---

## 強み

- **ドメイン別 Context 設計**: Auth / Cards / Decks / Tutor の責務分離が明確
- **OIDC + PKCE 認証**: `oidc-client-ts` による堅牢な認証フロー、設定バリデーション付き
- **メモ化の一貫した適用**: `useCallback` / `useMemo` によるレンダリング最適化
- **テストカバレッジ**: コンポーネント・フック・サービス・ページの各層にテストファイルが存在
- **アクセシビリティの基本対応**: `aria-label`, `data-testid`, `role` 属性の広範な適用
- **型安全なAPI通信**: ジェネリック `request<T>` メソッドによる型付きレスポンス

---

## サマリー

| 重要度 | Components | Pages & App | Hooks/Contexts/Services | 合計 |
|--------|-----------|-------------|------------------------|------|
| 🔴 Critical | 4 | 0 | 3 | **7** |
| 🟡 Warning | 19 | 9 | 10 | **38** |
| 🔵 Info | 12 | 7 | 7 | **26** |
| **合計** | **35** | **16** | **20** | **71** |

---

## Critical（本番運用に影響するリスク）

### C-1: トークンリフレッシュの競合状態

- **ファイル**: `services/api.ts:73-88`
- **問題**: `refreshPromise` の解放が全リクエストの `finally` で行われるため、並行リクエスト時にロック機構が破綻する。待機側も `finally` で `isRefreshing = false` を実行してしまう。
- **修正案**: リフレッシュを開始した側だけが `finally` でリセットする設計に変更。
```ts
if (!this.isRefreshing) {
  this.isRefreshing = true;
  this.refreshPromise = this.refreshToken().finally(() => {
    this.isRefreshing = false;
    this.refreshPromise = null;
  });
}
try {
  await this.refreshPromise;
  return this.request<T>(endpoint, options, true);
} catch {
  authService.login().catch(() => {});
  throw new Error("Session expired");
}
```

### C-2: `authService.login()` の fire-and-forget

- **ファイル**: `services/api.ts:69,83`
- **問題**: `login()` が `await` も `.catch()` もなく呼ばれ、リダイレクトエラーが無視される。直後の `throw` がリダイレクト処理と競合する。
- **修正案**: `.catch()` を追加してエラーをログに出力する。

### C-3: `fetchCards` / `fetchDueCards` の競合状態

- **ファイル**: `contexts/CardsContext.tsx:55-89`
- **問題**: 同一の `isLoading` を共有し並行呼び出し時に状態が競合。`AbortController` が未使用のためアンマウント後の setState リスクがある。
- **修正案**: `useEffect` に `AbortController` のクリーンアップを追加。`isLoading` を関数ごとに分離。

### C-4: `ReviewProgress.tsx` のゼロ除算

- **ファイル**: `components/ReviewProgress.tsx:7`
- **問題**: `total=0` で `current / total` が `NaN` となりプログレスバーの `width` が `NaN%` になる。`aria-valuemin={1}` も WAI-ARIA 仕様上 `0` が正しい。
- **修正案**: `total > 0 ? Math.round((current / total) * 100) : 0` に変更。`aria-valuemin={0}` に修正。

### C-5: `StatsSummary.tsx` の `.toFixed()` クラッシュ

- **ファイル**: `components/stats/StatsSummary.tsx:64`
- **問題**: `average_grade` が `undefined` の場合に実行時エラー。
- **修正案**: `(stats.average_grade ?? 0).toFixed(1)` に変更。

### C-6: `WeakCardItem.tsx` の `.toFixed()` クラッシュ

- **ファイル**: `components/stats/WeakCardItem.tsx:34`
- **問題**: `ease_factor` が `undefined` / `NaN` の場合に実行時エラー。
- **修正案**: `typeof card.ease_factor === 'number' ? card.ease_factor.toFixed(1) : 'N/A'` に変更。

### C-7: `ReviewForecast.tsx` のスプレッド展開リスク

- **ファイル**: `components/stats/ReviewForecast.tsx:15`
- **問題**: `Math.max(...forecast.map(...))` は大きな配列でスタックオーバーフローのリスクがある。
- **修正案**: `forecast.reduce((max, d) => Math.max(max, d.due_count), 1)` に変更。

---

## Warning（早期対応を推奨）

### セキュリティ

#### W-1: URL パラメータの `encodeURIComponent` 不統一

- **ファイル**: `services/api.ts:132-154, 203-214, 254-265`
- **問題**: tutor 系は `encodeURIComponent` を使用しているが、cards / decks / reviews の ID はエンコードなしで URL に埋め込まれている。
- **修正案**: すべてのリソース ID に `encodeURIComponent` を適用して統一する。

#### W-2: URL 検証が正規表現のみ

- **ファイル**: `components/ReferenceDisplay.tsx:45-54`
- **問題**: ユーザー入力 URL の検証が `/^https?:\/\//i` のみ。`URL` コンストラクタによるパースを経ていない。
- **修正案**: `new URL(url)` でパースし `protocol` を明示的にチェックする関数を導入。

#### W-3: `access_token` が React state に平文保持

- **ファイル**: `hooks/useAuth.ts:14-22`
- **問題**: React DevTools からコンポーネントの state でアクセストークンが可視。
- **修正案**: サービス層にカプセル化し、`getAccessToken()` 関数経由でのみ取得する設計に変更。

#### W-4: `VITE_LIFF_ID` のバリデーション欠如

- **ファイル**: `services/liff.ts:11`
- **問題**: 未設定時に空文字列にフォールバックし、LIFF SDK の初期化が不定な挙動になる。OIDC 設定には `validateOidcConfig()` があるが LIFF ID には同等のチェックがない。
- **修正案**: LIFF 使用時は起動時バリデーションを追加。

### 状態管理

#### W-5: タイマーのアンマウント時クリーンアップ欠如

- **ファイル**: `contexts/TutorContext.tsx:59-66`
- **問題**: `timeoutTimerRef` の `setTimeout` に対するアンマウント時クリーンアップの `useEffect` が存在しない。タイマー発火時に未マウントコンポーネントへの setState が発生する。
- **修正案**: `useEffect` の return で `clearTimeoutTimer()` を呼ぶ。

#### W-6: 楽観的メッセージ削除の競合リスク

- **ファイル**: `contexts/TutorContext.tsx:144-147`
- **問題**: エラー時に `prev.slice(0, -1)` で最後のメッセージを削除するが、送信中に別のメッセージが追加されると誤削除する。
- **修正案**: 追加時に `crypto.randomUUID()` で一意 ID を付与し、ID で削除する。

#### W-7: メッセージ上限のハードコード

- **ファイル**: `contexts/TutorContext.tsx:204`
- **問題**: `message_count >= 20` のマジックナンバー。`sendMessage` レスポンスではサーバーの `is_limit_reached` を使うが、`resumeSession` 時だけクライアント判定。
- **修正案**: 定数化、またはサーバーレスポンスに上限フラグを含める。

#### W-8: ミューテーション後の全件再取得

- **ファイル**: `contexts/DecksContext.tsx:56-70`
- **問題**: `createDeck` / `updateDeck` はレスポンスで更新後の `Deck` を受け取っているのに活用せず `fetchDecks()` で全件再取得。
- **修正案**: レスポンスを `setDecks` で直接反映する楽観的更新に変更。

#### W-9: `DecksContext` のミューテーション中 `isLoading` 未設定

- **ファイル**: `contexts/DecksContext.tsx:56-70`
- **問題**: `createDeck` / `updateDeck` / `deleteDeck` 中に `setIsLoading` が呼ばれず、二重送信防止ができない。
- **修正案**: ミューテーション中も `isLoading` を制御する。

#### W-10: `AuthContext` の冗長な `useMemo`

- **ファイル**: `contexts/AuthContext.tsx:43-51`
- **問題**: `useAuth` 内で既にメモ化されているのに、`AuthContext` でもう一度 `useMemo` でラップしている。
- **修正案**: `AuthContext` 側の `useMemo` を削除し、`useAuth` のメモ化に一任。

### パフォーマンス

#### W-11: N+1 API リクエスト

- **ファイル**: `components/tutor/RelatedCardChip.tsx:13-31`
- **問題**: マウント時に個別カード ID ごとに API リクエストを発行。セッション履歴が長い場合に膨大なリクエストが発生する。
- **修正案**: バックエンドからセッションデータにカード情報を含めるか、一括取得 API を使用。

#### W-12: カード保存の直列実行

- **ファイル**: `pages/GeneratePage.tsx:220-233`
- **問題**: `for...of` ループで1枚ずつ `createCard` を呼び、10枚で遅延が10倍。
- **修正案**: `Promise.all` で並列実行、またはバッチ作成エンドポイントの利用。

#### W-13: タイマーリーク

- **ファイル**: `pages/GeneratePage.tsx:138-140`
- **問題**: `timer2` が `progressTimerRef.current` に保存されず、アンマウント時にクリアされない。
- **修正案**: 両タイマーを配列として ref に保持し、クリーンアップで全件 clear する。

### バグ

#### W-14: URL バリデーションの矛盾

- **ファイル**: `components/UrlInput.tsx:12,25`
- **問題**: バリデーションは `https://` のみ許可だが、`handlePaste` では `http://` も受け入れる。
- **修正案**: バリデーション条件を統一する。

#### W-15: `location.state` 未消費で成功メッセージ再表示

- **ファイル**: `pages/CardsPage.tsx:36-38`
- **問題**: ブラウザの戻る操作で `location.state` が復元され、成功メッセージが再表示される。
- **修正案**: 消費後に `window.history.replaceState(null, '')` で state をクリア。

#### W-16: ログアウト後のナビゲーション競合

- **ファイル**: `pages/SettingsPage.tsx:107-118`
- **問題**: `logout()` 後の `navigate('/')` が OIDC エンドセッションリダイレクトと競合する可能性。
- **修正案**: `authService.logout()` の実装を確認し、リダイレクト制御を統一。

#### W-17: `reconfirmQueue` の状態参照パターン不統一

- **ファイル**: `pages/ReviewPage.tsx:232`
- **問題**: `handleGrade` でクロージャ直接参照、`handleReconfirmForgotten` では updater 関数パターン。不統一により古い state を参照するリスク。
- **修正案**: `setReconfirmQueue` の updater 関数パターンに統一。

#### W-18: `resumeSession` の未処理 Promise 拒否

- **ファイル**: `pages/TutorPage.tsx:40-48`
- **問題**: `.then()` のみで `.catch()` がなく、例外時に未処理の Promise 拒否が発生。
- **修正案**: `.catch()` を追加、または `async/await` + `try/catch` に統一。

### アクセシビリティ

#### W-19: `role="radiogroup"` と `aria-pressed` の矛盾

- **ファイル**: `components/FilterChips.tsx:29`
- **問題**: コンテナが `role="radiogroup"` だが子要素は `<button>` + `aria-pressed`。`radiogroup` の子は `role="radio"` でなければならない。
- **修正案**: `role="group"` に変更。

#### W-20: モーダルの `role="dialog"` / `aria-modal` 欠如

- **ファイル**: `components/DeckFormModal.tsx:140-146`
- **問題**: モーダルコンテナに `role="dialog"`, `aria-modal="true"`, `aria-labelledby` が設定されていない。
- **修正案**: 適切な ARIA 属性を追加し、`h2` に `id` を付与して `aria-labelledby` で参照。

#### W-21: `<li>` のキーボードアクセス不可

- **ファイル**: `components/DeckSummary.tsx:64-65`
- **問題**: `<li>` に `onClick` があるが `tabIndex={0}` と `onKeyDown` がない。
- **修正案**: `<Link>` または `<button>` に置き換えるか、`tabIndex` + `onKeyDown` を追加。

#### W-22: 全モーダルダイアログのフォーカストラップ欠如

- **ファイル**: `pages/DecksPage.tsx:287`, `pages/CardDetailPage.tsx:383`, `pages/TutorPage.tsx:372`
- **問題**: 削除確認・セッション終了確認ダイアログでフォーカストラップが未実装。Tab キーでダイアログ外にフォーカス移動可能。
- **修正案**: `focus-trap-react` の導入、または `useEffect` + `onKeyDown` による制御。

#### W-23: SVG の `aria-hidden` 欠如 / エラーの `role="alert"` 欠如

- **ファイル**: `components/common/Error.tsx:10-12,8`
- **問題**: エラーアイコン SVG に `aria-hidden="true"` がなく、コンテナに `role="alert"` がない。
- **修正案**: `<svg aria-hidden="true">` と `<div role="alert">` を追加。

#### W-24: チャット入力の `aria-label` 欠如

- **ファイル**: `components/tutor/ChatInput.tsx:26-33`
- **問題**: `<input>` に `aria-label` がなく、`placeholder` はアクセシブルネームの代替にならない。
- **修正案**: `aria-label="チャットメッセージを入力"` を追加。

#### W-25: セッション展開ボタンの `aria-expanded` 欠如

- **ファイル**: `components/tutor/SessionList.tsx:104-107`
- **問題**: 展開ボタンに `aria-label` と `aria-expanded` がない。
- **修正案**: `aria-expanded={expandedId === s.session_id}` と `aria-label` を追加。

#### W-26: `<label>` と `<textarea>` の関連付け欠如

- **ファイル**: `components/CardPreview.tsx:50-58`
- **問題**: 編集モードの `<textarea>` に `id` がなく、`<label>` の `htmlFor` との関連付けがない。
- **修正案**: `id` を付与して `htmlFor` で紐付ける。

### コード品質

#### W-27: `getTypeIcon` 関数の重複

- **ファイル**: `components/ReferenceEditor.tsx:86-95`, `components/ReferenceDisplay.tsx:14-23`
- **問題**: 全く同一の実装が2ファイルに存在。
- **修正案**: `utils/reference.ts` に共通化してインポート。

#### W-28: 日付フォーマット関数の重複

- **ファイル**: `components/stats/ForecastBar.tsx:17-20`, `components/tutor/SessionList.tsx:10-17`
- **問題**: 別実装の日付フォーマット関数が存在。`utils/date.ts` が既にあるのに未使用。
- **修正案**: `utils/date.ts` に統合。

#### W-29: インデックスを `key` に使用（3箇所）

- **ファイル**: `components/tutor/SessionList.tsx:134`, `components/ReferenceEditor.tsx:105`, `pages/TutorPage.tsx:282`
- **問題**: 追加・削除時に React の reconciliation が誤動作するリスク。
- **修正案**: メッセージ型に `id` フィールドを追加、または `crypto.randomUUID()` を付与。

#### W-30: `err as Error` パターン（8箇所）

- **ファイル**: `useAuth.ts:84,112,136,171`, `CardsContext.tsx:63,85`, `DecksContext.tsx:50`, `useStats.ts:40`
- **問題**: `catch (err) { setError(err as Error) }` は型アサーションで実行時の保証がない。
- **修正案**: `toError` ユーティリティ関数を `utils/` に追加して統一。

#### W-31: `SessionList.tsx` のエラー無視

- **ファイル**: `components/tutor/SessionList.tsx:62-66`
- **問題**: `.catch(() => { // ignore })` でセッション取得エラーが完全に無視される。
- **修正案**: エラー状態を保持してユーザーにメッセージを表示。

#### W-32: エラー表示パターンの不統一

- **ファイル**: `pages/ReviewPage.tsx:412,494-501,547-551,682-684`
- **問題**: 3つの画面状態でエラー表示の UI パターンが異なる。
- **修正案**: 共通のエラーバナーコンポーネントに統一。

### API通信

#### W-33: `fetch` にタイムアウト未設定

- **ファイル**: `services/api.ts:60`
- **問題**: ネットワーク無応答時に Promise が永遠に pending になり `isLoading` が固定される。
- **修正案**: `AbortSignal.timeout(30_000)` を追加。

#### W-34: `CallbackPage` の `useEffect` 依存配列

- **ファイル**: `pages/CallbackPage.tsx:10-22`
- **問題**: `authService` がクロージャ参照されているが依存配列に含まれていない。外部シングルトンなので動作に影響はないが明示的でない。
- **修正案**: シングルトンであることをコメントで明記。

---

## Info（改善推奨・低優先度）

### I-1: `main.tsx` の非 null アサーション

- **ファイル**: `main.tsx:11`
- **問題**: `document.getElementById('root')!` のエラーメッセージが不親切。
- **修正案**: null チェック + 明示的なエラーメッセージ。

### I-2: 404 ルートの欠如

- **ファイル**: `App.tsx:25-119`
- **問題**: 未定義パスへのアクセスでブランクページが表示される。
- **修正案**: `<Route path="*" element={<Navigate to="/" replace />} />` を追加。

### I-3: `AuthUser` 型の重複定義

- **ファイル**: `hooks/useAuth.ts:14-22`, `contexts/AuthContext.tsx:5-13`
- **問題**: 同一内容のインターフェースが2箇所にローカル定義。
- **修正案**: `types/` に一元化してインポート。

### I-4: エラー型の不統一

- **ファイル**: `contexts/TutorContext.tsx:17` vs 他の Context
- **問題**: TutorContext の `error` が `string | null` で、他は `Error | null`。
- **修正案**: `Error | null` に統一し、表示時に `.message` を取り出す設計に。

### I-5: `dueCardToCard` のデフォルト値リスク

- **ファイル**: `contexts/CardsContext.tsx:26-39`
- **問題**: 変換結果が `updateCard` 等で誤用された場合に不正データが送信される。
- **修正案**: 変換結果をマークするか専用の型を定義。

### I-6: `Promise.all` による部分データ破棄

- **ファイル**: `hooks/useStats.ts:31-35`
- **問題**: 3つの API のうち1つが失敗すると他の成功データも破棄される。
- **修正案**: `Promise.allSettled` で個別の失敗を扱う。

### I-7: 循環依存

- **ファイル**: `services/api.ts:360`, `services/tutor-api.ts:14`
- **問題**: `api.ts` が `export * from "./tutor-api"` し、`tutor-api.ts` が `apiClient` をインポートする循環依存。
- **修正案**: `tutor-api.ts` を `api.ts` に統合、または `export *` を削除。

### I-8: エラー種別の未分類

- **ファイル**: `services/api.ts:91-98`
- **問題**: HTTP エラーとネットワークエラーが同一の `Error` で上位に伝播し、呼び出し元で種別判定ができない。
- **修正案**: `ApiError` / `NetworkError` のような独自エラークラスを導入。

### I-9: HTTPステータスの文字列マッチング

- **ファイル**: `components/CardForm.tsx:83-95`
- **問題**: `message.includes('504')` でステータスコードを判定。脆弱な文字列マッチング。
- **修正案**: カスタムエラークラスの `status` プロパティで判定。

### I-10: `<button>` の `type` 属性欠如

- **ファイル**: `components/BrowserProfileSettings.tsx:82,111,119`, `components/GenerateOptions.tsx:48-59,93-107`
- **問題**: フォーム内で `type` 未指定だとデフォルト `submit` として動作するリスク。
- **修正案**: すべてに `type="button"` を明示。

### I-11: 不要な変数

- **ファイル**: `pages/CardsPage.tsx:116`
- **問題**: `const displayCards = filteredCards;` は単純な別名で冗長。
- **修正案**: `displayCards` を削除して `filteredCards` を直接使用。

### I-12: `SearchBar.tsx` の冗長な `role`

- **ファイル**: `components/SearchBar.tsx:47-48`
- **問題**: `<input type="search">` は暗黙的に `searchbox` ロールを持つため `role="searchbox"` は冗長。
- **修正案**: `role="searchbox"` を削除。

### I-13: `ProtectedRoute` のエラー情報未活用

- **ファイル**: `components/common/ProtectedRoute.tsx:11`
- **問題**: `error` オブジェクトの内容を使わずハードコード文字列のみ表示。
- **修正案**: `error.message` を適切にサニタイズして表示。

### I-14: LIFF プロファイルの戻り値型欠如

- **ファイル**: `services/liff.ts:40-44`
- **問題**: `getLiffProfile` の戻り値型が推論任せ。
- **修正案**: `Promise<Profile>` を明示的に宣言。

### I-15: Context プロバイダーの過度なネスト

- **ファイル**: `App.tsx:23-121`
- **問題**: 4階層のネストで Provider 追加時に深くなる。
- **修正案**: `AppProviders` コンポーネントに集約。

### I-16: GenerateProgress のプログレスバー ARIA 欠如

- **ファイル**: `components/GenerateProgress.tsx:52-57`
- **問題**: `role="progressbar"`, `aria-valuenow` 等が未設定。
- **修正案**: 適切な ARIA 属性を追加。

### I-17: `CardDetailPage` のオーバーフェッチ

- **ファイル**: `pages/CardDetailPage.tsx:47-49`
- **問題**: マウントのたびに `fetchDecks()` を呼んでいるが `DecksContext` にキャッシュがある。
- **修正案**: 未取得の場合のみフェッチする条件を追加。

### I-18: `LinkLinePage` の早期 return と finally の冗長性

- **ファイル**: `pages/LinkLinePage.tsx:58-93`
- **問題**: 早期 return パスで `setIsLinking(false)` を手動呼び出ししており、`finally` と冗長。
- **修正案**: 早期 return を `throw` に変更し `catch` + `finally` で一元管理。

### I-19: `TutorPage` の不要な `pendingModeSwitch` state

- **ファイル**: `pages/TutorPage.tsx:56-61`
- **問題**: `pendingModeSwitch` + `useEffect` による間接的なビュー遷移が複雑。
- **修正案**: `startSession` 完了後に直接 `setView("chat")` を呼ぶ。

---

## 推奨対応の優先順位

### Phase 1: バグ・安全性（Critical + セキュリティ）

1. C-1: トークンリフレッシュの競合状態修正
2. C-2: `authService.login()` の fire-and-forget 修正
3. C-3: `CardsContext` の `AbortController` 追加
4. C-4〜C-7: `.toFixed()` / ゼロ除算 / スプレッド展開の防御的修正
5. W-1: `encodeURIComponent` の統一
6. W-33: `fetch` タイムアウトの追加

### Phase 2: 状態管理・パフォーマンス

7. W-5: タイマーのクリーンアップ
8. W-6: 楽観的メッセージ削除の ID ベース化
9. W-13: `GeneratePage` タイマーリーク修正
10. W-12: カード保存の並列化
11. W-8: ミューテーション後の楽観的更新

### Phase 3: コード品質・アクセシビリティ

12. W-27〜W-28: 重複コードの共通化
13. W-29: `key` プロパティの改善
14. W-30: `toError` ユーティリティの導入
15. W-19〜W-26: アクセシビリティ改善
