# feature/agentcore-memory-integration コードレビュー (第2回)

**レビュー日**: 2026-03-08 (第2回)
**レビュアー**: Claude Opus 4.6 + Codex (OpenAI o4-mini, read-only sandbox)
**対象**: `main..feature/agentcore-memory-integration` (11 commits, 35 files, +7813/-86)
**テスト結果**: 115 passed, 0 failed (5.34s)

---

## 前回レビューからの修正状況

| ID | 内容 | 状態 |
|----|------|------|
| CRITICAL-1 | BedrockTutorAIService に session_manager 引数追加 | **修正済** (ca50a9e) |
| HIGH-1 | SAM デフォルト値の修正 | **要確認** (下記 MEDIUM-3 参照) |
| HIGH-2 | start_session の put_item 競合解消 | **修正済** (put_item → SM の順序に変更) |

---

## 今回の指摘事項

### CRITICAL-1: AgentCore バックエンドで get_session の履歴復元が機能しない

**指摘者**: Codex (Claude 検証済み)

`_get_session_messages()` は簡易的な `_MessageHolder` クラスを作成し `sm.initialize(holder)` を呼んでいるが、実際の `AgentCoreMemorySessionManager` は `RepositorySessionManager` を継承しており、`initialize()` 内で `agent.agent_id` や Strands Session/SessionAgent の概念を前提としている。

`_MessageHolder` は `messages` 属性しか持たないため、AgentCore バックエンドでは `initialize()` が属性エラーまたは `SessionException` で失敗し、毎回フォールバックパスに落ちる。フォールバック先の `item.get("messages", [])` も、SessionManager 移行後は DynamoDB アイテムに `messages` フィールドが存在しないため、結果として空リストが返る。

**検証結果**: SDK ソースコード (`/opt/anaconda3/lib/python3.13/site-packages/bedrock_agentcore/memory/integrations/strands/session_manager.py`) にて、`AgentCoreMemorySessionManager.__init__` で `RepositorySessionManager.__init__(session_id=..., session_repository=self)` を呼び、`create_session()` / `read_session()` 内で `self.config.actor_id` や `memoryId` を使った `create_event()` / `list_events()` を実行することを確認。簡易 holder では対応不可。

**該当箇所**:
- `backend/src/services/tutor_service.py:473-510` (`_get_session_messages`)
- SDK: `session_manager.py:155` (`super().__init__`)
- SDK: `session_manager.py:162-192` (`create_session` / `read_session`)

**対策案**:
- AgentCore バックエンドの場合は、`MemoryClient.list_events()` を直接呼んで会話履歴を取得する専用パスを実装
- もしくは Strands `Agent` インスタンスを一時的に生成して `initialize()` に渡す

---

### CRITICAL-2: SAM テンプレートの IAM 権限が AgentCore SDK の要求に不足

**指摘者**: Codex (Claude 検証済み)

テンプレートでは `bedrock-agentcore:InvokeMemory` と `bedrock-agentcore:RetrieveMemory` のみ付与しているが、実際の `AgentCoreMemorySessionManager` が呼ぶ SDK メソッドは以下の API を使用する:

- `create_event` (セッション作成時・メッセージ保存時)
- `list_events` (セッション読み取り時)
- `get_event` (エージェント状態読み取り時)
- `retrieve_memory_records` (長期記憶取得時)

これらは `bedrock-agentcore:CreateEvent`, `bedrock-agentcore:ListEvents`, `bedrock-agentcore:GetEvent`, `bedrock-agentcore:RetrieveMemoryRecords` 等の IAM アクションに相当する可能性が高い。`TUTOR_SESSION_BACKEND=agentcore` でデプロイすると `AccessDenied` で動作しない。

**該当箇所**:
- `backend/template.yaml:415-419` (IAM ポリシー)
- SDK: `session_manager.py:181` (`create_event`)
- SDK: `session_manager.py:220` (`list_events`)

**対策案**:
- AWS ドキュメントで AgentCore Memory の正確な IAM アクション名を確認し、必要なアクションを追加
- 開発中は `bedrock-agentcore:*` で動作確認後、最小権限に絞る

---

### HIGH-1: start_session の AI 失敗時にセッション不整合

**指摘者**: Codex (Claude 確認済み)

`start_session()` は以下の順序で処理する:
1. `_auto_end_active_sessions()` — 既存セッション終了
2. `put_item()` — 新セッションメタデータ保存 (status=active)
3. `generate_response()` — AI greeting 生成

手順 3 で AI やSessionManager が失敗した場合、「旧セッションは終了済み、新セッションは active だが挨拶も履歴もない」という不整合状態になる。

**該当箇所**:
- `backend/src/services/tutor_service.py:148-178`

**対策案**:
- AI greeting 生成を先に行い、成功した場合のみ auto_end + put_item を実行
- もしくは AI 失敗時に新セッションを削除するロールバック処理を追加

---

### HIGH-2: [RELATED_CARDS] タグが SessionManager に保存され get_session で再露出

**指摘者**: Codex (Claude 確認済み)

`StrandsTutorAIService.generate_response()` は `[RELATED_CARDS: card1, card2]` タグ付きの生テキストを返し、Agent が SessionManager にそのまま保存する。`TutorService` は API レスポンス返却前に `clean_response_text()` でタグを除去するが、SessionManager に保存されるのはクリーニング前のテキスト。

`get_session` で `_get_session_messages()` が SessionManager から履歴を復元すると、タグ付きテキストがそのままクライアントに返る。

**該当箇所**:
- `backend/src/services/tutor_ai_service.py:234-235` (Agent がタグ付きテキストを SM に保存)
- `backend/src/services/tutor_service.py:179,254` (レスポンスのみ clean)
- `backend/src/services/tutor_service.py:486-503` (復元時に clean しない)

**対策案**:
- `_get_session_messages()` 内でも `clean_response_text()` を適用
- もしくは SessionManager への保存前にクリーニングする (Agent の callback フック等)

---

### MEDIUM-1: get_session / end_session で timestamp と related_cards が欠損

**指摘者**: Codex + Claude (合意、前回から未修正)

`_get_session_messages()` が SessionManager 経由で復元したメッセージに対して `related_cards=[]` と `timestamp=""` を固定値で埋めている。`_strands_to_dynamo_message()` で timestamp を保存しているにもかかわらず、復元時にそれを利用していない。

**該当箇所**:
- `backend/src/services/tutor_service.py:497-503`

**対策案**:
- DynamoDB SessionManager の場合: DynamoDB から直接 messages を読み取り timestamp/related_cards を復元
- AgentCore の場合: event の timestamp を利用

---

### MEDIUM-2: end_session が SessionManager を使わず旧 messages フィールドを参照

**指摘者**: Claude (前回から未修正)

`end_session()` (L345) は `_get_session_messages()` を呼んでいるが、DynamoDB の `item` が SessionManager 移行後は `messages` フィールドを持たない場合があり、フォールバック時に空リストが返る可能性がある。

**該当箇所**:
- `backend/src/services/tutor_service.py:345`

---

### MEDIUM-3: Factory の singleton が実 SDK では機能しない

**指摘者**: Codex (Claude 検証済み)

`create_tutor_session_manager()` は `_get_agentcore_client()` で MemoryClient のシングルトンを作成し `memory_client=client` として渡しているが、実際の `AgentCoreMemorySessionManager.__init__` は `memory_client` パラメータを受け取らない。`**kwargs` に吸収されて無視され、毎回 `MemoryClient(region_name=...)` が新規生成される。

**検証結果**: SDK ソースで `__init__(self, agentcore_memory_config, region_name=None, boto_session=None, boto_client_config=None, **kwargs)` を確認。`memory_client` は signature に存在しない。

**該当箇所**:
- `backend/src/services/tutor_session_factory.py:107-114`
- SDK: `session_manager.py:98-119` (constructor)

**対策案**:
- SDK の実際のインターフェースに合わせてファクトリを修正
- `region_name`, `boto_session` を渡す方式に変更
- boto3 Session をシングルトン化する方が実効性がある

---

### LOW-1: _MessageHolder のクラスミュータブルデフォルト

**指摘者**: Claude (前回から未修正)

`_get_session_messages()` 内の `_MessageHolder` クラスの `messages` がクラス変数として `list[dict] = []` で定義されている。`__init__` でインスタンス変数に上書きしているので実害はないが紛らわしい。

---

### LOW-2: Factory のモジュールレベル変数パターンの複雑さ

**指摘者**: Claude (前回から未修正)

`tutor_session_factory.py` の `sys.modules[__name__]` 経由 lazy-import パターンは可読性が低い。

---

## テスト品質

**指摘者**: Codex + Claude (合意)

### 良い点
- 新規ファイル (SessionManager, Factory) のユニットテストは充実 (計 ~2600 行追加)
- 統合テストで API レスポンス形状の検証、マルチターン、ライフサイクルテストが網羅的
- moto を活用した実 DynamoDB テーブルでの統合テスト

### 改善が必要な点
- AgentCore バックエンドのテストがすべてモックベースで、実 SDK の interface mismatch を検出できていない (CRITICAL-1, MEDIUM-3)
- `get_session` テストで `timestamp`, `related_cards` の値検証が欠落 (MEDIUM-1 が検出されない)
- AI レスポンスに `[RELATED_CARDS]` タグが含まれるケースの end-to-end テストがない (HIGH-2)

---

## 良い点

両レビュアーが認めたポジティブな点:

1. **Factory パターンによる柔軟な切り替え**: AgentCore / DynamoDB を環境変数で制御でき、拡張性が高い
2. **フォールバック設計**: `_get_session_messages()` の SessionManager 失敗時 DynamoDB フォールバックは堅実
3. **put_item 順序の修正**: put_item を SessionManager 操作の前に実行する修正により、messages 上書き問題は解消
4. **テストカバレッジ**: 115 テスト全通過、新規コードに対する充実したテスト
5. **ドキュメント**: 設計文書・タスクファイルが丁寧に整備されている
6. **BedrockTutorAIService 互換性修正**: 前回の CRITICAL-1 が ca50a9e で適切に修正済み

---

## 結論

### マージ判定: **要修正 (Changes Requested)**

#### DynamoDB バックエンドのみ使用する場合

DynamoDB バックエンドに限定すれば **概ね動作する** が、以下が必要:
- HIGH-1 (AI 失敗時の不整合) のリスク受容 or 修正
- HIGH-2 (RELATED_CARDS タグ露出) の修正
- MEDIUM-1 (timestamp/related_cards 欠損) の修正

#### AgentCore バックエンドを使用する場合

**現時点では動作しない**。以下の修正が必須:
- CRITICAL-1 (get_session 履歴復元)
- CRITICAL-2 (IAM 権限不足)
- MEDIUM-3 (Factory singleton 不整合)

### 優先度順の対応リスト

| 優先度 | ID | 内容 | 影響範囲 | 工数 |
|--------|-----------|------|----------|------|
| CRITICAL | CRITICAL-1 | AgentCore get_session 履歴復元の実装 | AgentCore のみ | 中 |
| CRITICAL | CRITICAL-2 | SAM IAM 権限を SDK 要件に合わせる | AgentCore のみ | 小 |
| HIGH | HIGH-1 | start_session AI 失敗時のロールバック | 全バックエンド | 中 |
| HIGH | HIGH-2 | RELATED_CARDS タグの履歴保存問題 | 全バックエンド | 小 |
| MEDIUM | MEDIUM-1 | timestamp/related_cards 復元 | 全バックエンド | 小 |
| MEDIUM | MEDIUM-2 | end_session の SessionManager 対応 | 全バックエンド | 小 |
| MEDIUM | MEDIUM-3 | Factory singleton を SDK に合わせる | AgentCore のみ | 小 |
| LOW | LOW-1,2 | コードスタイル改善 | - | 小 |

### 推奨マージ戦略

AgentCore 統合は本番未使用であることを前提に、以下の段階的アプローチを推奨:

1. **Phase 1** (マージ条件): HIGH-1, HIGH-2, MEDIUM-1, MEDIUM-2 を修正 → DynamoDB バックエンドとして安全にマージ可能
2. **Phase 2** (後続 PR): CRITICAL-1, CRITICAL-2, MEDIUM-3 を修正 → AgentCore バックエンドの有効化
