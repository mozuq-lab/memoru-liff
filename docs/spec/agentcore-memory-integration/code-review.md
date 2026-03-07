# feature/agentcore-memory-integration コードレビュー

**レビュー日**: 2026-03-08
**レビュアー**: Claude Opus 4.6 + Codex (OpenAI)
**対象**: `main..feature/agentcore-memory-integration` (11 commits, 35 files, +7607/-73)

---

## 概要

Strands Agents SDK の SessionManager を活用し、チューターセッションの会話履歴管理を DynamoDB 直接管理から AgentCore Memory / DynamoDB SessionManager に切り替える実装。Factory パターンで backend を切り替え可能にしている。

---

## 指摘事項

### CRITICAL-1: BedrockTutorAIService との後方互換性が壊れている

**指摘者**: Codex + Claude (合意)

`TutorService` は `generate_response(..., session_manager=sm)` を常に呼ぶようになったが、`BedrockTutorAIService.generate_response()` は `session_manager` 引数を受け付けない。

SAM テンプレートの `USE_STRANDS` のデフォルト値は `"false"` なので、デフォルト構成では `BedrockTutorAIService` が使われ、`TypeError: unexpected keyword argument 'session_manager'` で即座にクラッシュする。

**該当箇所**:
- `backend/src/services/tutor_service.py:150` (`start_session`)
- `backend/src/services/tutor_service.py:246` (`send_message`)
- `backend/src/services/tutor_ai_service.py:96` (`BedrockTutorAIService.generate_response` - session_manager 未対応)

**対策案**:
- `BedrockTutorAIService.generate_response()` にも `session_manager=None` 引数を追加し、受け取っても無視する（`**kwargs` でも可）
- もしくは `USE_STRANDS` のデフォルトを `"true"` に変更

---

### HIGH-1: SAM テンプレートのデフォルト値で AgentCore が即 500 エラー

**指摘者**: Codex + Claude (合意)

`TutorSessionBackend` のデフォルト値が `"agentcore"` だが、`AgentCoreMemoryId` のデフォルト値が `""` (空文字列) のため、パラメータ未指定でデプロイすると `create_tutor_session_manager()` が `TutorAIServiceError("AGENTCORE_MEMORY_ID is required")` を即座に raise する。

**該当箇所**:
- `backend/template.yaml:73-81` (パラメータ定義)
- `backend/src/services/tutor_session_factory.py:85-90`

**対策案**:
- `TutorSessionBackend` のデフォルト値を `"dynamodb"` にする（AgentCore は明示的に opt-in）
- もしくは `AgentCoreMemoryId` が空の場合は自動的に dynamodb にフォールバック

---

### HIGH-2: start_session の put_item が SessionManager の履歴を上書きする

**指摘者**: Codex, Claude が確認

`start_session()` の流れ:
1. SessionManager 経由で AI greeting 生成 → SessionManager が `append_message()` で DynamoDB の `messages` フィールドに書き込み
2. その後 `self.table.put_item(Item=item)` でメタデータを書き込むが、`item` に `messages` キーがない

DynamoDB の `put_item` はアイテム全体を置換するため、SessionManager が書いた `messages` フィールドが消える。

**該当箇所**:
- `backend/src/services/tutor_service.py:145-188`
- `backend/src/services/tutor_session_manager.py:104` (`append_message`)

**対策案**:
- `put_item` の前に SessionManager の close を呼び、`put_item` 側で `messages` を含めるか
- もしくは `put_item` を先に実行し、SessionManager の操作を後にする
- AgentCore backend なら別テーブルなので影響なしだが、DynamoDB backend では致命的

---

### MEDIUM-1: get_session と end_session で会話メタデータが欠損

**指摘者**: Codex, Claude が確認

`_get_session_messages()` が SessionManager 経由で復元したメッセージに `timestamp=""` と `related_cards=[]` を固定値で埋めている。従来は各メッセージに実際の timestamp と related_cards が保持されていた。

さらに `end_session()` (L344) は SessionManager を使わず旧来の `item.get("messages", [])` を参照しているため、SessionManager 管理に移行した環境では空リストが返る。

**該当箇所**:
- `backend/src/services/tutor_service.py:455-510` (`_get_session_messages`)
- `backend/src/services/tutor_service.py:344` (`end_session`)

**対策案**:
- `_strands_to_dynamo_message()` で timestamp を保存しているので、`_get_session_messages()` でそれを復元する
- `end_session()` も `_get_session_messages()` を使うように統一する

---

### MEDIUM-2: IAM ポリシーが過剰 (bedrock-agentcore:* / Resource: *)

**指摘者**: Codex + Claude (合意)

`bedrock-agentcore:*` を `Resource: "*"` で全 Lambda に付与しており、最小権限の原則に反する。AgentCore を使わない構成 (dynamodb backend) でも全操作が許可される。

**該当箇所**:
- `backend/template.yaml:407-414`

**対策案**:
- Condition で `TutorSessionBackend == "agentcore"` の場合のみ付与
- Action を必要最小限（`bedrock-agentcore:InvokeMemory` 等）に絞る
- Resource を特定の Memory ARN に限定

---

### MEDIUM-3: DynamoDBSessionManager で毎回 boto3.resource を生成

**指摘者**: Codex, Claude が確認

`create_tutor_session_manager()` は呼び出しのたびに `DynamoDBSessionManager` を新規作成し、そのコンストラクタで `boto3.resource("dynamodb")` を生成する。`TutorService` は既に `self.dynamodb` を保持しているが、それが使い回されていない。

Lambda のコールドスタートやリクエストごとのオーバーヘッドが増加する。

**該当箇所**:
- `backend/src/services/tutor_session_factory.py:115`
- `backend/src/services/tutor_session_manager.py:55-63`

**対策案**:
- Factory に `dynamodb_resource` 引数を追加し、`TutorService` から渡す
- もしくはモジュールレベルでシングルトン化

---

### LOW-1: _MessageHolder のクラスミュータブルデフォルト

**指摘者**: Claude

`_get_session_messages()` 内で定義される `_MessageHolder` クラスの `messages` がクラス変数として `list[dict] = []` で定義されている。直後に `holder.messages = []` でインスタンス変数として上書きしているので実害はないが、紛らわしいコード。

**該当箇所**:
- `backend/src/services/tutor_service.py:477-479`

---

### LOW-2: Factory のモジュールレベル変数パターンが複雑

**指摘者**: Claude

`tutor_session_factory.py` でモジュールレベルに `MemoryClient = None` 等を定義し、`sys.modules[__name__]` 経由で書き換える lazy-import パターンは、テスト時の mock.patch のために必要とはいえ、可読性が低い。

---

## テスト品質

**指摘者**: Codex + Claude (合意)

- 統合テスト (`test_tutor_integration.py`) が SessionManager の実保存パスを通していない。テスト内で AI サービスを mock しているため、SessionManager のメソッド（`initialize`, `append_message`, `sync_agent`）が実際に呼ばれるかの検証が不十分
- `get_session` の既存テストで `messages` の中身検証が外されており、HIGH-2 の履歴消失バグを検出できない
- 個別の `test_tutor_session_manager.py`, `test_tutor_session_factory.py` は十分なカバレッジがある

---

## 良い点

両レビュアーが認めたポジティブな点:

1. **Factory パターンによる切り替え**: AgentCore / DynamoDB の切り替えが環境変数で制御でき、拡張性が高い
2. **後方互換性の意図**: `generate_response()` で session_manager の有無による分岐を設けている（ただし BedrockTutorAIService 側が未対応で不完全）
3. **フォールバック設計**: `_get_session_messages()` で SessionManager 失敗時に DynamoDB の messages フィールドにフォールバックする設計は堅実
4. **テストカバレッジ**: 新規ファイル (SessionManager, Factory) に対するユニットテストは充実（計 ~2600 行のテスト追加）
5. **ドキュメント**: 設計文書・タスクファイルが丁寧に整備されている

---

## 結論

### マージ判定: **要修正 (Changes Requested)**

CRITICAL-1 (BedrockTutorAIService 互換性) と HIGH-2 (put_item による履歴上書き) は、デフォルト構成で即座にクラッシュ or データ消失を引き起こすため、マージ前に必ず修正が必要。

### 優先度順の対応リスト

| 優先度 | ID | 内容 | 工数目安 |
|--------|------------|------|----------|
| CRITICAL | CRITICAL-1 | BedrockTutorAIService に session_manager 引数追加 | 小 |
| HIGH | HIGH-1 | SAM デフォルト値の修正 | 小 |
| HIGH | HIGH-2 | start_session の put_item 競合解消 | 中 |
| MEDIUM | MEDIUM-1 | end_session の SessionManager 対応 | 小 |
| MEDIUM | MEDIUM-2 | IAM ポリシーの最小化 | 小 |
| MEDIUM | MEDIUM-3 | boto3 resource の使い回し | 小 |
| LOW | LOW-1, LOW-2 | コードスタイル改善 | 小 |
