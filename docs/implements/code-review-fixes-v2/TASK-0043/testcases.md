# TASK-0043: card_count Transaction Fixes - Test Cases

**Task ID**: TASK-0043
**Task Type**: TDD (Test-Driven Development)
**Created**: 2026-02-21
**Test File (card)**: `backend/tests/unit/test_card_service.py`
**Test File (user)**: `backend/tests/unit/test_user_service.py`

---

## Test Case Summary

| ID | Test Case | Class | Fix | Priority | Reliability |
|----|-----------|-------|-----|----------|-------------|
| TC-01 | Card creation with missing card_count attribute | TestCardCountIfNotExists | Fix 1 | P0 | Blue |
| TC-02 | ConditionalCheckFailed raises CardLimitExceededError | TestTransactionErrorClassification | Fix 2 | P0 | Blue |
| TC-03 | Non-ConditionalCheckFailed raises InternalError | TestTransactionErrorClassification | Fix 2 | P0 | Blue |
| TC-04a | Missing CancellationReasons key raises InternalError | TestTransactionErrorClassification | Fix 2 | P1 | Yellow |
| TC-04b | Empty CancellationReasons list raises InternalError | TestTransactionErrorClassification | Fix 2 | P1 | Yellow |
| TC-05 | delete_card decrements card_count | TestDeleteCardTransaction | Fix 3 | P0 | Blue |
| TC-06a | delete_card race condition raises CardNotFoundError | TestDeleteCardTransaction | Fix 3 | P1 | Blue |
| TC-06b | delete_card prevents negative card_count | TestDeleteCardTransaction | Fix 3 | P1 | Yellow |
| TC-07 | get_or_create_user returns existing user | TestGetOrCreateUser | Fix 4 | P0 | Blue |
| TC-08 | get_or_create_user creates new user | TestGetOrCreateUser | Fix 4 | P0 | Blue |
| TC-09 | End-to-end create/delete card_count consistency | TestCardCountEndToEnd | Fix 1+3 | P0 | Blue |

---

## Test Infrastructure

### Existing Fixtures (reused)

The existing test infrastructure in `backend/tests/unit/test_card_service.py` already provides:

- `dynamodb_table` fixture: Creates mock DynamoDB tables (cards + users) via moto
- `card_service` fixture: Creates CardService instance with mock transact_write_items

The existing `card_service` fixture's `mock_transact_write_items` must be **extended** to handle:
1. `Delete` operations (currently only handles `Update` and `Put`)
2. The `reviews_table_name` reference (new parameter)
3. card_count decrement logic in the Update operation

### New Fixture Requirements

#### Reviews Table in `dynamodb_table`

The `dynamodb_table` fixture needs to also create a `memoru-reviews-test` table:

```python
# Add to dynamodb_table fixture, after users_table creation:
reviews_table = dynamodb.create_table(
    TableName="memoru-reviews-test",
    KeySchema=[
        {"AttributeName": "user_id", "KeyType": "HASH"},
        {"AttributeName": "card_id", "KeyType": "RANGE"},
    ],
    AttributeDefinitions=[
        {"AttributeName": "user_id", "AttributeType": "S"},
        {"AttributeName": "card_id", "AttributeType": "S"},
    ],
    BillingMode="PAY_PER_REQUEST",
)
reviews_table.wait_until_exists()
```

#### Updated `card_service` Fixture

The `card_service` fixture must pass `reviews_table_name`:

```python
@pytest.fixture
def card_service(dynamodb_table):
    service = CardService(
        table_name="memoru-cards-test",
        users_table_name="memoru-users-test",
        reviews_table_name="memoru-reviews-test",  # NEW
        dynamodb_resource=dynamodb_table,
    )
    # ... mock_transact_write_items updated for Delete operations ...
```

#### Extended `mock_transact_write_items`

The mock must handle `Delete` operations for delete_card transactions:

```python
def mock_transact_write_items(TransactItems, **kwargs):
    from boto3.dynamodb.types import TypeDeserializer
    from botocore.exceptions import ClientError

    deserializer = TypeDeserializer()
    reviews_table = dynamodb_table.Table("memoru-reviews-test")

    for item in TransactItems:
        if 'Update' in item:
            # ... existing Update logic (unchanged) ...
            pass

        elif 'Put' in item:
            # ... existing Put logic (unchanged) ...
            pass

        elif 'Delete' in item:
            delete = item['Delete']
            table_name = delete['TableName']
            if 'cards' in table_name:
                table = cards_table
            elif 'reviews' in table_name:
                table = reviews_table
            else:
                table = users_table

            key_dict = {k: deserializer.deserialize(v) for k, v in delete['Key'].items()}

            # Check ConditionExpression if present
            if 'ConditionExpression' in delete:
                response = table.get_item(Key=key_dict)
                if 'Item' not in response:
                    raise ClientError(
                        {
                            "Error": {
                                "Code": "TransactionCanceledException",
                                "Message": "Transaction cancelled",
                            },
                            "CancellationReasons": [
                                {"Code": "ConditionalCheckFailed"}
                            ],
                        },
                        "TransactWriteItems",
                    )

            # Perform delete
            table.delete_item(Key=key_dict)

    return {}
```

---

## Test Class 1: TestCardCountIfNotExists

**File**: `backend/tests/unit/test_card_service.py`
**Fix**: Fix 1 - `if_not_exists` safety for card_count increment
**Maps to**: EARS-001, EARS-002, EARS-003, EARS-004
**Acceptance Criteria**: AC-001, AC-002

### TC-01: Card Creation with Missing card_count Attribute

**Description**: Verify that card creation succeeds when the user record exists but lacks the `card_count` attribute. The `if_not_exists(card_count, :zero)` expression should treat the missing attribute as 0 and set card_count to 1 after creation.

**Preconditions**:
- User record exists in Users table with `user_id` and `created_at` only
- **No** `card_count` attribute on the user record

**Expected Result**:
- Card is created with a valid `card_id`
- User record now has `card_count = 1`

```python
class TestCardCountIfNotExists:
    """Tests for if_not_exists safety in card creation (Fix 1)."""

    def test_create_card_with_missing_card_count(self, card_service, dynamodb_table):
        """TC-01: Card creation succeeds when user record lacks card_count attribute.

        Given: A user record exists without card_count attribute
        When: A card is created for that user
        Then: The card is created successfully and card_count is initialized to 1

        Maps to: AC-001, AC-002, EARS-001, EARS-002, EARS-003, EARS-004
        Reliability: Blue
        """
        # Setup: User exists but card_count attribute is missing
        users_table = dynamodb_table.Table("memoru-users-test")
        users_table.put_item(
            Item={
                "user_id": "test-user-no-count",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "settings": {"notification_time": "09:00", "timezone": "Asia/Tokyo"},
                # Note: NO card_count attribute
            }
        )

        # Execute
        card = card_service.create_card(
            user_id="test-user-no-count",
            front="Question 1",
            back="Answer 1",
        )

        # Assert: Card created successfully
        assert card.card_id is not None
        assert card.user_id == "test-user-no-count"
        assert card.front == "Question 1"
        assert card.back == "Answer 1"

        # Assert: card_count was initialized to 1
        user = users_table.get_item(Key={"user_id": "test-user-no-count"})["Item"]
        assert user["card_count"] == 1
```

**Key Verification Points**:
- The mock `transact_write_items` must properly handle `if_not_exists` in the UpdateExpression
- The current mock already initializes `card_count = 0` when user has no `card_count`, which aligns with `if_not_exists` behavior
- After fix, the DynamoDB expression `if_not_exists(card_count, :zero) + :inc` will correctly handle the missing attribute

---

## Test Class 2: TestTransactionErrorClassification

**File**: `backend/tests/unit/test_card_service.py`
**Fix**: Fix 2 - Error classification of TransactionCanceledException
**Maps to**: EARS-005, EARS-006, EARS-007, EARS-008, EARS-009
**Acceptance Criteria**: AC-006, AC-007, AC-008, AC-009, AC-010

### TC-02: ConditionalCheckFailed Raises CardLimitExceededError

**Description**: Verify that when `TransactionCanceledException` includes `CancellationReasons[0].Code == 'ConditionalCheckFailed'`, the system correctly raises `CardLimitExceededError`.

**Preconditions**:
- Mock `transact_write_items` raises `ClientError` with `TransactionCanceledException` and `CancellationReasons[0].Code == 'ConditionalCheckFailed'`

**Expected Result**:
- `CardLimitExceededError` is raised (not `InternalError` or `CardServiceError`)

```python
class TestTransactionErrorClassification:
    """Tests for TransactionCanceledException error classification (Fix 2)."""

    def test_conditional_check_failed_raises_limit_error(self, card_service, monkeypatch):
        """TC-02: ConditionalCheckFailed at index 0 raises CardLimitExceededError.

        Given: transact_write_items raises TransactionCanceledException
               with CancellationReasons[0].Code == 'ConditionalCheckFailed'
        When: create_card is called
        Then: CardLimitExceededError is raised

        Maps to: AC-006, EARS-006
        Reliability: Blue
        """
        from botocore.exceptions import ClientError

        original_client = card_service.dynamodb.meta.client

        def mock_transact(*args, **kwargs):
            raise ClientError(
                {
                    "Error": {
                        "Code": "TransactionCanceledException",
                        "Message": "Transaction cancelled",
                    },
                    "CancellationReasons": [
                        {"Code": "ConditionalCheckFailed", "Message": "The conditional request failed"},
                    ],
                },
                "TransactWriteItems",
            )

        monkeypatch.setattr(original_client, "transact_write_items", mock_transact)

        with pytest.raises(CardLimitExceededError) as exc_info:
            card_service.create_card(
                user_id="test-user-id",
                front="Question",
                back="Answer",
            )

        assert "2000" in str(exc_info.value)
```

### TC-03: Non-ConditionalCheckFailed Raises InternalError

**Description**: Verify that when `TransactionCanceledException` includes a non-`ConditionalCheckFailed` code at index 0, it raises `InternalError` instead of `CardLimitExceededError`.

**Preconditions**:
- Mock `transact_write_items` raises `ClientError` with `TransactionCanceledException` and `CancellationReasons[0].Code == 'ValidationError'`

**Expected Result**:
- `InternalError` is raised
- `InternalError` is distinguishable from `CardLimitExceededError`

```python
    def test_non_conditional_raises_internal_error(self, card_service, monkeypatch):
        """TC-03: Non-ConditionalCheckFailed reason raises InternalError.

        Given: transact_write_items raises TransactionCanceledException
               with CancellationReasons[0].Code == 'ValidationError'
        When: create_card is called
        Then: InternalError is raised (not CardLimitExceededError)

        Maps to: AC-007, AC-010, EARS-007, EARS-009
        Reliability: Blue
        """
        from botocore.exceptions import ClientError
        from src.services.card_service import InternalError

        original_client = card_service.dynamodb.meta.client

        def mock_transact(*args, **kwargs):
            raise ClientError(
                {
                    "Error": {
                        "Code": "TransactionCanceledException",
                        "Message": "Transaction cancelled",
                    },
                    "CancellationReasons": [
                        {"Code": "ValidationError", "Message": "Validation error on expression"},
                    ],
                },
                "TransactWriteItems",
            )

        monkeypatch.setattr(original_client, "transact_write_items", mock_transact)

        with pytest.raises(InternalError):
            card_service.create_card(
                user_id="test-user-id",
                front="Question",
                back="Answer",
            )
```

### TC-04a: Missing CancellationReasons Key Raises InternalError

**Description**: Verify that when `TransactionCanceledException` has no `CancellationReasons` key in the response, the system raises `InternalError`.

**Preconditions**:
- Mock `transact_write_items` raises `ClientError` with `TransactionCanceledException` and **no** `CancellationReasons` key

**Expected Result**:
- `InternalError` is raised (not `CardLimitExceededError` or unhandled exception)

```python
    def test_missing_cancellation_reasons_raises_internal(self, card_service, monkeypatch):
        """TC-04a: Missing CancellationReasons key raises InternalError.

        Given: transact_write_items raises TransactionCanceledException
               without CancellationReasons key in the response
        When: create_card is called
        Then: InternalError is raised

        Maps to: AC-008, EARS-008
        Reliability: Yellow
        """
        from botocore.exceptions import ClientError
        from src.services.card_service import InternalError

        original_client = card_service.dynamodb.meta.client

        def mock_transact(*args, **kwargs):
            raise ClientError(
                {
                    "Error": {
                        "Code": "TransactionCanceledException",
                        "Message": "Transaction cancelled",
                    },
                    # Note: No CancellationReasons key at all
                },
                "TransactWriteItems",
            )

        monkeypatch.setattr(original_client, "transact_write_items", mock_transact)

        with pytest.raises(InternalError):
            card_service.create_card(
                user_id="test-user-id",
                front="Question",
                back="Answer",
            )
```

### TC-04b: Empty CancellationReasons List Raises InternalError

**Description**: Verify that when `TransactionCanceledException` has an empty `CancellationReasons` list, the system raises `InternalError`.

**Preconditions**:
- Mock `transact_write_items` raises `ClientError` with `TransactionCanceledException` and `CancellationReasons = []`

**Expected Result**:
- `InternalError` is raised (empty list is falsy, same branch as missing key)

```python
    def test_empty_cancellation_reasons_raises_internal(self, card_service, monkeypatch):
        """TC-04b: Empty CancellationReasons list raises InternalError.

        Given: transact_write_items raises TransactionCanceledException
               with CancellationReasons as an empty list
        When: create_card is called
        Then: InternalError is raised

        Maps to: AC-008, EARS-008
        Reliability: Yellow
        """
        from botocore.exceptions import ClientError
        from src.services.card_service import InternalError

        original_client = card_service.dynamodb.meta.client

        def mock_transact(*args, **kwargs):
            raise ClientError(
                {
                    "Error": {
                        "Code": "TransactionCanceledException",
                        "Message": "Transaction cancelled",
                    },
                    "CancellationReasons": [],  # Empty list
                },
                "TransactWriteItems",
            )

        monkeypatch.setattr(original_client, "transact_write_items", mock_transact)

        with pytest.raises(InternalError):
            card_service.create_card(
                user_id="test-user-id",
                front="Question",
                back="Answer",
            )
```

**Implementation Note for TC-04a/TC-04b**: The error classification code must use `reasons = e.response.get("CancellationReasons", [])` followed by `if reasons and reasons[0].get("Code") == "ConditionalCheckFailed"`. This handles both missing key (`.get()` returns `[]`) and empty list (falsy check fails, falls through to `InternalError`).

---

## Test Class 3: TestDeleteCardTransaction

**File**: `backend/tests/unit/test_card_service.py`
**Fix**: Fix 3 - Transactional delete with card_count decrement
**Maps to**: EARS-010, EARS-011, EARS-012, EARS-013, EARS-014
**Acceptance Criteria**: AC-011, AC-012, AC-013, AC-014, AC-015, AC-016

### TC-05: delete_card Decrements card_count

**Description**: Verify that deleting a card atomically decrements card_count in the Users table via transact_write_items.

**Preconditions**:
- User record exists with `card_count = 5`
- A card exists for the user

**Expected Result**:
- Card is deleted from Cards table
- User's `card_count` is decremented (5 -> 6 from create, 6 -> 5 from delete)

```python
class TestDeleteCardTransaction:
    """Tests for transactional card deletion with card_count decrement (Fix 3)."""

    def test_delete_card_decrements_card_count(self, card_service, dynamodb_table):
        """TC-05: Deleting a card decrements card_count transactionally.

        Given: User with card_count = 5 and at least one card
        When: A card is deleted
        Then: card_count is decremented by 1

        Maps to: AC-011, AC-012, EARS-010
        Reliability: Blue
        """
        users_table = dynamodb_table.Table("memoru-users-test")

        # Setup: User with card_count = 5
        users_table.put_item(
            Item={
                "user_id": "test-user-id",
                "card_count": 5,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "settings": {"notification_time": "09:00", "timezone": "Asia/Tokyo"},
            }
        )

        # Create a card (card_count becomes 6)
        card = card_service.create_card(
            user_id="test-user-id",
            front="Question",
            back="Answer",
        )

        # Verify card_count is 6
        user_before = users_table.get_item(Key={"user_id": "test-user-id"})["Item"]
        assert user_before["card_count"] == 6

        # Delete the card
        card_service.delete_card("test-user-id", card.card_id)

        # Assert: card_count should be 5 (6 - 1)
        user_after = users_table.get_item(Key={"user_id": "test-user-id"})["Item"]
        assert user_after["card_count"] == 5

        # Assert: card is deleted
        with pytest.raises(CardNotFoundError):
            card_service.get_card("test-user-id", card.card_id)
```

### TC-06a: Delete Race Condition Raises CardNotFoundError

**Description**: Verify that when a card has already been deleted by a concurrent request (TransactItems index 0 ConditionExpression fails), the system raises `CardNotFoundError`.

**Preconditions**:
- Mock `get_card` to succeed (card appears to exist at check time)
- Mock `transact_write_items` raises `ClientError` with `CancellationReasons[0].Code == 'ConditionalCheckFailed'`

**Expected Result**:
- `CardNotFoundError` is raised

```python
    def test_delete_card_race_condition_not_found(self, card_service, monkeypatch):
        """TC-06a: Race condition during delete raises CardNotFoundError.

        Given: A card exists at check time but is deleted before transaction
        When: delete_card is called
        Then: CardNotFoundError is raised due to ConditionExpression failure at index 0

        Maps to: AC-016, EARS-012
        Reliability: Blue
        """
        from botocore.exceptions import ClientError
        from src.models.card import Card

        # Mock get_card to succeed (card appears to exist)
        mock_card = Card(
            user_id="test-user-id",
            front="Q",
            back="A",
            created_at=datetime.now(timezone.utc),
            next_review_at=datetime.now(timezone.utc),
        )
        monkeypatch.setattr(card_service, "get_card", lambda uid, cid: mock_card)

        # Mock transact_write_items to simulate card already deleted (race condition)
        original_client = card_service.dynamodb.meta.client

        def mock_transact(*args, **kwargs):
            raise ClientError(
                {
                    "Error": {
                        "Code": "TransactionCanceledException",
                        "Message": "Transaction cancelled",
                    },
                    "CancellationReasons": [
                        {"Code": "ConditionalCheckFailed", "Message": "Card does not exist"},
                        {"Code": "None"},   # Review delete (no condition)
                        {"Code": "None"},   # User update
                    ],
                },
                "TransactWriteItems",
            )

        monkeypatch.setattr(original_client, "transact_write_items", mock_transact)

        with pytest.raises(CardNotFoundError):
            card_service.delete_card("test-user-id", "card-already-deleted")
```

### TC-06b: card_count = 0 Delete Prevention

**Description**: Verify that card_count cannot go negative when a delete is attempted and card_count is already 0 (data drift scenario).

**Preconditions**:
- Mock `get_card` to succeed (card exists)
- Mock `transact_write_items` raises `ClientError` with `CancellationReasons[2].Code == 'ConditionalCheckFailed'` (card_count > :zero check failed)

**Expected Result**:
- `CardServiceError` is raised with message containing "card_count"
- card_count remains at 0 (not -1)

```python
    def test_delete_card_prevents_negative_count(self, card_service, monkeypatch):
        """TC-06b: card_count cannot go negative during delete.

        Given: User's card_count is already 0 (data integrity drift)
        When: delete_card is called
        Then: CardServiceError is raised indicating card_count is at 0

        Maps to: AC-013, EARS-013, EARS-014
        Reliability: Yellow
        """
        from botocore.exceptions import ClientError
        from src.models.card import Card

        # Mock get_card to succeed (card exists despite count = 0)
        mock_card = Card(
            user_id="test-user-id",
            front="Q",
            back="A",
            created_at=datetime.now(timezone.utc),
            next_review_at=datetime.now(timezone.utc),
        )
        monkeypatch.setattr(card_service, "get_card", lambda uid, cid: mock_card)

        # Mock transact_write_items to simulate card_count = 0 condition failure
        original_client = card_service.dynamodb.meta.client

        def mock_transact(*args, **kwargs):
            raise ClientError(
                {
                    "Error": {
                        "Code": "TransactionCanceledException",
                        "Message": "Transaction cancelled",
                    },
                    "CancellationReasons": [
                        {"Code": "None"},                       # Index 0: Card delete OK
                        {"Code": "None"},                       # Index 1: Review delete OK
                        {"Code": "ConditionalCheckFailed"},     # Index 2: card_count > 0 failed
                    ],
                },
                "TransactWriteItems",
            )

        monkeypatch.setattr(original_client, "transact_write_items", mock_transact)

        with pytest.raises(CardServiceError) as exc_info:
            card_service.delete_card("test-user-id", "card-with-zero-count")

        assert "card_count" in str(exc_info.value).lower()
```

---

## Test Class 4: TestGetOrCreateUser

**File**: `backend/tests/unit/test_user_service.py`
**Fix**: Fix 4 - User existence guarantee before card creation
**Maps to**: EARS-015, EARS-016
**Acceptance Criteria**: AC-017, AC-018, AC-019, AC-020

### TC-07: get_or_create_user Returns Existing User

**Description**: Verify that `get_or_create_user` returns an existing user without modification when the user already exists.

**Preconditions**:
- User record exists with `user_id`, `card_count = 5`, and other attributes

**Expected Result**:
- Existing user is returned
- No attributes are modified (card_count remains 5)

```python
class TestGetOrCreateUser:
    """Tests for get_or_create_user idempotency (Fix 4)."""

    def test_get_or_create_user_existing(self, user_service, dynamodb_table):
        """TC-07: get_or_create_user returns existing user unchanged.

        Given: A user record exists with card_count = 5
        When: get_or_create_user is called
        Then: The existing user is returned with card_count unchanged

        Maps to: AC-019, AC-020, EARS-016
        Reliability: Blue
        """
        # Setup: Existing user with card_count
        table = dynamodb_table.Table("memoru-users-test")
        table.put_item(
            Item={
                "user_id": "existing-user-id",
                "card_count": 5,
                "created_at": "2024-01-01T00:00:00+00:00",
                "settings": {"notification_time": "09:00", "timezone": "Asia/Tokyo"},
            }
        )

        # Execute
        user = user_service.get_or_create_user("existing-user-id")

        # Assert: existing user returned unchanged
        assert user.user_id == "existing-user-id"
        assert user.settings["notification_time"] == "09:00"

        # Verify in database: card_count not modified
        stored = table.get_item(Key={"user_id": "existing-user-id"})["Item"]
        assert stored["card_count"] == 5
```

### TC-08: get_or_create_user Creates New User

**Description**: Verify that `get_or_create_user` creates a new user when one does not exist.

**Preconditions**:
- No user record exists for the given `user_id`

**Expected Result**:
- New user record is created
- User has expected default values (settings with defaults)
- **Note**: The User model's `to_dynamodb_item()` does NOT include `card_count`. This is expected -- Fix 1 (`if_not_exists`) handles the missing attribute.

```python
    def test_get_or_create_user_new(self, user_service, dynamodb_table):
        """TC-08: get_or_create_user creates new user when not found.

        Given: No user record exists for 'new-user-id'
        When: get_or_create_user is called
        Then: A new user is created with default settings

        Note: The User model's to_dynamodb_item() does NOT include card_count.
              This is by design -- Fix 1 (if_not_exists) handles the missing attribute
              when the first card is created.

        Maps to: AC-017, AC-018, EARS-015, EARS-016
        Reliability: Blue
        """
        # Execute
        user = user_service.get_or_create_user("new-user-id")

        # Assert: user created
        assert user.user_id == "new-user-id"
        assert user.settings["notification_time"] == "09:00"
        assert user.settings["timezone"] == "Asia/Tokyo"

        # Verify in database
        table = dynamodb_table.Table("memoru-users-test")
        stored = table.get_item(Key={"user_id": "new-user-id"})["Item"]
        assert stored["user_id"] == "new-user-id"
        assert "created_at" in stored
        # card_count is NOT set by to_dynamodb_item() -- this is expected
        # Fix 1 (if_not_exists) handles missing card_count attribute
```

---

## Test Class 5: TestCardCountEndToEnd

**File**: `backend/tests/unit/test_card_service.py`
**Fix**: Fix 1 + Fix 3 combined
**Maps to**: Combined verification
**Acceptance Criteria**: AC-021, AC-022, AC-023

### TC-09: End-to-End Create/Delete card_count Consistency

**Description**: Integration test verifying that create and delete operations maintain card_count consistency across the full lifecycle.

**Preconditions**:
- Clean user state (user record auto-created via mock)

**Expected Result**:
- card_count accurately reflects the number of cards at each step

```python
class TestCardCountEndToEnd:
    """Integration tests for card_count consistency (Fix 1 + Fix 3)."""

    def test_create_delete_card_count_consistency(self, card_service, dynamodb_table):
        """TC-09: card_count stays consistent through create and delete cycle.

        Given: A fresh user (no card_count attribute)
        When: 3 cards are created, then 2 are deleted
        Then: card_count accurately reflects the number of cards at each step

        Steps:
          1. Create 3 cards -> card_count == 3
          2. Delete 1st card -> card_count == 2
          3. Delete 2nd card -> card_count == 1

        Maps to: AC-021, AC-022, AC-023
        Reliability: Blue
        """
        users_table = dynamodb_table.Table("memoru-users-test")

        # Create 3 cards
        cards = []
        for i in range(3):
            card = card_service.create_card(
                user_id="test-user-id",
                front=f"Question {i}",
                back=f"Answer {i}",
            )
            cards.append(card)

        # Verify: card_count == 3
        user = users_table.get_item(Key={"user_id": "test-user-id"})["Item"]
        assert user["card_count"] == 3

        # Delete first card
        card_service.delete_card("test-user-id", cards[0].card_id)

        # Verify: card_count == 2
        user = users_table.get_item(Key={"user_id": "test-user-id"})["Item"]
        assert user["card_count"] == 2

        # Delete second card
        card_service.delete_card("test-user-id", cards[1].card_id)

        # Verify: card_count == 1
        user = users_table.get_item(Key={"user_id": "test-user-id"})["Item"]
        assert user["card_count"] == 1

        # Remaining card should still be accessible
        remaining = card_service.get_card("test-user-id", cards[2].card_id)
        assert remaining.card_id == cards[2].card_id
```

---

## Edge Cases Covered by Test Cases

### Fix 1: if_not_exists

| Edge Case | Test Case | Description |
|-----------|-----------|-------------|
| EC-001 | TC-01 | User record exists with no card_count attribute at all |
| EC-002 | Existing tests | User record exists with card_count = 0 (normal increment) |
| EC-003 | Existing tests (TestCardServiceRaceConditionPrevention) | card_count = 1999 (just under limit) |
| EC-004 | TC-02, Existing tests | card_count = 2000 (at limit, ConditionalCheckFailed) |

### Fix 2: Error Classification

| Edge Case | Test Case | Description |
|-----------|-----------|-------------|
| EC-006 | TC-04a | CancellationReasons key missing from error response |
| EC-007 | TC-04b | CancellationReasons is empty list [] |
| EC-008 | TC-03 | CancellationReasons[0] has non-ConditionalCheckFailed Code |
| EC-010 | TC-02 | Only index 0 is checked for limit classification |

### Fix 3: Delete Atomicity

| Edge Case | Test Case | Description |
|-----------|-----------|-------------|
| EC-013 | TC-06a | Card already deleted by concurrent request (race condition) |
| EC-014 | TC-06b | card_count = 0 but card still exists (data drift) |
| EC-015 | TC-09 | card_count = 1, deleting the last card (boundary) |

### Fix 4: User Existence

| Edge Case | Test Case | Description |
|-----------|-----------|-------------|
| EC-017 | TC-08 + TC-01 | First-time user calls POST /cards (combined verification) |
| EC-018 | TC-07 | get_or_create_user for existing user (idempotent) |

---

## Import Requirements

### test_card_service.py (new imports)

```python
# Add to existing imports at top of file:
from src.services.card_service import (
    CardService,
    CardNotFoundError,
    CardLimitExceededError,
    CardServiceError,   # NEW - needed for TC-06b
    InternalError,      # NEW - needed for TC-03, TC-04a, TC-04b
)
```

### test_user_service.py (no new imports needed)

The existing imports are sufficient for TC-07 and TC-08. The `get_or_create_user` method is already implemented in `user_service.py`.

---

## Traceability Matrix

| Requirement | Test Case(s) | Acceptance Criteria |
|-------------|-------------|---------------------|
| EARS-001 (if_not_exists UpdateExpression) | TC-01, TC-09 | AC-001, AC-002 |
| EARS-002 (if_not_exists ConditionExpression) | TC-01, TC-02 | AC-004 |
| EARS-003 (:zero attribute value) | TC-01 | AC-005 |
| EARS-004 (Missing card_count init) | TC-01 | AC-001, AC-002 |
| EARS-005 (InternalError class) | TC-03, TC-04a, TC-04b | AC-009 |
| EARS-006 (ConditionalCheckFailed classification) | TC-02 | AC-006 |
| EARS-007 (Non-limit failure classification) | TC-03 | AC-007 |
| EARS-008 (Missing CancellationReasons) | TC-04a, TC-04b | AC-008 |
| EARS-009 (Error logging) | TC-03 | AC-010 |
| EARS-010 (Transactional delete) | TC-05, TC-09 | AC-011, AC-012 |
| EARS-011 (reviews_table_name init) | TC-05 (fixture) | AC-015 |
| EARS-012 (Delete card not found) | TC-06a | AC-016 |
| EARS-013 (card_count = 0 on delete) | TC-06b | AC-013 |
| EARS-014 (card_count lower bound) | TC-06b | AC-013 |
| EARS-015 (Pre-create user) | TC-08 | AC-017, AC-018 |
| EARS-016 (get_or_create_user idempotency) | TC-07, TC-08 | AC-019, AC-020 |

---

## Execution Order

Tests should be executed in the following order during TDD Red phase:

1. **TC-01** (if_not_exists) -- Foundational test, verifies safe increment
2. **TC-02** (ConditionalCheckFailed) -- Error classification baseline
3. **TC-03** (non-ConditionalCheckFailed) -- New InternalError class required
4. **TC-04a** (missing CancellationReasons) -- Edge case for error parsing
5. **TC-04b** (empty CancellationReasons) -- Edge case for error parsing
6. **TC-05** (delete decrements) -- Requires transactional delete implementation
7. **TC-06a** (delete race condition) -- Error handling for delete transaction
8. **TC-06b** (negative count prevention) -- Edge case for delete transaction
9. **TC-07** (get_or_create existing) -- User service verification
10. **TC-08** (get_or_create new) -- User service verification
11. **TC-09** (end-to-end) -- Full integration verification

**Expected failures in Red phase**:
- TC-01: Fails because `card_count + :inc` does not use `if_not_exists`
- TC-03: Fails because `InternalError` class does not exist yet
- TC-04a: Fails because all TransactionCanceledException raise CardLimitExceededError
- TC-04b: Fails because all TransactionCanceledException raise CardLimitExceededError
- TC-05: Fails because delete_card does not use transact_write_items
- TC-06a: Fails because delete_card does not use transact_write_items
- TC-06b: Fails because delete_card does not use transact_write_items
- TC-09: Fails because delete does not decrement card_count

**Expected passes in Red phase** (already working):
- TC-02: May pass if existing code catches ConditionalCheckFailed (depends on current behavior)
- TC-07: Should pass (get_or_create_user already implemented)
- TC-08: Should pass (get_or_create_user already implemented)

---

**Document Version**: 1.0
**Last Updated**: 2026-02-21
**Author**: Claude Code
