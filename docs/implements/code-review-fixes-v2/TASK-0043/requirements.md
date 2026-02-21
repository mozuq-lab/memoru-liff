# TASK-0043: card_count Transaction Fixes - TDD Requirements

**Task ID**: TASK-0043
**Task Type**: TDD (Test-Driven Development)
**Created**: 2026-02-21
**Related Requirements**: REQ-V2-011, REQ-V2-012, REQ-V2-013, REQ-V2-014, REQ-V2-101, REQ-V2-102, REQ-V2-103

---

## 1. Overview

This document defines the detailed TDD requirements for fixing 4 critical issues in the DynamoDB card_count transaction management. Each fix is specified using EARS (Easy Approach to Requirements Syntax) notation with acceptance criteria, edge cases, specific code locations, and reliability levels.

### Scope of Changes

| # | Fix | File(s) | Method(s) |
|---|-----|---------|-----------|
| 1 | `if_not_exists` safety for card_count increment | `backend/src/services/card_service.py` | `create_card` (L106-127) |
| 2 | Error classification of `TransactionCanceledException` | `backend/src/services/card_service.py` | `create_card` (L129-133) |
| 3 | Atomic card_count decrement on delete | `backend/src/services/card_service.py` | `delete_card` (L234-250) |
| 4 | User existence guarantee before card creation | `backend/src/api/handler.py` | `create_card` endpoint (L337-382) |

---

## 2. EARS Notation Requirements

### 2.1 Fix 1: `if_not_exists` Safety (REQ-V2-011, REQ-V2-101)

#### EARS-001: Normal card_count Increment

**Type**: Ubiquitous (always applies)

> The system shall use `if_not_exists(card_count, :zero) + :inc` in the UpdateExpression when incrementing card_count during card creation.

**Reliability**: 🔵 *CR-02: card_service.py L112 uses bare `card_count + :inc` which fails when attribute is missing*

**Code Location**: `backend/src/services/card_service.py` line 112

**Current Code**:
```python
'UpdateExpression': 'SET card_count = card_count + :inc',
```

**Expected Code**:
```python
'UpdateExpression': 'SET card_count = if_not_exists(card_count, :zero) + :inc',
```

#### EARS-002: Condition Expression Safety

**Type**: Ubiquitous

> The system shall use `if_not_exists(card_count, :zero) < :limit` in the ConditionExpression when checking the card limit during card creation.

**Reliability**: 🔵 *CR-02: card_service.py L113 uses bare `card_count < :limit` which fails when attribute is missing*

**Code Location**: `backend/src/services/card_service.py` line 113

**Current Code**:
```python
'ConditionExpression': 'card_count < :limit',
```

**Expected Code**:
```python
'ConditionExpression': 'if_not_exists(card_count, :zero) < :limit',
```

#### EARS-003: Zero Expression Attribute Value

**Type**: Ubiquitous

> The system shall include `:zero` with value `{'N': '0'}` in the ExpressionAttributeValues for the card_count update transaction.

**Reliability**: 🔵 *Derived from EARS-001 and EARS-002; if_not_exists requires a fallback value*

**Code Location**: `backend/src/services/card_service.py` lines 114-117

**Current Code**:
```python
'ExpressionAttributeValues': {
    ':inc': {'N': '1'},
    ':limit': {'N': str(self.MAX_CARDS_PER_USER)}
}
```

**Expected Code**:
```python
'ExpressionAttributeValues': {
    ':inc': {'N': '1'},
    ':limit': {'N': str(self.MAX_CARDS_PER_USER)},
    ':zero': {'N': '0'}
}
```

#### EARS-004: Missing card_count Initialization

**Type**: Event-driven

> When a user record exists but lacks the `card_count` attribute, the system shall treat card_count as 0 and successfully create the card with card_count set to 1.

**Reliability**: 🔵 *CR-02: New users created by get_or_create_user may not have card_count attribute initially, depending on User.to_dynamodb_item() implementation*

---

### 2.2 Fix 2: Error Classification (REQ-V2-012, REQ-V2-102, REQ-V2-103)

#### EARS-005: InternalError Exception Class

**Type**: Ubiquitous

> The system shall define an `InternalError` exception class that inherits from `CardServiceError` for non-limit-related transaction failures.

**Reliability**: 🔵 *CR-02: Currently all TransactionCanceledException are classified as CardLimitExceededError, masking other errors*

**Code Location**: `backend/src/services/card_service.py` (new class, after `CardLimitExceededError` definition at L26-29)

**Expected Code**:
```python
class InternalError(CardServiceError):
    """Raised when an internal transaction error occurs."""
    pass
```

#### EARS-006: ConditionalCheckFailed Classification

**Type**: Event-driven

> When a `TransactionCanceledException` occurs during card creation and `CancellationReasons[0].Code` equals `'ConditionalCheckFailed'`, the system shall raise `CardLimitExceededError`.

**Reliability**: 🔵 *CR-02: Index 0 in TransactItems is the Users table Update operation where the card_count condition is checked*

**Code Location**: `backend/src/services/card_service.py` lines 129-133

**Current Code**:
```python
except ClientError as e:
    if e.response["Error"]["Code"] == "TransactionCanceledException":
        raise CardLimitExceededError(f"Card limit of {self.MAX_CARDS_PER_USER} exceeded")
    raise CardServiceError(f"Failed to create card: {e}")
```

**Expected Code**:
```python
except ClientError as e:
    if e.response["Error"]["Code"] == "TransactionCanceledException":
        reasons = e.response.get("CancellationReasons", [])
        if reasons and reasons[0].get("Code") == "ConditionalCheckFailed":
            raise CardLimitExceededError(
                f"Card limit of {self.MAX_CARDS_PER_USER} exceeded"
            )
        logger.error(f"Transaction cancelled with reasons: {reasons}")
        raise InternalError("Card creation failed due to transaction conflict")
    raise CardServiceError(f"Failed to create card: {e}")
```

#### EARS-007: Non-Limit Transaction Failure

**Type**: Event-driven

> When a `TransactionCanceledException` occurs during card creation and `CancellationReasons[0].Code` is NOT `'ConditionalCheckFailed'`, the system shall raise `InternalError` (not `CardLimitExceededError`).

**Reliability**: 🔵 *CR-02: Other error codes (e.g., ValidationError, TransactionConflict) indicate non-limit failures that should not be reported as card limit exceeded*

#### EARS-008: Missing CancellationReasons

**Type**: Event-driven

> When a `TransactionCanceledException` occurs during card creation and the `CancellationReasons` key is absent or the array is empty, the system shall raise `InternalError`.

**Reliability**: 🟡 *CR-02: DynamoDB API documentation suggests CancellationReasons may be absent in some error scenarios*

#### EARS-009: Error Logging for Non-Limit Failures

**Type**: Event-driven

> When a `TransactionCanceledException` occurs that is not a card limit exceeded error, the system shall log the CancellationReasons at ERROR level before raising the exception.

**Reliability**: 🔵 *CR-02: Required for debugging visibility of non-limit transaction failures*

---

### 2.3 Fix 3: Transactional Delete with card_count Decrement (REQ-V2-013)

#### EARS-010: Transactional Delete Operation

**Type**: Ubiquitous

> The system shall use `transact_write_items` to atomically delete a card from the Cards table, delete the corresponding review from the Reviews table, and decrement `card_count` in the Users table.

**Reliability**: 🔵 *CR-02: card_service.py L234-250 currently uses simple delete_item without card_count update, causing data integrity drift*

**Code Location**: `backend/src/services/card_service.py` lines 234-250 (entire `delete_card` method)

**Current Code**:
```python
def delete_card(self, user_id: str, card_id: str) -> None:
    self.get_card(user_id, card_id)
    try:
        self.table.delete_item(Key={"user_id": user_id, "card_id": card_id})
    except ClientError as e:
        raise CardServiceError(f"Failed to delete card: {e}")
```

**Expected Structure**:
```python
def delete_card(self, user_id: str, card_id: str) -> None:
    self.get_card(user_id, card_id)  # Verify card exists
    try:
        client = self.dynamodb.meta.client
        client.transact_write_items(
            TransactItems=[
                {  # Index 0: Delete card
                    'Delete': {
                        'TableName': self.table_name,
                        'Key': {'user_id': {'S': user_id}, 'card_id': {'S': card_id}},
                        'ConditionExpression': 'attribute_exists(card_id)'
                    }
                },
                {  # Index 1: Delete review (no condition - may not exist)
                    'Delete': {
                        'TableName': self.reviews_table_name,
                        'Key': {'user_id': {'S': user_id}, 'card_id': {'S': card_id}}
                    }
                },
                {  # Index 2: Decrement card_count with lower bound check
                    'Update': {
                        'TableName': self.users_table_name,
                        'Key': {'user_id': {'S': user_id}},
                        'UpdateExpression': 'SET card_count = card_count - :dec',
                        'ConditionExpression': 'card_count > :zero',
                        'ExpressionAttributeValues': {
                            ':dec': {'N': '1'},
                            ':zero': {'N': '0'}
                        }
                    }
                }
            ]
        )
    except ClientError as e:
        # Error handling (see EARS-012, EARS-013)
```

#### EARS-011: reviews_table_name Initialization

**Type**: Ubiquitous

> The system shall accept and store a `reviews_table_name` parameter in the `CardService.__init__` method, defaulting to the `REVIEWS_TABLE` environment variable or `'memoru-reviews-dev'`.

**Reliability**: 🔵 *Derived from EARS-010: The transactional delete requires access to the Reviews table name*

**Code Location**: `backend/src/services/card_service.py` lines 37-58 (`__init__` method)

**Current __init__ Parameters**:
```python
def __init__(self, table_name=None, dynamodb_resource=None, users_table_name=None):
```

**Expected __init__ Parameters**:
```python
def __init__(self, table_name=None, dynamodb_resource=None, users_table_name=None, reviews_table_name=None):
```

**New Attribute**:
```python
self.reviews_table_name = reviews_table_name or os.environ.get("REVIEWS_TABLE", "memoru-reviews-dev")
```

#### EARS-012: Delete Card Not Found via Transaction

**Type**: Event-driven

> When a `TransactionCanceledException` occurs during card deletion and `CancellationReasons[0].Code` equals `'ConditionalCheckFailed'`, the system shall raise `CardNotFoundError` because the card no longer exists (race condition with another delete).

**Reliability**: 🔵 *CR-02: The card delete uses `ConditionExpression: 'attribute_exists(card_id)'` at TransactItems index 0*

#### EARS-013: card_count Already Zero on Delete

**Type**: Event-driven

> When a `TransactionCanceledException` occurs during card deletion and `CancellationReasons[2].Code` equals `'ConditionalCheckFailed'`, the system shall raise `CardServiceError` indicating card_count is already at 0.

**Reliability**: 🟡 *CR-02: This is a data integrity edge case where card_count has drifted out of sync with actual card count. The condition `card_count > :zero` at TransactItems index 2 prevents negative values.*

#### EARS-014: card_count Lower Bound Protection

**Type**: Ubiquitous

> The system shall include `ConditionExpression: 'card_count > :zero'` in the Users table Update within the delete transaction to prevent card_count from going negative.

**Reliability**: 🔵 *CR-02: Defensive programming to prevent data integrity issues from cascading*

---

### 2.4 Fix 4: User Existence Guarantee (REQ-V2-014)

#### EARS-015: Pre-Create User on Card Creation

**Type**: Ubiquitous

> The system shall call `user_service.get_or_create_user(user_id)` before `card_service.create_card()` in the POST /cards handler.

**Reliability**: 🔵 *CR-02: handler.py L361 proceeds directly to card creation without ensuring user record exists. Combined with Fix 1 (if_not_exists), this provides a complete safety net.*

**Code Location**: `backend/src/api/handler.py` lines 361-368

**Current Code**:
```python
try:
    card = card_service.create_card(
        user_id=user_id,
        front=request.front,
        back=request.back,
        deck_id=request.deck_id,
        tags=request.tags,
    )
```

**Expected Code**:
```python
try:
    # Ensure user exists before card creation
    user_service.get_or_create_user(user_id)

    card = card_service.create_card(
        user_id=user_id,
        front=request.front,
        back=request.back,
        deck_id=request.deck_id,
        tags=request.tags,
    )
```

#### EARS-016: get_or_create_user Idempotency

**Type**: Ubiquitous

> The `get_or_create_user` method shall be idempotent: if the user already exists, it shall return the existing user without modification; if the user does not exist, it shall create a new user record.

**Reliability**: 🔵 *CR-02: Already implemented in user_service.py L116-132. Verification that card_count is properly initialized on creation.*

**Code Location**: `backend/src/services/user_service.py` lines 116-132

**Note**: The existing `get_or_create_user` implementation delegates to `create_user()` which calls `User()` constructor, then `to_dynamodb_item()`. The `User` model does NOT include `card_count` in `to_dynamodb_item()` (see `backend/src/models/user.py` L114-131). This means newly created users will NOT have a `card_count` attribute, making Fix 1 (`if_not_exists`) essential for correctness.

---

## 3. Acceptance Criteria

### 3.1 Fix 1: `if_not_exists` Safety

| AC-ID | Criterion | Test Case | Priority |
|-------|-----------|-----------|----------|
| AC-001 | Card creation succeeds when user record has no `card_count` attribute | TC-01 | P0 |
| AC-002 | After first card creation, `card_count` is set to 1 in the Users table | TC-01 | P0 |
| AC-003 | Card creation still succeeds when user already has `card_count` attribute | TC-09 (existing tests) | P0 |
| AC-004 | Card limit check still works correctly with `if_not_exists` | TC-02 | P0 |
| AC-005 | The `:zero` attribute value `{'N': '0'}` is included in ExpressionAttributeValues | Code inspection | P0 |

### 3.2 Fix 2: Error Classification

| AC-ID | Criterion | Test Case | Priority |
|-------|-----------|-----------|----------|
| AC-006 | `TransactionCanceledException` with `ConditionalCheckFailed` at index 0 raises `CardLimitExceededError` | TC-02 | P0 |
| AC-007 | `TransactionCanceledException` with non-`ConditionalCheckFailed` at index 0 raises `InternalError` | TC-03 | P0 |
| AC-008 | `TransactionCanceledException` with empty/missing `CancellationReasons` raises `InternalError` | TC-04 | P1 |
| AC-009 | `InternalError` exception class exists and inherits from `CardServiceError` | Code inspection | P0 |
| AC-010 | Non-limit transaction failures are logged at ERROR level | TC-03 | P1 |

### 3.3 Fix 3: Transactional Delete

| AC-ID | Criterion | Test Case | Priority |
|-------|-----------|-----------|----------|
| AC-011 | Deleting a card decrements `card_count` by 1 in the Users table | TC-05 | P0 |
| AC-012 | Card deletion and `card_count` decrement occur atomically (single transaction) | TC-05 | P0 |
| AC-013 | `card_count` cannot go below 0 during deletion | TC-06 | P1 |
| AC-014 | Review record is also deleted in the same transaction | Code inspection | P0 |
| AC-015 | `reviews_table_name` is configurable via constructor parameter and env var | Code inspection | P0 |
| AC-016 | Race condition with concurrent delete raises `CardNotFoundError` | TC-06 variant | P1 |

### 3.4 Fix 4: User Existence Guarantee

| AC-ID | Criterion | Test Case | Priority |
|-------|-----------|-----------|----------|
| AC-017 | `get_or_create_user` is called before `create_card` in POST /cards handler | TC-07, TC-08 | P0 |
| AC-018 | New user gets a record created before first card creation | TC-08 | P0 |
| AC-019 | Existing user is returned unchanged by `get_or_create_user` | TC-07 | P0 |
| AC-020 | `get_or_create_user` is idempotent (multiple calls produce same result) | TC-07 | P0 |

### 3.5 End-to-End Integrity

| AC-ID | Criterion | Test Case | Priority |
|-------|-----------|-----------|----------|
| AC-021 | Creating N cards results in `card_count = N` | TC-09 | P0 |
| AC-022 | Creating N cards then deleting M cards results in `card_count = N - M` | TC-09 | P0 |
| AC-023 | Full cycle: create 3 cards, delete 2, verify `card_count = 1` | TC-09 | P0 |

---

## 4. Test Cases

### TC-01: Card Creation with Missing card_count Attribute

**Reliability**: 🔵

**Description**: Verify that card creation succeeds when the user record exists but lacks the `card_count` attribute, and that `card_count` is initialized to 1 after creation.

**Preconditions**:
- User record exists in Users table with `user_id` and `created_at` only
- No `card_count` attribute on the user record

**Test Steps**:
1. Set up user record without `card_count` attribute
2. Call `card_service.create_card(user_id, front="Q1", back="A1")`
3. Verify card is created successfully (card_id is not None)
4. Query Users table and verify `card_count == 1`

**Expected Result**:
- Card is created with a valid `card_id`
- User record now has `card_count = 1`

**Maps to**: AC-001, AC-002, EARS-001, EARS-002, EARS-003, EARS-004

---

### TC-02: ConditionalCheckFailed Raises CardLimitExceededError

**Reliability**: 🔵

**Description**: Verify that when `TransactionCanceledException` includes `CancellationReasons[0].Code == 'ConditionalCheckFailed'`, it correctly raises `CardLimitExceededError`.

**Preconditions**:
- Mock `transact_write_items` to raise `ClientError` with:
  - `Error.Code = 'TransactionCanceledException'`
  - `CancellationReasons = [{"Code": "ConditionalCheckFailed", "Message": "..."}]`

**Test Steps**:
1. Configure mock to simulate limit exceeded
2. Call `card_service.create_card(user_id, front="Q", back="A")`
3. Assert `CardLimitExceededError` is raised

**Expected Result**:
- `CardLimitExceededError` is raised (not `InternalError` or `CardServiceError`)

**Maps to**: AC-006, EARS-006

---

### TC-03: Non-ConditionalCheckFailed Raises InternalError

**Reliability**: 🔵

**Description**: Verify that when `TransactionCanceledException` includes a non-`ConditionalCheckFailed` code at index 0, it raises `InternalError` instead of `CardLimitExceededError`.

**Preconditions**:
- Mock `transact_write_items` to raise `ClientError` with:
  - `Error.Code = 'TransactionCanceledException'`
  - `CancellationReasons = [{"Code": "ValidationError", "Message": "..."}]`

**Test Steps**:
1. Configure mock to simulate non-limit transaction failure
2. Call `card_service.create_card(user_id, front="Q", back="A")`
3. Assert `InternalError` is raised (not `CardLimitExceededError`)

**Expected Result**:
- `InternalError` is raised
- Error is distinguishable from `CardLimitExceededError`

**Maps to**: AC-007, AC-010, EARS-007, EARS-009

---

### TC-04: Missing CancellationReasons Raises InternalError

**Reliability**: 🟡

**Description**: Verify that when `TransactionCanceledException` has no `CancellationReasons` key or an empty array, the system raises `InternalError`.

**Preconditions**:
- Mock `transact_write_items` to raise `ClientError` with:
  - `Error.Code = 'TransactionCanceledException'`
  - No `CancellationReasons` key in the response

**Test Steps**:
1. Configure mock with missing `CancellationReasons`
2. Call `card_service.create_card(user_id, front="Q", back="A")`
3. Assert `InternalError` is raised

**Expected Result**:
- `InternalError` is raised (not `CardLimitExceededError` or unhandled exception)

**Edge Case Variants**:
- **TC-04a**: `CancellationReasons` key absent entirely
- **TC-04b**: `CancellationReasons` is an empty list `[]`

**Maps to**: AC-008, EARS-008

---

### TC-05: delete_card Decrements card_count

**Reliability**: 🔵

**Description**: Verify that deleting a card atomically decrements card_count in the Users table.

**Preconditions**:
- User record exists with `card_count = 5`
- At least one card exists for the user

**Test Steps**:
1. Set up user with `card_count = 5`
2. Create a card (card_count becomes 6)
3. Delete the created card
4. Query Users table and verify `card_count == 5` (6 - 1 = 5)

**Expected Result**:
- Card is deleted from Cards table
- User's `card_count` is decremented by 1

**Maps to**: AC-011, AC-012, EARS-010

---

### TC-06: card_count = 0 Delete Prevention

**Reliability**: 🟡

**Description**: Verify that card_count cannot go negative when a delete is attempted and card_count is already 0.

**Preconditions**:
- Mock `transact_write_items` to raise `ClientError` with:
  - `Error.Code = 'TransactionCanceledException'`
  - `CancellationReasons` with `ConditionalCheckFailed` at index 2 (Users table Update)
- Mock `get_card` to succeed (card exists)

**Test Steps**:
1. Configure mock to simulate card_count = 0 condition failure
2. Call `card_service.delete_card(user_id, card_id)`
3. Assert `CardServiceError` is raised with message containing "card_count"

**Expected Result**:
- `CardServiceError` is raised
- card_count remains at 0 (not -1)

**Edge Case Variants**:
- **TC-06a**: `CancellationReasons[0].Code == 'ConditionalCheckFailed'` (card already deleted by another request) - should raise `CardNotFoundError`
- **TC-06b**: `CancellationReasons[2].Code == 'ConditionalCheckFailed'` (card_count at 0) - should raise `CardServiceError`

**Maps to**: AC-013, AC-016, EARS-012, EARS-013, EARS-014

---

### TC-07: get_or_create_user Returns Existing User

**Reliability**: 🔵

**Description**: Verify that `get_or_create_user` returns an existing user without modification.

**Preconditions**:
- User record exists with `user_id`, `card_count = 5`, and other attributes

**Test Steps**:
1. Create user record in Users table with known attributes
2. Call `user_service.get_or_create_user(user_id)`
3. Verify returned user matches existing record
4. Verify `card_count` is unchanged

**Expected Result**:
- Existing user is returned
- No attributes are modified

**Maps to**: AC-019, AC-020, EARS-016

---

### TC-08: get_or_create_user Creates New User

**Reliability**: 🔵

**Description**: Verify that `get_or_create_user` creates a new user when one does not exist.

**Preconditions**:
- No user record exists for the given `user_id`

**Test Steps**:
1. Call `user_service.get_or_create_user("new-user-id")`
2. Verify user is created
3. Query Users table to verify record exists

**Expected Result**:
- New user record is created
- User has expected default values

**Note**: The User model's `to_dynamodb_item()` does NOT include `card_count` (verified in `backend/src/models/user.py` L114-131). This means newly created users will lack `card_count`, making Fix 1 (`if_not_exists`) essential.

**Maps to**: AC-017, AC-018, EARS-015, EARS-016

---

### TC-09: End-to-End card_count Consistency

**Reliability**: 🔵

**Description**: Integration test verifying that create and delete operations maintain card_count consistency across the full lifecycle.

**Preconditions**:
- Clean user state (user record will be auto-created via mock)

**Test Steps**:
1. Create 3 cards for the same user
2. Verify `card_count == 3`
3. Delete the first card
4. Verify `card_count == 2`
5. Delete the second card
6. Verify `card_count == 1`

**Expected Result**:
- card_count accurately reflects the number of cards at each step

**Maps to**: AC-021, AC-022, AC-023

---

## 5. Edge Cases

### 5.1 card_count Attribute Missing (Fix 1)

| Edge Case | Description | Expected Behavior | Reliability |
|-----------|-------------|-------------------|-------------|
| EC-001 | User record exists with no `card_count` attribute at all | `if_not_exists` treats as 0; card creation succeeds; card_count set to 1 | 🔵 |
| EC-002 | User record exists with `card_count = 0` | Normal increment to 1 | 🔵 |
| EC-003 | User record exists with `card_count = 1999` | Normal increment to 2000 (just under limit) | 🔵 |
| EC-004 | User record exists with `card_count = 2000` | `ConditionalCheckFailed` raised; `CardLimitExceededError` | 🔵 |
| EC-005 | User record does not exist at all (no PK match) | DynamoDB creates item with card_count = 1 (upsert behavior of Update) | 🟡 |

### 5.2 CancellationReasons Parsing (Fix 2)

| Edge Case | Description | Expected Behavior | Reliability |
|-----------|-------------|-------------------|-------------|
| EC-006 | `CancellationReasons` key missing from error response | `InternalError` raised | 🟡 |
| EC-007 | `CancellationReasons` is empty list `[]` | `InternalError` raised (falsy check) | 🟡 |
| EC-008 | `CancellationReasons[0]` has no `Code` key | `InternalError` raised (`.get('Code')` returns None) | 🟡 |
| EC-009 | `CancellationReasons[0].Code == 'None'` (string "None") | `InternalError` raised (not equal to `'ConditionalCheckFailed'`) | 🟡 |
| EC-010 | Multiple items in `CancellationReasons` with mixed codes | Only index 0 is checked (Users table); `ConditionalCheckFailed` at index 0 means limit exceeded | 🔵 |
| EC-011 | `TransactionCanceledException` from non-transact operation | Should not reach this code path (only `transact_write_items` generates this) | 🔵 |

### 5.3 Delete Atomicity (Fix 3)

| Edge Case | Description | Expected Behavior | Reliability |
|-----------|-------------|-------------------|-------------|
| EC-012 | Card exists but no review record exists | Transaction succeeds (Delete without condition on Reviews table) | 🔵 |
| EC-013 | Card already deleted by concurrent request | `CancellationReasons[0].Code == 'ConditionalCheckFailed'`; raises `CardNotFoundError` | 🔵 |
| EC-014 | `card_count = 0` but card still exists (data drift) | `CancellationReasons[2].Code == 'ConditionalCheckFailed'`; raises `CardServiceError` | 🟡 |
| EC-015 | `card_count = 1` and deleting the last card | Normal decrement to 0; succeeds (condition is `> :zero`, i.e., `1 > 0` is true) | 🔵 |
| EC-016 | Non-TransactionCanceledException error during delete | Falls through to generic `CardServiceError` | 🔵 |

### 5.4 User Existence (Fix 4)

| Edge Case | Description | Expected Behavior | Reliability |
|-----------|-------------|-------------------|-------------|
| EC-017 | First-time user calls POST /cards | `get_or_create_user` creates user, then `create_card` succeeds with `if_not_exists` | 🔵 |
| EC-018 | Concurrent `get_or_create_user` calls for same user | `create_user` handles `ConditionalCheckFailedException` by returning existing user | 🔵 |
| EC-019 | `get_or_create_user` failure (DynamoDB error) | Exception propagates; card is NOT created (consistent state) | 🔵 |

---

## 6. Code Location Summary

### 6.1 Files to Modify

| File | Absolute Path | Changes |
|------|--------------|---------|
| card_service.py | `/Volumes/external/dev/memoru-liff/backend/src/services/card_service.py` | Add `InternalError` class; add `reviews_table_name` param; modify `create_card` UpdateExpression/ConditionExpression/error handling; rewrite `delete_card` with transaction |
| handler.py | `/Volumes/external/dev/memoru-liff/backend/src/api/handler.py` | Add `get_or_create_user(user_id)` call before `create_card` in POST /cards handler |
| test_card_service.py | `/Volumes/external/dev/memoru-liff/backend/tests/unit/test_card_service.py` | Add TC-01 through TC-09 test cases; update conftest mock for delete transaction |

### 6.2 Files NOT Modified (Verified Correct)

| File | Absolute Path | Reason |
|------|--------------|--------|
| user_service.py | `/Volumes/external/dev/memoru-liff/backend/src/services/user_service.py` | `get_or_create_user` already implemented correctly (L116-132) |
| user.py (model) | `/Volumes/external/dev/memoru-liff/backend/src/models/user.py` | No changes needed; `to_dynamodb_item()` not including `card_count` is acceptable because Fix 1 handles missing attribute |

### 6.3 Specific Line Changes

| File | Current Lines | Change Description |
|------|--------------|-------------------|
| `card_service.py` L26-29 | After `CardLimitExceededError` | Add `InternalError` class definition |
| `card_service.py` L37 | `__init__` signature | Add `reviews_table_name` parameter |
| `card_service.py` L46 | After `self.users_table_name` | Add `self.reviews_table_name` assignment |
| `card_service.py` L112 | `UpdateExpression` | Add `if_not_exists(card_count, :zero)` |
| `card_service.py` L113 | `ConditionExpression` | Add `if_not_exists(card_count, :zero)` |
| `card_service.py` L114-117 | `ExpressionAttributeValues` | Add `':zero': {'N': '0'}` |
| `card_service.py` L129-133 | Exception handler | Replace with CancellationReasons parsing logic |
| `card_service.py` L234-250 | `delete_card` method | Replace with transactional implementation |
| `handler.py` L361 | Before `card_service.create_card` | Add `user_service.get_or_create_user(user_id)` |

---

## 7. Transaction Index Reference

### 7.1 create_card TransactItems Order

| Index | Table | Operation | Purpose | Error Meaning |
|-------|-------|-----------|---------|---------------|
| 0 | Users | Update | Increment `card_count` with limit check | `ConditionalCheckFailed` = card limit exceeded |
| 1 | Cards | Put | Insert new card record | Conflict (unlikely with UUID key) |

### 7.2 delete_card TransactItems Order

| Index | Table | Operation | Purpose | Error Meaning |
|-------|-------|-----------|---------|---------------|
| 0 | Cards | Delete | Remove card with existence check | `ConditionalCheckFailed` = card already deleted |
| 1 | Reviews | Delete | Remove review (no condition) | N/A (unconditional) |
| 2 | Users | Update | Decrement `card_count` with `> 0` check | `ConditionalCheckFailed` = card_count already at 0 |

---

## 8. Reliability Level Summary

### By Requirement

| ID | Requirement | Level | Rationale |
|----|-------------|-------|-----------|
| EARS-001 | `if_not_exists` in UpdateExpression | 🔵 | Code analysis confirms bare `card_count + :inc` at L112 |
| EARS-002 | `if_not_exists` in ConditionExpression | 🔵 | Code analysis confirms bare `card_count < :limit` at L113 |
| EARS-003 | `:zero` attribute value | 🔵 | Derived from EARS-001/002 |
| EARS-004 | Missing card_count initialization | 🔵 | User model `to_dynamodb_item()` confirmed to not include card_count |
| EARS-005 | InternalError class | 🔵 | Needed for error distinction |
| EARS-006 | ConditionalCheckFailed classification | 🔵 | TransactItems[0] is the limit check operation |
| EARS-007 | Non-limit failure classification | 🔵 | Other error codes must not be reported as limit exceeded |
| EARS-008 | Missing CancellationReasons | 🟡 | Based on DynamoDB API documentation patterns |
| EARS-009 | Error logging | 🔵 | Required for operational visibility |
| EARS-010 | Transactional delete | 🔵 | Code analysis confirms non-transactional delete at L234-250 |
| EARS-011 | reviews_table_name initialization | 🔵 | Required by EARS-010 |
| EARS-012 | Delete card not found (race) | 🔵 | ConditionExpression at index 0 |
| EARS-013 | card_count = 0 on delete | 🟡 | Data drift edge case |
| EARS-014 | card_count lower bound | 🔵 | Defensive programming requirement |
| EARS-015 | Pre-create user | 🔵 | Code analysis confirms missing call at L361 |
| EARS-016 | get_or_create_user idempotency | 🔵 | Already implemented at user_service.py L116-132 |

### Summary Table

| Level | Count | Percentage |
|-------|-------|------------|
| 🔵 Blue (confirmed) | 14 | 87.5% |
| 🟡 Yellow (inferred) | 2 | 12.5% |
| 🔴 Red (speculative) | 0 | 0% |

**Quality Assessment**: High quality - 87.5% blue, no red items.

---

## 9. Dependencies and Constraints

### 9.1 Technical Dependencies

- `boto3` - Already present in requirements
- `botocore.exceptions.ClientError` - Already imported
- No new external package dependencies

### 9.2 DynamoDB Transaction Limits

- Max 25 items per `TransactWriteItems` call (we use max 3)
- Max 4MB total transaction size (our items are small)
- Items in a transaction must be in different items (no two operations on same PK+SK)

### 9.3 Testing Constraints

- **Moto limitations**: `moto` has known bugs with `transact_write_items`. The existing test fixture at `test_card_service.py` L78-162 uses a custom mock. This mock must be extended to handle:
  - Delete operations (currently only handles Update and Put)
  - The `reviews_table_name` reference
  - card_count decrement logic

### 9.4 Backward Compatibility

- `CardLimitExceededError` behavior unchanged for limit-exceeded cases
- New `InternalError` class for previously-misclassified errors (non-breaking)
- API response format unchanged
- `delete_card` method signature unchanged

---

## 10. Test File Structure

### Test Classes to Add in `backend/tests/unit/test_card_service.py`

```
class TestCardCountIfNotExists:
    """Tests for if_not_exists safety in card creation (Fix 1)."""
    - test_create_card_with_missing_card_count          (TC-01)

class TestTransactionErrorClassification:
    """Tests for TransactionCanceledException error classification (Fix 2)."""
    - test_conditional_check_failed_raises_limit_error  (TC-02)
    - test_non_conditional_raises_internal_error         (TC-03)
    - test_missing_cancellation_reasons_raises_internal  (TC-04a)
    - test_empty_cancellation_reasons_raises_internal    (TC-04b)

class TestDeleteCardTransaction:
    """Tests for transactional card deletion with card_count decrement (Fix 3)."""
    - test_delete_card_decrements_card_count            (TC-05)
    - test_delete_card_prevents_negative_count          (TC-06)
    - test_delete_card_race_condition_not_found          (TC-06a)

class TestCardCountEndToEnd:
    """Integration tests for card_count consistency (Fix 1+3+4)."""
    - test_create_delete_card_count_consistency          (TC-09)
```

### Test Classes to Add in `backend/tests/unit/test_user_service.py` (or existing file)

```
class TestGetOrCreateUser:
    """Tests for get_or_create_user (Fix 4)."""
    - test_get_or_create_user_existing                  (TC-07)
    - test_get_or_create_user_new                       (TC-08)
```

---

**Document Version**: 1.0
**Last Updated**: 2026-02-21
**Author**: Claude Code
