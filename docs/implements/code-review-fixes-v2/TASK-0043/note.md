# TASK-0043: card_count Transaction Fixes - Implementation Note

**Task ID**: TASK-0043
**Task Type**: TDD (Test-Driven Development)
**Status**: Ready for Implementation
**Created**: 2026-02-21
**Expected Work**: 8 hours

---

## Executive Summary

This task addresses 4 critical issues in DynamoDB card_count transaction management:

1. **if_not_exists Safety**: Safely handle card_count increment when attribute doesn't exist
2. **Error Classification**: Properly distinguish between CardLimitExceeded and other TransactionCanceledException failures
3. **Delete Atomicity**: Decrement card_count transactionally during card deletion
4. **User Existence**: Guarantee user record exists before card creation

All issues require transactional modifications to ensure data consistency and prevent race conditions.

---

## Current State Analysis

### Code Review Findings

**File: `/Volumes/external/dev/memoru-liff/backend/src/services/card_service.py`**

#### Issue 1: Unsafe card_count Increment (Lines 106-127)

**Current Code:**
```python
'UpdateExpression': 'SET card_count = card_count + :inc',
'ConditionExpression': 'card_count < :limit',
```

**Problem**:
- When user record lacks `card_count` attribute, the transaction fails
- New users don't have `card_count` until first creation attempt
- Results in CardServiceError instead of graceful card_count initialization

**Impact**: HIGH - Prevents first card creation for new users

#### Issue 2: Over-Simplified Error Classification (Lines 129-133)

**Current Code:**
```python
except ClientError as e:
    if e.response["Error"]["Code"] == "TransactionCanceledException":
        raise CardLimitExceededError(f"Card limit of {self.MAX_CARDS_PER_USER} exceeded")
    raise CardServiceError(f"Failed to create card: {e}")
```

**Problem**:
- Treats ALL TransactionCanceledException as CardLimitExceededError
- Doesn't inspect CancellationReasons array
- Masks other transaction failures (e.g., race conditions in Cards table)

**Impact**: MEDIUM - Incorrect error reporting, poor debugging visibility

#### Issue 3: Missing card_count Decrement (Lines 234-250)

**Current Code:**
```python
def delete_card(self, user_id: str, card_id: str) -> None:
    self.get_card(user_id, card_id)
    try:
        self.table.delete_item(Key={"user_id": user_id, "card_id": card_id})
    except ClientError as e:
        raise CardServiceError(f"Failed to delete card: {e}")
```

**Problem**:
- Deletes card without updating card_count
- card_count becomes out-of-sync with actual card count
- Can lead to user being blocked from creating cards

**Impact**: CRITICAL - Data integrity issue causing stuck users

#### Issue 4: No User Pre-Creation (handler.py Line 362)

**Current Code:**
```python
@app.post("/cards")
def create_card():
    user_id = get_user_id_from_context()
    try:
        card = card_service.create_card(
            user_id=user_id,
            front=request.front,
            back=request.back,
            ...
        )
```

**Problem**:
- Assumes user record exists when create_card is called
- Combines with Issue 1: no safe initialization path

**Impact**: MEDIUM - Dependency ordering issue

---

## DynamoDB Transaction Context

### TransactWriteItems Structure

For card creation, the transaction must:
1. Update Users table: Increment card_count with condition check
2. Put Cards table: Insert new card item

**TransactItems Order** (used for error identification):
- Index 0: Users table Update (card_count check)
- Index 1: Cards table Put

### CancellationReasons Structure

When TransactionCanceledException occurs, the response includes:
```python
'CancellationReasons': [
    {
        'Code': 'ConditionalCheckFailed' | 'ValidationError' | 'DuplicateTransactionError' | 'IdempotentParameterMismatchError' | 'TransactionConflict',
        'Message': '...',
        'Item': {...}  # Optional
    },
    ...
]
```

- **Index 0 ConditionalCheckFailed**: card_count >= 2000 (expected for limit)
- **Index 0 ValidationError**: Malformed expression
- **Other indices with failures**: Validation or conflict in Cards/Reviews tables

---

## Implementation Roadmap

### Phase 1: Exception Hierarchy Enhancement

**Goal**: Create clearer error classification system

**Tasks**:
1. Define `InternalError` exception in card_service.py
   - For non-limit TransactionCanceledException
   - Provides clearer error semantics than generic CardServiceError

### Phase 2: Fix Issue 1 - if_not_exists Safety

**File**: `backend/src/services/card_service.py`

**Lines**: 106-127 (create_card method)

**Changes**:
```python
'UpdateExpression': 'SET card_count = if_not_exists(card_count, :zero) + :inc',
'ConditionExpression': 'if_not_exists(card_count, :zero) < :limit',
'ExpressionAttributeValues': {
    ':inc': {'N': '1'},
    ':limit': {'N': str(self.MAX_CARDS_PER_USER)},
    ':zero': {'N': '0'}
}
```

**Rationale**:
- `if_not_exists(card_count, :zero)` returns 0 if attribute missing
- Allows safe increment even when attribute doesn't exist
- Condition still protects limit

### Phase 3: Fix Issue 2 - Error Classification

**File**: `backend/src/services/card_service.py`

**Lines**: 129-133 (exception handling in create_card)

**Changes**:
```python
except ClientError as e:
    if e.response["Error"]["Code"] == "TransactionCanceledException":
        reasons = e.response.get("CancellationReasons", [])

        # Index 0 = Users table Update (where card_count condition is checked)
        if reasons and reasons[0].get("Code") == "ConditionalCheckFailed":
            raise CardLimitExceededError(f"Card limit of {self.MAX_CARDS_PER_USER} exceeded")

        # Other transaction failures are internal errors
        logger.error(f"Transaction failed: {reasons}")
        raise InternalError("Card creation failed due to transaction conflict")

    raise CardServiceError(f"Failed to create card: {e}")
```

**Key Points**:
- Inspects CancellationReasons array
- Uses Index 0 to identify limit vs other failures
- Logs detailed error for debugging
- Creates appropriate exception type

### Phase 4: Fix Issue 3 - Transactional Delete

**File**: `backend/src/services/card_service.py`

**Lines**: 234-250 (delete_card method)

**Changes**:
```python
def delete_card(self, user_id: str, card_id: str) -> None:
    """Delete a card with transactional card_count decrement."""
    # Verify card exists
    self.get_card(user_id, card_id)

    try:
        client = self.dynamodb.meta.client

        # Use transaction to atomically delete card and decrement card_count
        client.transact_write_items(
            TransactItems=[
                {
                    'Delete': {
                        'TableName': self.table_name,
                        'Key': {
                            'user_id': {'S': user_id},
                            'card_id': {'S': card_id}
                        },
                        'ConditionExpression': 'attribute_exists(card_id)'
                    }
                },
                {
                    'Delete': {
                        'TableName': self.reviews_table_name,
                        'Key': {
                            'user_id': {'S': user_id},
                            'card_id': {'S': card_id}
                        }
                    }
                },
                {
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
        if e.response["Error"]["Code"] == "TransactionCanceledException":
            reasons = e.response.get("CancellationReasons", [])
            # Card doesn't exist (Index 0)
            if reasons and reasons[0].get("Code") == "ConditionalCheckFailed":
                raise CardNotFoundError(f"Card not found: {card_id}")
            # User card_count at 0 (Index 2)
            if len(reasons) > 2 and reasons[2].get("Code") == "ConditionalCheckFailed":
                raise CardServiceError("Cannot delete card: card_count already at 0")
        raise CardServiceError(f"Failed to delete card: {e}")
```

**New Dependencies**:
- Need `reviews_table_name` attribute
- Must initialize in `__init__`

**Key Points**:
- Delete Cards item with existence check (Index 0)
- Delete Reviews item without condition (Index 1)
- Decrement card_count with lower bound check (Index 2)
- Protects against card_count going negative

### Phase 5: Fix Issue 4 - Ensure User Exists

**File**: `backend/src/api/handler.py`

**Lines**: 337-383 (create_card endpoint)

**Changes**:
```python
@app.post("/cards")
@tracer.capture_method
def create_card():
    """Create a new card."""
    user_id = get_user_id_from_context()
    logger.info(f"Creating card for user_id: {user_id}")

    try:
        body = app.current_event.json_body
        request = CreateCardRequest(**body)
    except ValidationError as e:
        logger.warning(f"Validation error: {e}")
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "Invalid request", "details": e.errors()}),
        )
    except json.JSONDecodeError:
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "Invalid JSON body"}),
        )

    try:
        # Ensure user exists before card creation
        user_service.get_or_create_user(user_id)

        # Create card
        card = card_service.create_card(
            user_id=user_id,
            front=request.front,
            back=request.back,
            deck_id=request.deck_id,
            tags=request.tags,
        )
        return Response(
            status_code=201,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps(card.to_response().model_dump(mode="json")),
        )
    except CardLimitExceededError:
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "Card limit exceeded. Maximum 2000 cards per user."}),
        )
    except Exception as e:
        logger.error(f"Error creating card: {e}")
        raise
```

**Key Change**: Add `user_service.get_or_create_user(user_id)` before card creation

**Verification**:
- `/users/me` endpoint already does this (line 97)
- Ensures consistency across endpoints

---

## TDD Implementation Strategy

### Red Phase (Test First)

**Test File**: `backend/tests/unit/test_card_service.py`

**Tests to Implement** (in order of complexity):

#### TC1: if_not_exists with Missing card_count (Foundational)
```python
def test_create_card_with_missing_card_count(card_service, dynamodb_table):
    """Test card creation when user record lacks card_count attribute."""
    # Setup: User exists but card_count attribute is missing
    users_table = dynamodb_table.Table("memoru-users-test")
    users_table.put_item(Item={
        "user_id": "test-user-id",
        "created_at": datetime.now(timezone.utc).isoformat(),
        # Note: NO card_count attribute
    })

    # Should create card successfully and initialize card_count to 1
    card = card_service.create_card(
        user_id="test-user-id",
        front="Q1",
        back="A1",
    )

    assert card.card_id is not None
    # Verify card_count was initialized to 1
    user = users_table.get_item(Key={"user_id": "test-user-id"})["Item"]
    assert user["card_count"] == 1
```

#### TC2: TransactionCanceledException with ConditionalCheckFailed
```python
def test_create_card_limit_exceeded_classification(card_service, monkeypatch):
    """Test that ConditionalCheckFailed in CancellationReasons raises CardLimitExceededError."""
    original_client = card_service.dynamodb.meta.client

    def mock_transact(*args, **kwargs):
        raise ClientError(
            {
                "Error": {"Code": "TransactionCanceledException"},
                "CancellationReasons": [
                    {"Code": "ConditionalCheckFailed", "Message": "..."}
                ],
            },
            "TransactWriteItems",
        )

    monkeypatch.setattr(original_client, "transact_write_items", mock_transact)

    with pytest.raises(CardLimitExceededError):
        card_service.create_card(user_id="uid", front="Q", back="A")
```

#### TC3: TransactionCanceledException with Other Error
```python
def test_create_card_transaction_internal_error(card_service, monkeypatch):
    """Test that non-ConditionalCheckFailed TransactionCanceledException raises InternalError."""
    original_client = card_service.dynamodb.meta.client

    def mock_transact(*args, **kwargs):
        raise ClientError(
            {
                "Error": {"Code": "TransactionCanceledException"},
                "CancellationReasons": [
                    {"Code": "ValidationError", "Message": "..."}
                ],
            },
            "TransactWriteItems",
        )

    monkeypatch.setattr(original_client, "transact_write_items", mock_transact)

    with pytest.raises(InternalError):
        card_service.create_card(user_id="uid", front="Q", back="A")
```

#### TC4: TransactionCanceledException without CancellationReasons
```python
def test_create_card_transaction_no_reasons(card_service, monkeypatch):
    """Test handling TransactionCanceledException with missing CancellationReasons."""
    original_client = card_service.dynamodb.meta.client

    def mock_transact(*args, **kwargs):
        raise ClientError(
            {"Error": {"Code": "TransactionCanceledException"}},
            "TransactWriteItems",
        )

    monkeypatch.setattr(original_client, "transact_write_items", mock_transact)

    with pytest.raises(InternalError):
        card_service.create_card(user_id="uid", front="Q", back="A")
```

#### TC5: delete_card Decrements card_count
```python
def test_delete_card_decrements_card_count(card_service, dynamodb_table):
    """Test that deleting a card decrements card_count transactionally."""
    users_table = dynamodb_table.Table("memoru-users-test")

    # Setup: User with 5 cards
    users_table.put_item(Item={
        "user_id": "test-user-id",
        "card_count": 5,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    # Create and delete a card
    card = card_service.create_card(
        user_id="test-user-id",
        front="Q",
        back="A",
    )

    card_service.delete_card("test-user-id", card.card_id)

    # card_count should be 5 (5 from setup, +1 from create, -1 from delete)
    user = users_table.get_item(Key={"user_id": "test-user-id"})["Item"]
    assert user["card_count"] == 5
```

#### TC6: delete_card Prevents Negative card_count
```python
def test_delete_card_prevents_negative_count(card_service, dynamodb_table, monkeypatch):
    """Test that card_count cannot go negative during delete."""
    users_table = dynamodb_table.Table("memoru-users-test")

    users_table.put_item(Item={
        "user_id": "test-user-id",
        "card_count": 0,  # Already at 0
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    # Mock to simulate card existing but user at 0
    original_client = card_service.dynamodb.meta.client

    def mock_transact(*args, **kwargs):
        # Check if this is delete attempt with card_count at 0
        raise ClientError(
            {
                "Error": {"Code": "TransactionCanceledException"},
                "CancellationReasons": [
                    {"Code": "None"},  # Card delete succeeds
                    {"Code": "None"},  # Review delete succeeds
                    {"Code": "ConditionalCheckFailed"},  # Count decrement fails
                ],
            },
            "TransactWriteItems",
        )

    monkeypatch.setattr(original_client, "transact_write_items", mock_transact)

    with pytest.raises(CardServiceError) as exc_info:
        card_service.delete_card("test-user-id", "card-123")

    assert "card_count" in str(exc_info.value).lower()
```

#### TC7: get_or_create_user Returns Existing
```python
def test_get_or_create_user_existing(user_service, dynamodb_table):
    """Test get_or_create_user returns existing user unchanged."""
    users_table = dynamodb_table.Table("memoru-users-test")

    now = datetime.now(timezone.utc)
    users_table.put_item(Item={
        "user_id": "test-user-id",
        "created_at": now.isoformat(),
        "card_count": 5,
    })

    user = user_service.get_or_create_user("test-user-id")

    assert user.user_id == "test-user-id"
    assert user.card_count == 5
```

#### TC8: get_or_create_user Creates New with card_count = 0
```python
def test_get_or_create_user_new(user_service, dynamodb_table):
    """Test get_or_create_user creates new user with card_count = 0."""
    user = user_service.get_or_create_user("new-user-id")

    assert user.user_id == "new-user-id"
    assert user.card_count == 0

    # Verify in database
    users_table = dynamodb_table.Table("memoru-users-test")
    stored = users_table.get_item(Key={"user_id": "new-user-id"})["Item"]
    assert stored["card_count"] == 0
```

#### TC9: End-to-End Card Creation → Deletion
```python
def test_card_create_delete_e2e(card_service, dynamodb_table):
    """Integration test: create and delete card maintains card_count consistency."""
    users_table = dynamodb_table.Table("memoru-users-test")

    # Create 3 cards
    cards = []
    for i in range(3):
        card = card_service.create_card(
            user_id="test-user-id",
            front=f"Q{i}",
            back=f"A{i}",
        )
        cards.append(card)

    user = users_table.get_item(Key={"user_id": "test-user-id"})["Item"]
    assert user["card_count"] == 3

    # Delete one card
    card_service.delete_card("test-user-id", cards[0].card_id)

    user = users_table.get_item(Key={"user_id": "test-user-id"})["Item"]
    assert user["card_count"] == 2

    # Delete another
    card_service.delete_card("test-user-id", cards[1].card_id)

    user = users_table.get_item(Key={"user_id": "test-user-id"})["Item"]
    assert user["card_count"] == 1
```

### Green Phase (Minimal Implementation)

1. Add `InternalError` exception class to card_service.py
2. Add `reviews_table_name` parameter to CardService.__init__
3. Update create_card() to use if_not_exists
4. Update create_card() error handling for CancellationReasons
5. Implement new delete_card() with transaction
6. Update handler.py create_card() endpoint to call get_or_create_user

### Refactor Phase

- Extract transaction building logic to helper methods
- Improve error logging with structured information
- Add docstring updates reflecting transaction semantics
- Verify mock transaction handling in conftest.py

---

## File Modifications Required

### New/Modified Files

| File | Type | Changes |
|------|------|---------|
| `backend/src/services/card_service.py` | Modified | Add InternalError, modify create_card, implement transactional delete_card |
| `backend/src/api/handler.py` | Modified | Add get_or_create_user call in create_card endpoint |
| `backend/tests/unit/test_card_service.py` | Modified | Add 9 comprehensive test cases |

### Dependencies

- `boto3` (already present)
- `botocore.exceptions.ClientError` (already present)
- No new external dependencies

---

## Technical Considerations

### DynamoDB Limits

- TransactWriteItems: Max 25 items per transaction
- We use ≤ 3 items per transaction ✓
- Max 4MB per transaction ✓

### Error Handling

- CancellationReasons is optional in error response
- Code always uses `.get()` with fallback
- Logging added for debugging

### Backward Compatibility

- Error types: CardLimitExceededError remains unchanged
- New InternalError for better classification (non-breaking)
- API responses unchanged from user perspective

### Testing Considerations

- Mock transact_write_items properly handles if_not_exists
- CancellationReasons must be in mock response for proper testing
- Need to verify transaction atomicity assumptions hold

---

## Success Criteria

### Phase Completion

- All 9 test cases pass (RED → GREEN → REFACTOR cycle)
- Code coverage ≥ 80% for modified methods
- No regression in existing tests

### Functional Verification

1. New user can create first card (tests TC1, TC7, TC9)
2. Card limit properly enforced with correct error (tests TC2, TC3)
3. Delete card decrements count atomically (tests TC5, TC6, TC9)
4. Error classification working correctly (tests TC2, TC3, TC4)
5. get_or_create_user idempotent (tests TC7, TC8)

### Code Quality

- Type hints on all new methods
- Docstrings updated for transaction behavior
- Logging structured and actionable
- No code duplication

---

## Risk Assessment

### High Risk Areas

1. **Mock transaction behavior** - Moto's transact_write_items has known bugs
   - Mitigation: Custom mock in conftest.py fixture

2. **Race condition in delete** - Multiple deletes same card
   - Mitigation: ConditionExpression on delete prevents double-deletion

3. **Negative card_count edge case** - Manual adjustments in production
   - Mitigation: Condition check prevents further decrements at 0

### Mitigation Strategies

- Integration tests with real DynamoDB (optional, for staging env)
- Monitoring card_count anomalies in production
- Gradual rollout with canary deployment

---

## Next Steps

1. Execute `/tsumiki:tdd-red` - Create failing tests
2. Implement changes to make tests pass
3. Execute `/tsumiki:tdd-green` - Verify all tests pass
4. Execute `/tsumiki:tdd-refactor` - Code cleanup and optimization
5. Update TASK-0043.md completion checkboxes
6. Create commit with all changes

---

## References

### DynamoDB Documentation
- [TransactWriteItems API](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/transaction-apis.html)
- [CancellationReasons Structure](https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_TransactWriteItems.html)

### Project Files
- Backend: `/Volumes/external/dev/memoru-liff/backend/src/services/`
- Tests: `/Volumes/external/dev/memoru-liff/backend/tests/unit/`
- Handler: `/Volumes/external/dev/memoru-liff/backend/src/api/handler.py`

### Related Tasks
- TASK-0035: Race condition prevention (context)
- TASK-0042: Code review findings (parent)

---

**Document Version**: 1.0
**Last Updated**: 2026-02-21
**Author**: Claude Code
