# Tasks: URL からカード自動生成（AgentCore Browser 活用）

**Input**: Design documents from `/specs/002-url-card-generation/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: TDD 必須（Constitution Principle I）。各ユーザーストーリーでテスト → 実装の順で進行。

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: プロジェクト依存関係の追加と基本構造のセットアップ

- [x] T001 Add Python dependencies (beautifulsoup4, markdownify) to backend/requirements.txt
- [x] T002 [P] Create URL generation Pydantic models in backend/src/models/url_generate.py
- [x] T003 [P] Add TypeScript type definitions for URL generation in frontend/src/types/generate.ts

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 全ユーザーストーリーが依存するコア基盤。URL バリデーションとコンテンツ取得の基本機能。

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 Write unit tests for URL validator in backend/tests/unit/test_url_validator.py
- [x] T005 Implement URL validator (https enforcement, SSRF prevention, length check) in backend/src/utils/url_validator.py
- [x] T006 Write unit tests for content chunker in backend/tests/unit/test_content_chunker.py
- [x] T007 Implement content chunker (heading-based section split, 3000 char limit, context attachment) in backend/src/services/content_chunker.py
- [x] T008 Add `generate_cards_from_url` method to AIService protocol in backend/src/services/ai_service.py
- [x] T009 Create URL generation prompt templates (card_type variants: qa, definition, cloze) in backend/src/services/prompts/url_generate.py

**Checkpoint**: Foundation ready — URL validation, chunking, prompt templates, and protocol defined

---

## Phase 3: User Story 1 — 公開 Web ページからカード生成 (Priority: P1) 🎯 MVP

**Goal**: ユーザーが公開 Web ページの URL を貼り付けると、HTTP fetch でコンテンツを取得し、AI が暗記カードを自動生成する。プレビュー・編集・保存が可能。

**Independent Test**: `POST /cards/generate-from-url` に公開ページ URL を送信 → カード配列が返る → フロントエンドでプレビュー表示 → 保存してデッキに追加される

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T010 [P] [US1] Write unit tests for HTTP content fetcher in backend/tests/unit/test_url_content_service.py
- [x] T011 [P] [US1] Write integration tests for generate-from-url API endpoint in backend/tests/integration/test_url_generate_api.py

### Implementation for User Story 1

- [x] T012 [US1] Implement HTTP content fetcher (HEAD check, GET with timeout, HTML→text via BeautifulSoup+markdownify) in backend/src/services/url_content_service.py
- [x] T013 [US1] Implement `generate_cards_from_url` in StrandsAIService (chunk→generate→merge→deduplicate) in backend/src/services/strands_service.py
- [x] T014 [US1] Implement `generate_cards_from_url` in BedrockService in backend/src/services/bedrock.py
- [x] T015 [US1] Add `generate_from_url` handler to API router in backend/src/api/handlers/ai_handler.py
- [x] T016 [US1] Add UrlGenerateFunction Lambda definition (120s timeout, 512MB, IAM for Bedrock) in backend/template.yaml
- [x] T017 [P] [US1] Create UrlInput component (URL input form with validation display) in frontend/src/components/UrlInput.tsx
- [x] T018 [P] [US1] Create GenerateProgress component (3-step progress: fetch→analyze→generate) in frontend/src/components/GenerateProgress.tsx
- [x] T019 [US1] Add `generateFromUrl()` method to API client in frontend/src/services/api.ts
- [x] T020 [US1] Extend GeneratePage with URL tab (tab switch between text/URL, integrate UrlInput and GenerateProgress) in frontend/src/pages/GeneratePage.tsx

**Checkpoint**: 公開ページの URL からカード生成→プレビュー→保存の一連のフローが動作する

---

## Phase 4: User Story 2 — SPA・動的コンテンツページからのカード生成 (Priority: P2)

**Goal**: AgentCore Browser を使用して JavaScript レンダリング後の DOM からコンテンツを取得し、カードを生成する。SPA 自動判定で HTTP fetch からシームレスにフォールバック。

**Independent Test**: SPA サイト（React ベースのドキュメントサイト等）の URL → AgentCore Browser がレンダリング → コンテンツ取得 → カード生成成功

### Tests for User Story 2

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T021 [P] [US2] Write unit tests for SPA detection logic in backend/tests/unit/test_url_content_service.py (extend)
- [x] T022 [P] [US2] Write unit tests for AgentCore Browser integration (mock) in backend/tests/unit/test_browser_service.py

### Implementation for User Story 2

- [x] T023 [US2] Implement SPA detection logic (noscript tag, empty container, bundle.js pattern, text threshold) in backend/src/services/url_content_service.py (extend)
- [x] T024 [US2] Implement AgentCore Browser content fetcher (create session, navigate, wait for render, extract DOM) in backend/src/services/browser_service.py
- [x] T025 [US2] Add AgentCore Browser IAM permissions (bedrock-agentcore:*) and environment variables to backend/template.yaml
- [x] T026 [US2] Add fallback logic: HTTP fetch first → SPA detected → AgentCore Browser retry in backend/src/services/url_content_service.py (extend)

**Checkpoint**: SPA サイトの URL でも正常にカード生成ができ、静的ページでは Browser を使わない

---

## Phase 5: User Story 3 — 生成オプションのカスタマイズ (Priority: P2)

**Goal**: ユーザーがカードタイプ（Q&A / 用語定義 / 穴埋め）と生成枚数の目安を指定できる。

**Independent Test**: 同じ URL で card_type=cloze と card_type=qa を指定 → 異なる形式のカードが生成される。target_count=5 と target_count=20 → 枚数が異なる。

### Tests for User Story 3

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T027 [P] [US3] Write unit tests for card type prompt variants in backend/tests/unit/test_url_generate_prompts.py
- [x] T028 [P] [US3] Write component tests for GenerateOptions in frontend/src/components/__tests__/GenerateOptions.test.tsx

### Implementation for User Story 3

- [x] T029 [US3] Implement card type-specific prompt logic (definition, cloze variants) in backend/src/services/prompts/url_generate.py (verified by tests)
- [x] T030 [US3] Wire target_count parameter through to chunk-level generation and merge logic in backend/src/services/strands_service.py and backend/src/services/bedrock.py (verified by tests)
- [x] T031 [US3] Create GenerateOptions component (card type selector, target count slider) in frontend/src/components/GenerateOptions.tsx
- [x] T032 [US3] Integrate GenerateOptions into GeneratePage URL tab in frontend/src/pages/GeneratePage.tsx (extend)

**Checkpoint**: ユーザーがオプションを変えると、生成結果のカードタイプと枚数が変わる

---

## Phase 6: User Story 4 — LINE チャットからの URL カード生成 (Priority: P3)

**Goal**: LINE チャットに URL を送信すると Bot がカードを生成し、Flex Message で結果を返す。

**Independent Test**: LINE チャットに URL 送信 → Bot が「カード生成中...」と返信 → 生成完了後に Flex Message でプレビュー表示

### Tests for User Story 4

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T033 [P] [US4] Write unit tests for URL detection in LINE message handler in backend/tests/unit/test_webhook_url_handler.py
- [x] T034 [P] [US4] Write unit tests for card preview Flex Message builder in backend/tests/unit/test_flex_message_builder.py

### Implementation for User Story 4

- [x] T035 [US4] Add URL detection to LINE Webhook message handler in backend/src/webhook/line_handler.py (extend)
- [x] T036 [US4] Create Flex Message builder for card preview (carousel format) in backend/src/services/flex_messages.py (extend)
- [x] T037 [US4] Implement async card generation flow (progress reply → generate → result reply) in backend/src/webhook/line_handler.py (extend)
- [x] T038 [US4] Add save callback handler (user taps save button in Flex Message) in backend/src/webhook/line_handler.py (extend)

**Checkpoint**: LINE チャットに URL を送信→生成→Flex Message プレビュー→保存 が動作する

---

## Phase 7: User Story 5 — 認証が必要なページからのカード生成 (Priority: P3)

**Goal**: AgentCore Browser の Browser Profiles 機能を使い、ログインが必要なページからもカードを生成できる。

**Independent Test**: Browser Profile にログインセッション保存済み → 認証必要ページの URL → 認証済みアクセスでカード生成成功

### Tests for User Story 5

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T039 [P] [US5] Write unit tests for browser profile management in backend/tests/unit/test_browser_profile_service.py
- [ ] T040 [P] [US5] Write integration tests for authenticated page access in backend/tests/integration/test_authenticated_url_generate.py

### Implementation for User Story 5

- [ ] T041 [US5] Create browser profile management service (create, list, validate profiles) in backend/src/services/browser_profile_service.py
- [ ] T042 [US5] Add profile_id parameter to URL generation request and pass to AgentCore Browser session in backend/src/services/url_content_service.py (extend) and backend/src/models/url_generate.py (extend)
- [ ] T043 [US5] Add browser profile API endpoints (GET /browser-profiles, POST /browser-profiles) in backend/src/api/handlers/browser_profile_handler.py
- [ ] T044 [US5] Create BrowserProfileSettings component (profile list, add/remove) in frontend/src/components/BrowserProfileSettings.tsx
- [ ] T045 [US5] Add profile selection to GeneratePage URL tab in frontend/src/pages/GeneratePage.tsx (extend)

**Checkpoint**: 認証が必要なページからもカード生成でき、Browser Profile の管理が可能

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: 品質向上、セキュリティ強化、ドキュメント整備

- [ ] T046 [P] Add error handling for edge cases (PDF links, image-heavy pages, multilingual pages, redirects) in backend/src/services/url_content_service.py (extend)
- [ ] T047 [P] Add duplicate detection warning (same URL re-generation) in backend/src/api/handlers/ai_handler.py (extend)
- [ ] T048 Add domain allow/block list configuration (FR-014) in backend/src/utils/url_validator.py (extend)
- [ ] T049 [P] Add Lambda Powertools structured logging for URL generation flow in backend/src/services/url_content_service.py (extend)
- [ ] T050 Run backend tests and verify coverage ≥ 80% via `cd backend && make test`
- [ ] T051 Run frontend tests and type-check via `cd frontend && npm run test && npm run type-check`
- [ ] T052 Run quickstart.md validation (manual smoke test with local API)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational (Phase 2)
- **US2 (Phase 4)**: Depends on US1 (Phase 3) — extends url_content_service.py
- **US3 (Phase 5)**: Depends on US1 (Phase 3) — extends prompts and frontend
- **US4 (Phase 6)**: Depends on US1 (Phase 3) — uses generate_cards_from_url
- **US5 (Phase 7)**: Depends on US2 (Phase 4) — extends Browser integration
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### User Story Dependencies

```text
Phase 1: Setup
     ↓
Phase 2: Foundational
     ↓
Phase 3: US1 (MVP) ─────────────────────┐
     ↓              ↓            ↓       │
Phase 4: US2    Phase 5: US3  Phase 6: US4  │
     ↓                                    │
Phase 7: US5                              │
     ↓                                    ↓
Phase 8: Polish ←─────────────────────────┘
```

### Within Each User Story

- Tests MUST be written and FAIL before implementation (TDD Red → Green → Refactor)
- Models before services
- Services before endpoints/handlers
- Backend before frontend (API must exist for frontend to call)
- Core implementation before integration

### Parallel Opportunities

- **Phase 1**: T002 and T003 can run in parallel (different languages)
- **Phase 2**: T004/T005 and T006/T007 are independent pairs (validator vs chunker)
- **Phase 3**: T010 and T011 (tests), T017 and T018 (frontend components) can run in parallel
- **Phase 4**: T021 and T022 (tests) can run in parallel
- **Phase 5**: T027 and T028 (tests) can run in parallel; T031 can start before T029/T030
- **Phase 6**: T033 and T034 (tests) can run in parallel
- **Phase 7**: T039 and T040 (tests) can run in parallel
- **Phase 8**: T046, T047, T049 can all run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch tests in parallel:
Task: T010 "Unit tests for HTTP content fetcher in backend/tests/unit/test_url_content_service.py"
Task: T011 "Integration tests for generate-from-url API in backend/tests/integration/test_url_generate_api.py"

# After tests written, implementation:
Task: T012 "HTTP content fetcher" (backend)
Task: T013 "StrandsAIService.generate_cards_from_url" (backend)
Task: T014 "BedrockService.generate_cards_from_url" (backend)

# Frontend components in parallel:
Task: T017 "UrlInput component"
Task: T018 "GenerateProgress component"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T003)
2. Complete Phase 2: Foundational (T004-T009)
3. Complete Phase 3: User Story 1 (T010-T020)
4. **STOP and VALIDATE**: Test US1 independently — URL → カード生成 → プレビュー → 保存
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 → Test independently → Deploy (MVP!)
3. Add US2 → SPA 対応追加 → Deploy
4. Add US3 → オプションカスタマイズ追加 → Deploy
5. Add US4 → LINE チャット統合 → Deploy
6. Add US5 → 認証ページ対応 → Deploy
7. Each story adds value without breaking previous stories

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing (TDD Red phase)
- Commit after each task (CLAUDE.md requirement)
- Stop at any checkpoint to validate story independently
