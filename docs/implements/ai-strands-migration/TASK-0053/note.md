# TASK-0053 Development Context Note

**Date**: 2026-02-23
**Status**: Ready for implementation
**Task Type**: TDD (Red → Green → Refactor)

---

## Quick Reference

This task implements the **AIService Protocol interface** and associated infrastructure. It is the foundational work for Phase 1 of ai-strands-migration, enabling both BedrockAIService and StrandsAIService to implement a common contract.

**Key Files to Create**:
- `/Volumes/external/dev/memoru-liff/backend/src/services/ai_service.py` (NEW)
- `/Volumes/external/dev/memoru-liff/backend/tests/unit/test_ai_service.py` (NEW)

**Key Files to Reference** (do NOT modify in this task):
- `/Volumes/external/dev/memoru-liff/backend/src/services/bedrock.py`
- `/Volumes/external/dev/memoru-liff/backend/src/services/prompts.py`
- `/Volumes/external/dev/memoru-liff/docs/design/ai-strands-migration/interfaces.py`
- `/Volumes/external/dev/memoru-liff/docs/design/ai-strands-migration/architecture.md`

---

## Technology Stack

### Python & Framework
- **Runtime**: Python 3.12
- **Async**: Standard `async`/`await` (NOT asyncio required for simple dataclass/protocol definitions)
- **Type Hints**: `typing` module (`Protocol`, `Literal`, `List`, `Union`)
- **Data Classes**: `dataclasses.dataclass` with default factories
- **Testing**: pytest with fixtures and parametrization

### AWS & Bedrock
- **Service**: Amazon Bedrock (Claude 3 Haiku)
- **Python SDK**: boto3 (already integrated in BedrockService)
- **Model ID**: `anthropic.claude-3-haiku-20240307-v1:0` (configurable via env var)
- **Error Handling**: `botocore.exceptions.ClientError` mapping to custom exceptions

### Pydantic
- **Version**: v2 (used in models layer, NOT in ai_service.py)
- **Usage in this task**: NOT USED. ai_service.py uses only dataclasses and Protocol.
- **Note**: Response models (GradeAnswerResponse, LearningAdviceResponse) use Pydantic but are TASK-0054+ scope

---

## Development Rules & Coding Conventions

### 1. Module Organization

```
backend/src/services/
├── ai_service.py          # NEW - Protocol + Factory + Exceptions
├── bedrock.py             # EXISTING - BedrockService (to be updated in TASK-0055)
├── strands_service.py     # FUTURE - StrandsAIService (TASK-0054+)
└── prompts.py             # EXISTING - prompt templates
```

### 2. Naming Conventions

**Exceptions**:
- Base: `AIServiceError` (inherits from `Exception`)
- Child classes: `AI{ErrorType}Error` (e.g., `AITimeoutError`, `AIRateLimitError`)
- Difference from Bedrock: Use **AI prefix** (not Bedrock prefix)

**Data Classes**:
- Use `@dataclass` decorator (not Pydantic BaseModel)
- Import from `dataclasses import dataclass, field`
- Use `field(default_factory=list)` for mutable defaults
- All required fields first, optional fields after

**Protocol**:
- Use `@runtime_checkable` decorator
- Import from `typing import Protocol, runtime_checkable`
- Define method stubs with `...` (Ellipsis)
- Document with docstrings

**Type Aliases**:
- Use `Literal` for enum-like types
- Export at module level for reuse

### 3. Import Organization

```python
# Standard library imports (alphabetical)
from dataclasses import dataclass, field
from typing import List, Literal, Protocol, runtime_checkable

# Third-party imports
# (none for ai_service.py itself)

# Local imports
# (use in create_ai_service() factory function - lazy imports to avoid cycles)
```

### 4. Error Handling

All exceptions in ai_service.py inherit from `AIServiceError`:

```python
class AIServiceError(Exception):
    """Base exception for AI service operations."""
    pass

class AITimeoutError(AIServiceError):
    """AI service timed out (→ HTTP 504)."""
    pass

class AIRateLimitError(AIServiceError):
    """Rate limit exceeded (→ HTTP 429)."""
    pass

class AIInternalError(AIServiceError):
    """Internal service error (→ HTTP 500)."""
    pass

class AIParseError(AIServiceError):
    """Response parsing error (→ HTTP 500)."""
    pass

class AIProviderError(AIServiceError):
    """Provider initialization/connection error (→ HTTP 503)."""
    pass
```

**Mapping from Bedrock exceptions** (for TASK-0055):
- `BedrockTimeoutError` → `AITimeoutError`
- `BedrockRateLimitError` → `AIRateLimitError`
- `BedrockInternalError` → `AIInternalError`
- `BedrockParseError` → `AIParseError`
- Initialization failures → `AIProviderError`

---

## Related Existing Implementations

### 1. Current BedrockService Structure

**File**: `/Volumes/external/dev/memoru-liff/backend/src/services/bedrock.py`

Current exceptions (to be migrated in TASK-0055):
```python
class BedrockServiceError(Exception):
    pass

class BedrockTimeoutError(BedrockServiceError):
    pass

class BedrockRateLimitError(BedrockServiceError):
    pass

class BedrockInternalError(BedrockServiceError):
    pass

class BedrockParseError(BedrockServiceError):
    pass
```

Current dataclasses (to be MOVED to ai_service.py):
```python
@dataclass
class GeneratedCard:
    """A generated flashcard."""
    front: str
    back: str
    suggested_tags: List[str]

@dataclass
class GenerationResult:
    """Result of card generation."""
    cards: List[GeneratedCard]
    input_length: int
    model_used: str
    processing_time_ms: int
```

Current method signature (reference for Protocol):
```python
def generate_cards(
    self,
    input_text: str,
    card_count: int = 5,
    difficulty: DifficultyLevel = "medium",
    language: Language = "ja",
) -> GenerationResult:
    """Generate flashcards from input text using AI."""
```

### 2. Type Definitions in prompts.py

**File**: `/Volumes/external/dev/memoru-liff/backend/src/services/prompts.py`

Existing type aliases (to be imported in ai_service.py):
```python
DifficultyLevel = Literal["easy", "medium", "hard"]
Language = Literal["ja", "en"]
```

**Note**: interface.py uses `"medium"` while TASK-0053 task file shows variations. Use `"medium"` per prompts.py.

### 3. Test Patterns from test_bedrock.py

**File**: `/Volumes/external/dev/memoru-liff/backend/tests/unit/test_bedrock.py`

Relevant test patterns:

**Fixture Pattern**:
```python
@pytest.fixture
def bedrock_service(self):
    """Create BedrockService with mock client."""
    mock_client = MagicMock()
    return BedrockService(bedrock_client=mock_client)
```

**Exception Testing**:
```python
def test_exception_hierarchy():
    """Test that exceptions inherit correctly."""
    assert issubclass(BedrockTimeoutError, BedrockServiceError)

def test_exception_catching():
    """Test catch-all exception handling."""
    with pytest.raises(BedrockServiceError):
        raise BedrockTimeoutError("message")
```

**Dataclass Testing**:
```python
def test_model_used_in_result(self):
    """Test that metadata is included."""
    service = BedrockService(model_id="test-model-id")
    result = service.generate_cards(...)
    assert result.model_used == "test-model-id"
```

---

## Design Document References

### Architecture Design
**File**: `/Volumes/external/dev/memoru-liff/docs/design/ai-strands-migration/architecture.md`

**Key Sections**:
- **System Overview** (lines 14-20): Protocol-based abstraction overview
- **AIService Protocol Detail Design** (lines 194-254): Exact Protocol signature
- **Factory Pattern** (lines 256-273): create_ai_service() implementation pattern

**Reliability Levels**:
- 🔵 Blue (Confirmed): All dataclass definitions, Protocol signatures, exception hierarchy
- 🟡 Yellow: ReviewSummary.streak_days calculation details (external dependency on TASK-0046)

### Interface Definitions
**File**: `/Volumes/external/dev/memoru-liff/docs/design/ai-strands-migration/interfaces.py`

**Key Exports** (lines 1-299):
- All dataclass definitions with detailed docstrings
- Complete exception hierarchy
- Protocol definition with all three methods
- Factory function signature
- Type aliases (DifficultyLevel, Language, SRSGrade)

**Design Notes**:
- Uses `@runtime_checkable` for Protocol
- Dataclasses use `field(default_factory=...)` for mutable defaults
- ReviewSummary.recent_review_dates: List[str] (not datetime objects)
- All classes include "🔵" or "🟡" reliability markers

---

## Key Constraints & Considerations

### 1. Backward Compatibility (CRITICAL)

- **Existing 260+ tests must ALL pass** (REQ-SM-405)
- The new ai_service.py module must NOT break existing imports
- BedrockService and its methods remain unchanged until TASK-0055
- Existing GeneratedCard and GenerationResult will be moved (duplicated in ai_service.py, then imported from ai_service.py in TASK-0055)

### 2. Protocol vs Implementation

- **Protocol** is structural typing - no inheritance required
- Use `@runtime_checkable` to enable `isinstance()` checks (though not always necessary)
- Implementations (BedrockAIService, StrandsAIService) just need to implement the methods
- Protocol methods use sync signatures (NOT async) in interfaces.py
  - **CLARIFICATION**: Task file mentions "async" but interface.py shows sync. **Use sync signatures in Protocol** (design doc is source of truth)

### 3. Factory Function Behavior

**Location**: `backend/src/services/ai_service.py` module level

**Pseudo-code**:
```python
def create_ai_service(use_strands: bool = None) -> AIService:
    """
    Args:
        use_strands: If None, read from USE_STRANDS env var
                     (default: "false")

    Returns:
        AIService: BedrockAIService or StrandsAIService instance

    Raises:
        AIProviderError: On SDK initialization failure
    """
    # Use lazy imports to avoid circular dependencies
    import os
    from services.bedrock import BedrockAIService
    from services.strands_service import StrandsAIService  # Future
```

**Environment Variable**:
- `USE_STRANDS`: "true" or "false" (case-insensitive, default "false")

### 4. Type Alias Handling

**Option 1** (Current prompts.py):
```python
DifficultyLevel = Literal["easy", "medium", "hard"]
Language = Literal["ja", "en"]
```

**Option 2** (interfaces.py with SRSGrade):
```python
SRSGrade = Literal[0, 1, 2, 3, 4, 5]  # Not used in this task
```

**Decision**: Use Literal types from typing, not Python 3.10 native `|` syntax (ensure Python 3.12 compatibility with older linters)

### 5. Dataclass Default Values

IMPORTANT: Be careful with mutable defaults:

```python
# ❌ WRONG
@dataclass
class ReviewSummary:
    tag_performance: dict = {}  # Shared mutable!

# ✅ CORRECT
@dataclass
class ReviewSummary:
    tag_performance: dict = field(default_factory=dict)
```

Applied to ai_service.py:
- `GeneratedCard.suggested_tags` → `field(default_factory=list)`
- `ReviewSummary.tag_performance` → `field(default_factory=dict)`
- `ReviewSummary.recent_review_dates` → `field(default_factory=list)`

---

## Test Coverage Requirements

**Target**: 80%+ coverage on ai_service.py

### Test File Structure
**Location**: `/Volumes/external/dev/memoru-liff/backend/tests/unit/test_ai_service.py`

**Test Classes** (from TASK-0053 task file):

1. **Protocol Validation** (Test 1 in task file, lines 244-256)
   - Verify AIService has required methods
   - Verify method signatures

2. **Dataclass Tests** (Test 2, lines 260-321)
   - GeneratedCard instantiation
   - GenerationResult instantiation
   - GradingResult (with grade range 0-5 validation)
   - LearningAdvice
   - ReviewSummary (with average_grade range validation)

3. **Exception Hierarchy** (Test 3, lines 325-346)
   - All exceptions inherit from AIServiceError
   - Exception catching works correctly

4. **Factory Function** (Test 4, lines 350-377)
   - `create_ai_service(use_strands=False)` → BedrockAIService
   - `create_ai_service(use_strands=True)` → StrandsAIService
   - Environment variable `USE_STRANDS` respected
   - Explicit parameter overrides environment variable
   - Initialization failure → AIProviderError

5. **Type Definition Tests** (Test 5, lines 381-396)
   - Difficulty level Literal validation
   - Language Literal validation
   - (These are mostly static type checking, may skip runtime tests)

### Running Tests

```bash
# Run TASK-0053 tests only
cd /Volumes/external/dev/memoru-liff
pytest backend/tests/unit/test_ai_service.py -v

# Check coverage
pytest backend/tests/unit/test_ai_service.py --cov=services.ai_service --cov-report=term-missing

# Run all existing tests to verify backward compatibility
pytest backend/tests/unit/ -v

# Expected result: 260+ tests pass
```

---

## Implementation Sequence (TDD Red-Green-Refactor)

### Phase 1: Red (Test Writing)

1. Create `/Volumes/external/dev/memoru-liff/backend/tests/unit/test_ai_service.py`
2. Add all test classes and test methods from TASK-0053 task file
3. Run: `pytest backend/tests/unit/test_ai_service.py -v`
4. **Expected**: All tests FAIL (module not implemented)

### Phase 2: Green (Implementation)

1. Create `/Volumes/external/dev/memoru-liff/backend/src/services/ai_service.py`
2. Add imports:
   ```python
   from __future__ import annotations
   from dataclasses import dataclass, field
   from typing import List, Literal, Protocol, runtime_checkable
   ```

3. Implement in order:
   - Type aliases (DifficultyLevel, Language)
   - Exception hierarchy (AIServiceError base + 5 children)
   - Dataclasses (GeneratedCard, GenerationResult, GradingResult, LearningAdvice, ReviewSummary)
   - AIService Protocol with @runtime_checkable
   - create_ai_service() factory function

4. Run tests: `pytest backend/tests/unit/test_ai_service.py -v`
5. **Expected**: All tests PASS

### Phase 3: Refactor (Quality Improvement)

1. Add module-level docstring with reliability markers
2. Enhance docstrings for complex dataclasses (ReviewSummary)
3. Add defensive checks in factory (better error messages)
4. Verify no circular imports (run full test suite)
5. Run: `pytest backend/tests/unit/test_ai_service.py --cov=services.ai_service`
6. **Expected**: 80%+ coverage, all 260+ existing tests still pass

---

## Code Location & Module Structure

```
/Volumes/external/dev/memoru-liff/
├── backend/
│   ├── src/
│   │   └── services/
│   │       ├── __init__.py              (may need to export from ai_service)
│   │       ├── ai_service.py            # NEW - This task
│   │       ├── bedrock.py               # Reference only
│   │       └── prompts.py               # Reference only
│   ├── tests/
│   │   └── unit/
│   │       ├── test_ai_service.py       # NEW - This task
│   │       └── test_bedrock.py          # Existing (must stay green)
│   └── template.yaml                    # Reference only (no changes)
└── docs/
    ├── design/
    │   └── ai-strands-migration/
    │       ├── architecture.md          # Design reference
    │       └── interfaces.py            # Interface reference
    └── implements/
        └── ai-strands-migration/
            └── TASK-0053/
                └── note.md              # This file
```

---

## Common Pitfalls to Avoid

### 1. Circular Imports
- ❌ Don't import StrandsAIService at module level in ai_service.py
- ✅ Use lazy imports in create_ai_service() factory function

### 2. Mutable Default Arguments
- ❌ Don't use `tags: List[str] = []`
- ✅ Use `tags: List[str] = field(default_factory=list)`

### 3. Breaking Existing Code
- ❌ Don't remove GeneratedCard from bedrock.py in this task
- ✅ Keep bedrock.py unchanged; it will import from ai_service.py in TASK-0055

### 4. Type Checking
- ❌ Don't use Python 3.10 syntax like `list[str]` (inconsistent with 3.12 typing)
- ✅ Use `List[str]` from typing module for consistency

### 5. Protocol Methods
- ❌ Don't make Protocol methods async (Protocol methods should sync in interface layer)
- ✅ Implementations (BedrockAIService) can be sync or async as needed

### 6. Exception Hierarchy
- ❌ Don't forget to inherit from AIServiceError for all child exceptions
- ✅ Always: `class AI{Type}Error(AIServiceError): pass`

---

## Integration Points (Future Tasks)

This task enables the following downstream work:

1. **TASK-0054**: Prompt Module Refactoring
   - Uses exception hierarchy from ai_service.py
   - Uses dataclass definitions (GradingResult, LearningAdvice, ReviewSummary)

2. **TASK-0055**: BedrockAIService Protocol Compliance
   - Imports from ai_service.py (GeneratedCard, GenerationResult, AIService Protocol)
   - Replaces BedrockServiceError with AIServiceError hierarchy
   - Updates imports in handler.py

3. **TASK-0056**: Handler.py AIServiceFactory Integration
   - Uses create_ai_service() factory function
   - Catches AIServiceError exceptions

---

## Quick Checklist

**Before Implementation**:
- [ ] Read interfaces.py (source of truth for signatures)
- [ ] Read architecture.md (system context)
- [ ] Review bedrock.py (existing patterns)
- [ ] Review test_bedrock.py (test patterns)

**During Implementation**:
- [ ] Use `@runtime_checkable` on Protocol
- [ ] Use `@dataclass` (not Pydantic) for data classes
- [ ] Use `field(default_factory=...)` for mutable defaults
- [ ] All exceptions inherit from AIServiceError
- [ ] Factory function uses lazy imports
- [ ] All docstrings have reliability markers (🔵/🟡)

**After Implementation**:
- [ ] All TASK-0053 tests pass (80%+ coverage)
- [ ] All 260+ existing tests pass
- [ ] No import errors in handler.py
- [ ] Type hints are complete and consistent

---

## Additional Resources

- **CLAUDE.md**: Project conventions and local dev setup
  - Path: `/Volumes/external/dev/memoru-liff/CLAUDE.md`
  - Relevant sections: Technology Stack, Development Commands, Testing

- **Backend Testing**: Standard pytest command
  ```bash
  cd /Volumes/external/dev/memoru-liff/backend
  make test  # Runs all tests
  ```

- **Type Checking** (if applicable):
  ```bash
  cd /Volumes/external/dev/memoru-liff/backend
  python -m mypy src/services/ai_service.py  # Future: verify type hints
  ```

---

## Summary

This task creates the **AIService Protocol** and **exception hierarchy** that enables seamless switching between BedrockAIService and StrandsAIService. The implementation is **purely structural** (Protocol + dataclasses + exceptions), with no external API calls. Focus on test coverage and backward compatibility.

**Estimated effort**: 8 hours (per task file estimate)
**Key milestone**: All 260+ existing tests remain green ✅
