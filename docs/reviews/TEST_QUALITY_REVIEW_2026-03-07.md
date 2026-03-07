# テスト品質レビュー

> **レビュー日**: 2026-03-07
> **対象**: `backend/`, `frontend/`, `infrastructure/cdk/`, `.github/workflows/`
> **目的**: 現在のテスト資産の十分性評価と、将来の改善候補の記録
> **位置づけ**: 今すぐ着手しない改善候補の棚卸しメモ

---

## 概要

現状のテスト基盤は、回帰防止の土台としては十分に機能している。特に以下は評価できる。

- バックエンドに `unit` / `integration` の明確な分離がある
- フロントエンドにコンポーネント・ページ・Context・Hook のテストが広く存在する
- URL 生成、レビュー再確認、認証周辺など、壊れやすい機能に対する回帰テストがある
- バックエンド coverage は約 `81%`
- フロントエンド coverage は約 `83.45%`

一方で、テストの厚みには偏りがある。総評としては、

**「単体テストとモックベース統合テストは概ね充実しているが、重要ユーザーフローのE2E、境界層、低 coverage コンポーネントには不足がある」**

という評価である。

---

## テスト資産の内訳

レビュー時点で確認したテストファイル数は以下の通り。

- backend unit: 68
- backend integration: 5
- backend template/contract: 2
- frontend Vitest: 49
- frontend Playwright E2E: 1
- infrastructure/cdk Jest: 3

テスト種別の性格は次の通り。

- `backend/tests/unit/`: サービス・モデル・ハンドラ中心の単体テスト
- `backend/tests/integration/`: モックベースの統合テスト
- `backend/tests/test_template_*.py`: API ルートや SAM テンプレートの契約テスト
- `frontend/src/**/*.test.ts(x)`: JSDOM + RTL によるコンポーネント/ページ/機能テスト
- `frontend/e2e/auth.spec.ts`: Playwright による限定的なE2E/スモークテスト
- `infrastructure/cdk/test/*.test.ts`: CDK スタックのスナップショット/アサーションテスト

---

## 良い点

- バックエンドのサービス層は、DynamoDB モックや AI サービスモックを用いた検証が比較的厚い
- フロントエンドの主要ページには、単純表示だけでなくユーザー操作まで含めたテストがある
- `ReviewPage` には通常フローと再確認フローをまたぐ統合テストがある
- API ルートや SAM 定義の不整合を検出する静的テストが存在する
- TypeScript strict mode と `tsc -b` によるビルド型チェックが導入されている

---

## 主な不足箇所

### 1. 重要ユーザーフローのE2Eが薄い

Playwright テストは存在するが、実態としては認証ストレージやルーティング確認が中心であり、学習アプリとして重要な以下の通し動作を守れていない。

- ログイン → ホーム表示
- カード作成 → 保存 → 一覧確認
- 復習開始 → 採点 → 完了
- URL 生成 → 候補確認 → 保存
- デッキ作成/削除 → 一覧反映

現状の E2E は「存在する」が、「主要フローを品質ゲートとして担保する」水準には達していない。

### 2. フロントエンドの URL 生成まわりにテストの薄い領域がある

フロントエンド coverage 実行時、以下のファイルが特に薄かった。

- `frontend/src/components/BrowserProfileSettings.tsx`: `2.12%`
- `frontend/src/components/UrlInput.tsx`: `6.66%`
- `frontend/src/components/GenerateProgress.tsx`: `25%`
- `frontend/src/pages/GeneratePage.tsx`: `63.04%`
- `frontend/src/pages/DecksPage.tsx`: `66.66%`
- `frontend/src/services/api.ts`: `43.85%`

特に `GeneratePage` は機能の複雑さに対して coverage が低く、URL モード、ブラウザプロファイル連携、保存時の `references` 付与などの重要分岐が十分に守られていない。

### 3. バックエンドのハンドラ層・Webhook層にムラがある

バックエンド coverage では以下が相対的に低かった。

- `backend/src/api/handlers/cards_handler.py`: `28%`
- `backend/src/api/handlers/browser_profile_handler.py`: `36%`
- `backend/src/api/handlers/review_handler.py`: `47%`
- `backend/src/api/handlers/ai_handler.py`: `52%`
- `backend/src/webhook/line_handler.py`: `28%`

サービス層は比較的厚い一方で、HTTP 入出力、JSON パース、クエリパラメータ、エラー変換、Webhook 分岐など、実運用で壊れやすい境界層の確認が不足している。

### 4. `integration` テストの多くはモックベースである

`backend/tests/integration/` は存在するが、外部 API や実インフラに対する本物の統合試験ではない。アプリケーション内の連携確認としては有効だが、以下の種類の不具合は依然として漏れやすい。

- デプロイ環境の設定差異
- API Gateway / Lambda / 認証連携の実挙動差異
- LINE / OIDC / Browser profile の実運用差異
- frontend と backend をまたぐ契約差異

### 5. CI に接続されていないテストがある

PR 用 CI では以下が回っている。

- backend: `pytest tests/`
- frontend: `npm run type-check`, `npm run test`

一方で、以下は少なくとも PR CI に含まれていない。

- `frontend` Playwright E2E
- `infrastructure/cdk` Jest テスト

テスト資産として存在していても、継続的に守られていなければ回帰防止力は下がる。

### 6. フロントエンドテストに `act(...)` 警告が多い

`CardForm` や `CardsContext` 系のテストでは、coverage 実行時に `act(...)` 警告が複数出ている。現時点では失敗には至っていないが、非同期 state 更新の待ち方が粗く、将来の React 更新や実装変更で flaky になるリスクがある。

---

## 優先度付きの追加候補

### P1: 先に追加したい

- Playwright: `ログイン済み → 復習開始 → 採点 → 完了` のハッピーパス
- Playwright: `URLから生成 → 候補確認 → 保存 → カード一覧遷移`
- `GeneratePage` URL モード
  - `profile_id` が request に含まれる
  - `page_info` が画面表示される
  - 保存時に `references[type=url]` が付与される
  - 保存時に `deck_id` が渡る
  - URL 生成タイムアウト時に専用エラーメッセージが出る
- `BrowserProfileSettings`
  - 初回ロード成功/失敗
  - 作成成功時の再取得
  - 削除成功時に選択中 profile が解除される
  - `disabled` 時に選択/追加/削除できない
- `cards_handler.py`
  - `GET /cards` の `limit` 異常値
  - `deck_id` フィルタ
  - `POST/PUT` の invalid JSON
  - `ValidationError` → 400
  - `CardLimitExceededError` → 400
- `line_handler.py`
  - `save_url_cards` の成功
  - 部分保存時の件数メッセージ
  - URL 抽出失敗/空 chunk/AI エラー
  - 署名ヘッダの大小文字差
  - `postback` / `message` の分岐

### P2: その次に追加したい

- `UrlInput`
  - `http://` paste 時の補正挙動
  - blur 後のみエラー表示
  - 空文字ではエラーを出さない
- `DecksPage`
  - 削除確定で `deleteDeck` と `fetchCards` が呼ばれる
  - overlay click で削除ダイアログが閉じる
  - `due_count=0` 時に復習ボタン非表示
- `api.ts`
  - 401 同時発生時の token refresh 競合制御
  - refresh 失敗時の `authService.login()` 呼び出し
  - 204 response の処理
- `browser_profile_handler.py`
  - 一覧/作成/削除の正常系
  - 認可エラー・バリデーションエラー

### P3: 中長期で検討

- Playwright を PR CI の smoke suite に組み込む
- `infrastructure/cdk` の Jest テストを PR CI に組み込む
- frontend と backend をまたぐ API 契約テストの追加
- 本物の OIDC / LINE / browser profile を使った staging 向け E2E の整備

---

## 具体的に薄いファイル

将来のテスト追加対象として、以下は優先的に再確認する価値が高い。

### frontend

- `frontend/src/pages/GeneratePage.tsx`
- `frontend/src/components/BrowserProfileSettings.tsx`
- `frontend/src/components/UrlInput.tsx`
- `frontend/src/components/GenerateProgress.tsx`
- `frontend/src/pages/DecksPage.tsx`
- `frontend/src/services/api.ts`

### backend

- `backend/src/api/handlers/cards_handler.py`
- `backend/src/api/handlers/browser_profile_handler.py`
- `backend/src/api/handlers/review_handler.py`
- `backend/src/api/handlers/ai_handler.py`
- `backend/src/webhook/line_handler.py`

---

## 結論

現状のテストは、**「薄い」よりは「概ね整っているが偏りがある」** という評価が適切である。

- 単体テスト・モックベース統合テスト: 良好
- フロントエンドのコンポーネント/ページテスト: 良好
- 実運用に近いE2E: 不足
- 境界層ハンドラ/Webhook: 不足
- CI 連携の広さ: 不足

したがって、今後の改善方針としては、**テスト総量を増やすよりも、E2E と境界層に重点的に投資する** のが最も費用対効果が高い。
