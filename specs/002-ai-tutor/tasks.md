# Tasks: AI Tutor (Interactive Learning)

**Input**: Design documents from `specs/002-ai-tutor/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/tutor-api.md, quickstart.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: DynamoDB テーブル定義、Pydantic モデル、API ルーティング、フロントエンド型定義など共通基盤の構築

- [x] T001 Add TutorSessionsTable (PK: user_id, SK: session_id, GSI: user_id-status-index) and IAM policies to `backend/template.yaml`
- [x] T002 [P] Create Pydantic models (TutorMessage, TutorSessionResponse, StartSessionRequest, SendMessageRequest, SendMessageResponse, SessionListResponse) in `backend/src/models/tutor.py`
- [x] T003 [P] Create TypeScript type definitions (TutorSession, TutorMessage, StartSessionRequest, SendMessageRequest, SendMessageResponse, SessionListResponse, LearningMode) in `frontend/src/types/tutor.ts`
- [x] T004 [P] Export tutor types from `frontend/src/types/index.ts`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: AI プロンプト、セッション管理サービス、API クライアントなど全ユーザーストーリーが依存する共通コンポーネント

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Tests for Foundational Phase (TDD: Red Phase)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T005a [P] Unit tests for tutor prompts (mode-specific prompt generation, card context injection, language-matching instruction) in `backend/tests/unit/test_tutor_prompts.py`
- [x] T006a [P] Unit tests for TutorAIService (Bedrock API call, multi-turn conversation, related card extraction) in `backend/tests/unit/test_tutor_ai_service.py`
- [x] T007a [P] Unit tests for TutorService (start_session, send_message, end_session, timeout check, message limit, auto-end active session, TTL) in `backend/tests/unit/test_tutor_service.py`
- [x] T008a [P] Unit tests for tutor handler (all endpoints, error responses including 409 for ended sessions, auth) in `backend/tests/unit/test_tutor_handler.py`

### Implementation for Foundational Phase

- [x] T005 Create mode-specific system prompt templates (free_talk, quiz, weak_point) with card context injection and language-matching instruction (respond in the same language as card content per FR-017) in `backend/src/services/prompts/tutor.py`
- [x] T006 Create TutorAIService (Bedrock Messages API multi-turn conversation, TUTOR_MODEL_ID env var, related card extraction from AI response) in `backend/src/services/tutor_ai_service.py`
- [x] T007 Create TutorService (start_session, send_message, end_session, list_sessions, get_session, auto-end existing active session, request-time timeout check: mark session as timed_out if last message > 30 min ago on any API call, message limit check, TTL calculation) in `backend/src/services/tutor_service.py`
- [x] T008 Create tutor API handler with Router (POST /sessions, POST /sessions/{sessionId}/messages with 409 Conflict for ended/timed_out sessions, DELETE /sessions/{sessionId}, GET /sessions, GET /sessions/{sessionId}) in `backend/src/api/handlers/tutor_handler.py`
- [x] T009 Register tutor router with prefix `/tutor` in `backend/src/api/handler.py` and add API Gateway routes to `backend/template.yaml`
- [x] T009a [P] Generate OpenAPI 3.0 specification from contracts/tutor-api.md in `specs/002-ai-tutor/contracts/tutor-api.openapi.yaml`
- [x] T010 [P] Create tutor API client (startSession, sendMessage, endSession, listSessions, getSession) in `frontend/src/services/tutor-api.ts` and export from `frontend/src/services/api.ts`

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 — Free Talk Learning Session (Priority: P1) 🎯 MVP

**Goal**: ユーザーがデッキを選択して Free Talk モードで AI チューターセッションを開始し、デッキ内容について自由に質問できる

**Independent Test**: デッキを選択 → Free Talk セッション開始 → デッキ内容について質問 → AI がカードを参照した回答を返す

### Tests for User Story 1 (TDD: Red Phase)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T012a [P] [US1] Component tests for TutorContext (session state, API integration, error handling) in `frontend/src/contexts/__tests__/TutorContext.test.tsx`
- [x] T012b [P] [US1] Component tests for ModeSelector, ChatMessage, ChatInput in `frontend/src/components/tutor/__tests__/`

### Implementation for User Story 1

- [x] T012 [US1] Create TutorContext (session state, messages, loading, error, startSession, sendMessage, endSession actions) in `frontend/src/contexts/TutorContext.tsx`
- [x] T013 [US1] Create ModeSelector component (Free Talk / Quiz / Weak Point Focus mode selection UI with icons and descriptions) in `frontend/src/components/tutor/ModeSelector.tsx`
- [x] T014 [P] [US1] Create ChatMessage component (user/assistant message styling, timestamp display, Tailwind chat bubble UI) in `frontend/src/components/tutor/ChatMessage.tsx`
- [x] T015 [P] [US1] Create ChatInput component (text input with send button, empty message prevention, disabled state during loading, max 2000 chars) in `frontend/src/components/tutor/ChatInput.tsx`
- [x] T016 [US1] Create TutorPage with mode selection → chat UI flow (ModeSelector → ChatMessage list → ChatInput, loading indicator, error handling with retry) in `frontend/src/pages/TutorPage.tsx`
- [x] T017 [US1] Add `/tutor/:deckId` route (ProtectedRoute) to `frontend/src/App.tsx`
- [x] T018 [US1] Add "AI Tutor" navigation button to deck view in `frontend/src/pages/HomePage.tsx` (2 taps to start session per SC-005)
- [x] T019 [US1] Wire TutorProvider into App component tree in `frontend/src/App.tsx`

**Checkpoint**: Free Talk セッションが完全に動作し、独立してテスト可能

---

## Phase 4: User Story 4 — Session Management (Priority: P2)

**Goal**: セッションの開始・継続・終了、会話履歴の保持、メッセージ上限（20 RT）、タイムアウト（30 分）管理

**Independent Test**: セッション開始 → メッセージ送信 → アプリ離脱 → 復帰 → 会話履歴が保持されている → セッション終了

### Implementation for User Story 4

- [x] T020 [US4] Add session continuation logic (fetch active session on TutorPage mount, resume if exists) to `frontend/src/contexts/TutorContext.tsx`
- [x] T021 [US4] Create SessionList component (recent ended sessions list, read-only, tap to view conversation history) in `frontend/src/components/tutor/SessionList.tsx`
- [x] T022 [US4] Add session list view and session history viewer to `frontend/src/pages/TutorPage.tsx`
- [x] T023 [US4] Add message limit reached UI (display limit message, suggest starting new session) to `frontend/src/pages/TutorPage.tsx`
- [x] T024 [US4] Add client-side timeout detection (30 min inactivity → show timeout message) to `frontend/src/contexts/TutorContext.tsx`
- [x] T025 [US4] Add session end button and confirmation to TutorPage chat header in `frontend/src/pages/TutorPage.tsx`
- [x] T025a [US4] Add mode switch handling (start new session when switching modes mid-session, per FR-012) to `frontend/src/pages/TutorPage.tsx`

**Checkpoint**: セッション管理（継続・終了・履歴・上限・タイムアウト・モード切替）が完全に動作

---

## Phase 5: User Story 2 — Quiz Mode (Priority: P2)

**Goal**: AI がデッキのカード内容からクイズを生成し、ユーザーの回答を評価してフィードバックを返す

**Independent Test**: Quiz モードでセッション開始 → AI が問題を出題 → 回答を送信 → 正誤判定とフィードバックが返る

### Implementation for User Story 2

- [x] T026 [US2] Enhance quiz system prompt in `backend/src/services/prompts/tutor.py` to instruct AI to generate questions from card content and evaluate answers with detailed feedback
- [x] T027 [US2] Add quiz-specific UI styling (question highlight, correct/incorrect visual feedback) to `frontend/src/components/tutor/ChatMessage.tsx`

**Checkpoint**: Quiz モードが独立して動作し、問題生成・回答評価・フィードバックが正しく機能

---

## Phase 6: User Story 3 — Weak Point Focus Mode (Priority: P3)

**Goal**: レビュー履歴から弱点カード（低正答率・低 ease factor）を特定し、AI が集中的に解説

**Independent Test**: レビュー履歴のあるデッキで Weak Point Focus セッション開始 → AI が弱点カードを重点的に解説。レビュー履歴なしの場合は Free Talk を提案

### Implementation for User Story 3

- [x] T028 [US3] Add weak card data retrieval (review history, accuracy, ease factor) to `backend/src/services/tutor_service.py` for weak_point mode session initialization
- [x] T029 [US3] Enhance weak_point system prompt in `backend/src/services/prompts/tutor.py` to include user's weak card data and instruct AI to prioritize those topics
- [x] T030 [US3] Add review history insufficiency check (return 422 when no review data) to session start in `backend/src/services/tutor_service.py`
- [x] T031 [US3] Add frontend handling for 422 error (display message suggesting Free Talk mode) in `frontend/src/contexts/TutorContext.tsx`

**Checkpoint**: Weak Point Focus モードが独立して動作。レビュー履歴なしの場合のフォールバックも機能

---

## Phase 7: User Story 5 — Related Card Navigation (Priority: P3)

**Goal**: AI 応答内の関連カード提案をタップ可能な chip として表示し、カード詳細に遷移

**Independent Test**: 会話中に AI がカードを参照 → 関連カード chip が表示 → タップ → CardDetailPage に遷移

### Implementation for User Story 5

- [x] T032 [P] [US5] Create RelatedCardChip component (tappable chip displaying card front text, navigate to `/cards/:id`) in `frontend/src/components/tutor/RelatedCardChip.tsx`
- [x] T033 [US5] Integrate RelatedCardChip into ChatMessage component (render chips below AI messages when related_cards is non-empty) in `frontend/src/components/tutor/ChatMessage.tsx`

**Checkpoint**: 関連カード chip の表示と遷移が正しく動作

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: エッジケース対応、エラーハンドリング強化、UX 改善

- [x] T034 Add empty deck validation (prevent session start, show appropriate message) to `backend/src/services/tutor_service.py` and `frontend/src/pages/TutorPage.tsx`
- [x] T035 Add AI service error handling (504 timeout, retry capability) to `backend/src/api/handlers/tutor_handler.py` and `frontend/src/contexts/TutorContext.tsx`
- [x] T036 Add large deck handling (100+ cards: summarize or truncate card context for Bedrock token limit) to `backend/src/services/tutor_ai_service.py`
- [x] T037 [P] Add loading indicator for AI response (typing animation or spinner) to `frontend/src/components/tutor/ChatMessage.tsx`
- [x] T039 Run backend tests (`cd backend && make test`) and frontend tests (`cd frontend && npm run test`) to verify no regressions

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion — BLOCKS all user stories
- **US1 Free Talk (Phase 3)**: Depends on Phase 2 — MVP deliverable
- **US4 Session Management (Phase 4)**: Depends on Phase 3 (needs basic TutorPage/TutorContext)
- **US2 Quiz (Phase 5)**: Depends on Phase 2 — can run parallel with Phase 3/4
- **US3 Weak Point (Phase 6)**: Depends on Phase 2 — can run parallel with Phase 3/4/5
- **US5 Related Cards (Phase 7)**: Depends on Phase 3 (needs ChatMessage component)
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational (Phase 2) — No dependencies on other stories
- **US4 (P2)**: Depends on US1 (extends TutorContext and TutorPage)
- **US2 (P2)**: Can start after Foundational (Phase 2) — Independent (prompt changes only)
- **US3 (P3)**: Can start after Foundational (Phase 2) — Independent (service + prompt changes)
- **US5 (P3)**: Depends on US1 (extends ChatMessage component)

### Within Each User Story

- Models/types before services
- Services before handlers/API
- Backend before frontend (API must exist for frontend to call)
- Core implementation before integration

### Parallel Opportunities

- T002, T003, T004 can run in parallel (different files, no dependencies)
- T005a, T006a, T007a, T008a can run in parallel (TDD test files, no dependencies)
- T012a, T012b can run in parallel (frontend test files, no dependencies)
- T010 can run in parallel with backend tasks T005-T009
- T014, T015 can run in parallel (different component files)
- T032 can run in parallel with other Phase 7 tasks
- US2 (Phase 5) and US3 (Phase 6) can run in parallel with each other

---

## Parallel Example: Phase 1 Setup

```bash
# Launch in parallel:
Task: T002 "Create Pydantic models in backend/src/models/tutor.py"
Task: T003 "Create TypeScript types in frontend/src/types/tutor.ts"
Task: T004 "Export tutor types from frontend/src/types/index.ts"
```

## Parallel Example: User Story 1

```bash
# After T012, T013 complete:
Task: T014 "Create ChatMessage component in frontend/src/components/tutor/ChatMessage.tsx"
Task: T015 "Create ChatInput component in frontend/src/components/tutor/ChatInput.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T004)
2. Complete Phase 2: Foundational (T005-T011)
3. Complete Phase 3: US1 Free Talk (T012-T019)
4. **STOP and VALIDATE**: Free Talk セッションが独立して動作することを確認
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 Free Talk → Test independently → Deploy/Demo (MVP!)
3. Add US4 Session Management → Test independently → Deploy/Demo
4. Add US2 Quiz + US3 Weak Point (parallel) → Test independently → Deploy/Demo
5. Add US5 Related Cards → Test independently → Deploy/Demo
6. Polish → Final validation → Deploy

### Task Summary

| Phase     | Story             | Task Count | Key Deliverables                                                  |
| --------- | ----------------- | ---------- | ----------------------------------------------------------------- |
| Phase 1   | Setup             | 4          | DynamoDB table, models, types                                     |
| Phase 2   | Foundational      | 12         | Tests (TDD), prompts, services, handler, API client, OpenAPI spec |
| Phase 3   | US1 Free Talk     | 10         | Tests (TDD), TutorPage, ChatMessage, ChatInput, ModeSelector      |
| Phase 4   | US4 Session Mgmt  | 7          | SessionList, timeout, limit, history, mode switch                 |
| Phase 5   | US2 Quiz          | 2          | Quiz prompt, quiz UI styling                                      |
| Phase 6   | US3 Weak Point    | 4          | Weak card data, prompt, 422 handling                              |
| Phase 7   | US5 Related Cards | 2          | RelatedCardChip, ChatMessage integration                          |
| Phase 8   | Polish            | 5          | Edge cases, error handling, final validation                      |
| **Total** |                   | **46**     |                                                                   |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
