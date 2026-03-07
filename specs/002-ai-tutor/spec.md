# Feature Specification: AI Tutor (Interactive Learning)

**Feature Branch**: `002-ai-tutor`
**Created**: 2026-03-06
**Status**: Draft
**Input**: User description: "デッキ単位で AI と対話しながら学習を深める。カードの暗記だけでなく「なぜそうなるのか」を理解し、関連知識を広げることで記憶の定着率を向上させる。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Free Talk Learning Session (Priority: P1)

A user selects a deck and starts an AI tutor session in "Free Talk" mode. The AI understands all cards in the deck and the user asks questions freely about the deck's topic. The AI responds with explanations, context, and suggests related cards from the deck.

**Why this priority**: This is the core value proposition — enabling deeper understanding through conversational learning. It provides immediate value to all users regardless of their learning stage and serves as the foundation for other learning modes.

**Independent Test**: Can be fully tested by starting a session with any deck, asking a question about the deck content, and verifying the AI provides a relevant answer referencing deck cards. Delivers value as a standalone Q&A feature.

**Acceptance Scenarios**:

1. **Given** a user has a deck with 10+ cards, **When** they start an AI tutor session in Free Talk mode, **Then** the AI sends an initial greeting message summarizing the deck content and inviting questions.
2. **Given** an active Free Talk session, **When** the user asks a question related to the deck topic, **Then** the AI responds with a relevant explanation and suggests related cards from the deck.
3. **Given** an active Free Talk session, **When** the user asks a follow-up question referencing a previous answer, **Then** the AI maintains conversation context and provides a coherent continuation.

---

### User Story 2 - Quiz Mode (Priority: P2)

A user selects a deck and starts an AI tutor session in "Quiz" mode. The AI generates questions based on the deck's card content and evaluates the user's answers, providing feedback and explanations for incorrect responses.

**Why this priority**: Quiz mode adds structured learning validation on top of the core dialogue capability. It helps users actively test their understanding rather than passively reading, which significantly improves retention.

**Independent Test**: Can be tested by starting a Quiz session, answering an AI-generated question, and verifying the AI provides appropriate feedback (correct/incorrect with explanation).

**Acceptance Scenarios**:

1. **Given** a user starts a Quiz mode session, **When** the session begins, **Then** the AI presents a question derived from the deck's card content.
2. **Given** the AI has asked a quiz question, **When** the user submits an answer, **Then** the AI evaluates the answer and provides feedback indicating whether it was correct, along with an explanation.
3. **Given** the user answers a quiz question incorrectly, **When** the AI provides feedback, **Then** the feedback includes the correct answer, an explanation of why it's correct, and links to related cards.

---

### User Story 3 - Weak Point Focus Mode (Priority: P3)

A user selects a deck and starts an AI tutor session in "Weak Point Focus" mode. The AI identifies cards the user struggles with (based on review history — low accuracy, low ease factor) and provides targeted explanations and practice for those specific topics.

**Why this priority**: This mode leverages existing SRS review data to personalize the learning experience. It requires review history to be meaningful, so it's most valuable for users who have already been reviewing cards regularly.

**Independent Test**: Can be tested by starting a Weak Point Focus session with a deck where the user has review history with some low-accuracy cards. Verify the AI focuses explanations on those weak areas.

**Acceptance Scenarios**:

1. **Given** a user has review history with cards that have low accuracy or low ease factor, **When** they start a Weak Point Focus session, **Then** the AI begins by addressing the user's weakest cards with targeted explanations.
2. **Given** an active Weak Point Focus session, **When** the AI explains a weak card, **Then** the explanation includes why the concept might be confusing and offers alternative ways to remember it.
3. **Given** a user has no review history for the selected deck, **When** they attempt to start a Weak Point Focus session, **Then** the system informs the user that review history is needed and suggests using Free Talk mode instead.

---

### User Story 4 - Session Management (Priority: P2)

A user can start, continue, and end tutor sessions. Conversation history is preserved within a session so the user can return to an ongoing conversation. Sessions have a reasonable message limit to manage costs and context quality.

**Why this priority**: Session management is essential infrastructure for a usable multi-turn conversation experience. Without it, users lose conversation context and the AI cannot maintain coherent dialogue.

**Independent Test**: Can be tested by starting a session, sending messages, leaving the app, returning, and verifying the conversation history is preserved. Also test that the session can be explicitly ended.

**Acceptance Scenarios**:

1. **Given** a user starts a new tutor session, **When** the session is created, **Then** the system assigns a unique session identifier and stores the session metadata.
2. **Given** an active session with conversation history, **When** the user sends a new message, **Then** the AI responds with awareness of the full conversation context.
3. **Given** a session has reached the maximum message limit (20 round-trips), **When** the user tries to send another message, **Then** the system informs the user the session limit is reached and suggests starting a new session.
4. **Given** an active session, **When** the user ends the session, **Then** the session is marked as ended and resources are released.

---

### User Story 5 - Related Card Navigation (Priority: P3)

During a tutor session, the AI suggests related cards from the deck. The user can tap on a related card suggestion to view the card details, providing a bridge between conversational learning and card-based review.

**Why this priority**: This feature enhances the integration between the tutor and the existing card system, but is not essential for the core learning dialogue to function.

**Independent Test**: Can be tested by engaging in a conversation where the AI mentions related cards, tapping a card suggestion, and verifying the card detail is displayed.

**Acceptance Scenarios**:

1. **Given** the AI responds with related card suggestions, **When** the user taps a related card, **Then** the card's front and back content is displayed.
2. **Given** the AI responds, **When** the response includes references to deck content, **Then** relevant cards are displayed as tappable chips below the AI message.

---

### Edge Cases

- What happens when a deck has no cards? The system should prevent starting a tutor session and display an appropriate message.
- What happens when a deck has more than 100 cards? The system should handle large decks gracefully without degraded response quality.
- What happens when the AI service is temporarily unavailable? The system should display a user-friendly error message and allow retry.
- What happens when the user sends an empty message? The system should prevent submission of empty messages.
- What happens when a session times out mid-conversation (30 minutes of inactivity)? The system should inform the user and allow them to start a new session.
- What happens when the user switches learning modes mid-session? A new session should be started with the new mode.

## Clarifications

### Session 2026-03-07

- Q: セッションデータ（会話履歴）の保持期間はどうしますか？ → A: セッション終了後7日間保持（DynamoDB TTL で自動削除）
- Q: 1ユーザーが同時に保持できるアクティブセッション数に制限はありますか？ → A: 1ユーザー1アクティブセッション（新規セッション開始時に既存アクティブセッションを自動終了）
- Q: AIチューターの応答言語はどのように決定しますか？ → A: カードのコンテンツ言語に合わせる（日本語カード→日本語応答）
- Q: セッションのタイムアウト時間はどのくらいですか？ → A: 最後のメッセージから30分でタイムアウト
- Q: 過去セッションの一覧表示・閲覧UIは必要ですか？ → A: 直近セッションの一覧表示あり（読み取り専用、会話履歴の閲覧のみ）

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow users to start an AI tutor session by selecting a deck and choosing a learning mode (Free Talk, Quiz, or Weak Point Focus).
- **FR-002**: System MUST provide the AI with the full content of all cards (front and back) in the selected deck as learning context.
- **FR-003**: System MUST maintain conversation history within a session so that the AI can reference prior messages.
- **FR-004**: System MUST limit sessions to a maximum of 20 round-trip exchanges to manage quality and cost.
- **FR-005**: System MUST display AI responses in a chat-style interface with distinct visual styling for user and AI messages.
- **FR-006**: System MUST allow users to explicitly end a tutor session.
- **FR-007**: System MUST suggest related cards from the deck in AI responses when relevant to the conversation.
- **FR-008**: In Quiz mode, the AI MUST generate questions based on deck card content and evaluate user answers.
- **FR-009**: In Weak Point Focus mode, the AI MUST prioritize explaining cards with low accuracy or low ease factor from the user's review history.
- **FR-010**: System MUST display an appropriate message when a user tries to start Weak Point Focus mode without sufficient review history.
- **FR-011**: System MUST prevent starting a tutor session for decks with no cards.
- **FR-012**: System MUST provide the ability to switch learning modes, which starts a new session.
- **FR-013**: System MUST display a loading indicator while waiting for AI responses.
- **FR-014**: System MUST handle AI service errors gracefully with user-friendly error messages and retry capability.
- **FR-015**: Users MUST be able to access the AI tutor from the deck view in the home page.
- **FR-016**: System MUST limit each user to 1 active session at a time. When a user starts a new session, any existing active session MUST be automatically ended.
- **FR-017**: AI MUST respond in the same language as the deck's card content (e.g., Japanese cards → Japanese responses).
- **FR-018**: System MUST automatically timeout sessions after 30 minutes of inactivity (no new messages). Timed-out sessions are marked as ended.
- **FR-019**: System MUST provide a read-only list of recent ended sessions (within 7-day retention period), allowing users to view past conversation history.
- **FR-020**: Users MUST NOT be able to resume or add messages to ended sessions; they can only view the conversation history.

### Key Entities

- **Tutor Session**: Represents an active learning conversation between a user and the AI for a specific deck. Key attributes: associated user, associated deck, learning mode, conversation history, creation time, message count, session status (active/ended), TTL (session終了後7日間で DynamoDB TTL により自動削除).
- **Tutor Message**: An individual message within a session. Key attributes: sender (user or AI), message content, related card references, timestamp.
- **Learning Mode**: The type of interaction pattern for a session. Values: Free Talk, Quiz, Weak Point Focus.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can start a tutor session and receive the first AI response within 10 seconds.
- **SC-002**: Users can complete a 10-message conversation (5 round-trips) without experiencing loss of conversation context.
- **SC-003**: In Quiz mode, at least 80% of AI-generated questions are directly relevant to the deck's card content.
- **SC-004**: In Weak Point Focus mode, the AI prioritizes the user's lowest-performing cards (by accuracy or ease factor) in at least 70% of its initial explanations.
- **SC-005**: The AI tutor feature is accessible from the deck view with no more than 2 taps to start a session.
- **SC-006**: Users can identify related card suggestions in AI responses and navigate to them with a single tap.
- **SC-007**: Error states (service unavailable, session limit reached, empty deck) are communicated clearly with actionable guidance for the user.
