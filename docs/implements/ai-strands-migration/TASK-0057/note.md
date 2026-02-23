# TASK-0057: StrandsAIService 基本実装（カード生成）
## TDD Task Note

**Date**: 2026-02-23
**Status**: Task Note Creation
**Type**: TDD (Red → Green → Refactor → Verify)
**Estimated Hours**: 8

---

## Executive Summary

This task note documents the complete implementation strategy for TASK-0057, which implements the `StrandsAIService` class using the AWS Strands Agents SDK for flashcard generation. The implementation follows a TDD approach with clear Red-Green-Refactor phases. The service will provide the same `generate_cards()` interface as the existing `BedrockService` while using Strands Agent for enhanced AI capabilities.

### Key Changes at a Glance

| Component | Change | Purpose |
|-----------|--------|---------|
| **New File** | `backend/src/services/strands_service.py` | Main Strands Agents integration |
| **AI Service Protocol** | Implement Protocol methods | Ensure interface compatibility |
| **Model Provider** | Environment-based selection | Bedrock (prod/staging) vs Ollama (dev) |
| **Error Handling** | Unified AIServiceError hierarchy | Consistent error management |
| **Tests** | `backend/tests/unit/test_strands_service.py` | 10+ test cases, 80%+ coverage |
| **Dependencies** | Strands Agents SDK v0.1+ | AWS Strands Agents integration |

---

## Part 1: Technology Stack

### Backend Framework & Language
- **Language**: Python 3.12
- **Framework**: AWS SAM (Serverless Application Model)
- **Runtime**: AWS Lambda
- **AI SDK**: AWS Strands Agents SDK (`strands-agents>=0.1.0,<2.0.0`)
- **Package Manager**: pip

**References**:
- `CLAUDE.md` - Project technical stack
- `backend/requirements.txt` - Dependencies including Strands Agents SDK

### AI Model Providers
- **Bedrock Model**: `anthropic.claude-3-haiku-20240307-v1:0` (production/staging)
- **Ollama Model**: `llama3.2` or `phi-3` (local development)
- **Model Selection**: Environment-based (ENVIRONMENT env var)

**References**:
- `backend/src/services/bedrock.py` - Existing Bedrock integration patterns
- `docs/spec/ai-strands-migration/requirements.md` - REQ-SM-005, REQ-SM-101 (model provider requirements)

### Data Serialization
- **Pydantic**: v2.5.0+ for type-safe data models
- **Data Classes**: Defined in `backend/src/services/ai_service.py`
  - `GeneratedCard`: Flashcard with front/back/suggested_tags
  - `GenerationResult`: Cards + metadata (input_length, model_used, processing_time_ms)
  - `GradingResult`, `LearningAdvice`: For Phase 3 features

**References**:
- `backend/src/services/ai_service.py` - AIService Protocol & data classes
- `backend/src/models/generate.py` - Response DTOs for API

---

## Part 2: Development Rules & Conventions

### Project-Specific Rules (from CLAUDE.md)

1. **TDD Workflow**: Use Tsumiki Kairo workflow
   - `/tsumiki:tdd-red` → `/tsumiki:tdd-green` → `/tsumiki:tdd-refactor` → `/tsumiki:tdd-verify-complete`
   - Task file: `docs/tasks/ai-strands-migration/TASK-0057.md`
   - Complete checklist boxes as development progresses

2. **Test Requirements**:
   - Minimum coverage: **80%** (requirement REQ-SM-404)
   - Test framework: pytest
   - Mock external dependencies (Strands Agent, Bedrock, Ollama)
   - All existing 260+ backend tests must remain passing (REQ-SM-405)

3. **Dependency Management**:
   - Strands Agents SDK version is pinned in `requirements.txt`
   - Version constraint: `>=0.1.0,<2.0.0` (to manage breaking changes)
   - All imports follow existing patterns from BedrockService

4. **Commit Rules**:
   - One task = one commit
   - Format: `TASK-0057: StrandsAIService 基本実装（カード生成）`
   - Include implementation details and co-author tag
   - Reference: CLAUDE.md Commit Rules

### Coding Conventions

- **Python Style**: PEP 8 (snake_case for functions/variables, CamelCase for classes)
- **Type Hints**: Full type annotations required (Python 3.12 support)
- **Docstrings**: Google style with Args/Returns/Raises sections
- **Error Handling**: Use AIServiceError hierarchy (not BedrockServiceError)

**References**:
- `CLAUDE.md` - Coding conventions section
- `backend/src/services/bedrock.py` - Existing implementation patterns (error handling, docstrings)

### Environment Variables

Required for StrandsAIService:

| Variable | Purpose | Prod | Dev |
|----------|---------|------|-----|
| `ENVIRONMENT` | Runtime environment | `prod`/`staging` | `dev` |
| `BEDROCK_MODEL_ID` | Bedrock model ID | `anthropic.claude-3-haiku-...` | N/A |
| `OLLAMA_HOST` | Ollama server URL | N/A | `http://localhost:11434` |
| `OLLAMA_MODEL` | Ollama model name | N/A | `llama3.2` |
| `USE_STRANDS` | Feature flag (handled by factory) | `true` | `true` |

**References**:
- `docs/design/ai-strands-migration/architecture.md` - Environment-based provider selection
- `backend/template.yaml` - Lambda environment variable definitions

---

## Part 3: Related Implementations & Reference Patterns

### Existing AI Service Implementation: BedrockService

**File**: `backend/src/services/bedrock.py` (332 lines)

Key patterns to follow:

```python
class BedrockService:
    """Service for interacting with Amazon Bedrock."""

    DEFAULT_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"
    MAX_TOKENS = 4096
    DEFAULT_TEMPERATURE = 0.7
    DEFAULT_TIMEOUT = 30

    def __init__(self, model_id: Optional[str] = None, bedrock_client=None):
        """Initialize with optional model override and test client."""

    def generate_cards(
        self,
        input_text: str,
        card_count: int = 5,
        difficulty: DifficultyLevel = "medium",
        language: Language = "ja",
    ) -> GenerationResult:
        """Main public method matching AIService Protocol."""

    def _invoke_with_retry(self, prompt: str) -> str:
        """Retry logic with Full Jitter exponential backoff."""

    def _invoke_claude(self, prompt: str) -> str:
        """Direct Bedrock API invocation."""

    def _parse_response(self, response_text: str) -> List[GeneratedCard]:
        """Response parsing and validation."""
```

**Patterns to adopt in StrandsAIService**:
- Optional dependency injection for testing (bedrock_client pattern)
- Retry logic with Full Jitter (may not be needed for Strands, but error handling should be consistent)
- Response parsing with JSON extraction (markdown code blocks)
- Consistent error types mapping

**References**:
- Lines 76-117: __init__ and model initialization pattern
- Lines 332-370: Retry logic pattern
- Lines 425-490: Response parsing pattern

### Error Hierarchy Implementation

**File**: `backend/src/services/ai_service.py` (Lines 71-106)

Unified error classes all implementations must use:

```python
class AIServiceError(Exception):
    """Base exception for AI services."""
    pass

class AITimeoutError(AIServiceError):
    """AI timeout → HTTP 504."""
    pass

class AIRateLimitError(AIServiceError):
    """AI rate limit → HTTP 429."""
    pass

class AIProviderError(AIServiceError):
    """AI provider unavailable → HTTP 503."""
    pass

class AIParseError(AIServiceError):
    """Response parse error → HTTP 500."""
    pass
```

**Usage in StrandsAIService**:
- Catch Strands SDK exceptions and map to AIServiceError hierarchy
- Do NOT use BedrockServiceError in new code
- Ensure error messages are descriptive for debugging

**References**:
- `docs/design/ai-strands-migration/architecture.md` - Error hierarchy design

### Prompt Management: Module Structure

**Directory**: `backend/src/services/prompts/`

**Files**:
- `__init__.py` - Package-level exports (re-exports from submodules)
- `_types.py` - Common type definitions (`Language`, `DifficultyLevel`)
- `generate.py` - Card generation prompt (existing, moved from prompts.py)
- `grading.py` - Answer grading prompt (Phase 3)
- `advice.py` - Learning advice prompt (Phase 3)

**Pattern for StrandsAIService**:
```python
from services.prompts import (
    get_card_generation_prompt,
    DifficultyLevel,
    Language,
)

# In __init__:
user_prompt = get_card_generation_prompt(
    input_text=input_text,
    card_count=card_count,
    difficulty=difficulty,
    language=language,
)
```

**References**:
- `backend/src/services/prompts/__init__.py` - Package exports
- `backend/src/services/prompts/_types.py` - Type definitions
- `backend/src/services/prompts/generate.py` - Prompt generation (lines 45-80+)

### API Handler Integration

**File**: `backend/src/api/handler.py`

Handler already has AIServiceFactory integration (TASK-0056):

```python
from services.ai_service import (
    create_ai_service,
    AIServiceError,
    AITimeoutError,
    AIRateLimitError,
    AIProviderError,
    AIParseError,
)

@app.post("/cards/generate")
def generate_cards_endpoint(event):
    """Generate flashcards via AI service."""
    ai_service = create_ai_service()  # Factory pattern
    result = ai_service.generate_cards(
        input_text=request.input_text,
        card_count=request.card_count,
        difficulty=request.difficulty,
        language=request.language,
    )
```

**Error mapping** (already implemented in handler):
```python
def _map_ai_error_to_http(error: AIServiceError) -> Response:
    if isinstance(error, AITimeoutError):
        return Response(status_code=504, ...)
    if isinstance(error, AIRateLimitError):
        return Response(status_code=429, ...)
    if isinstance(error, AIProviderError):
        return Response(status_code=503, ...)
    if isinstance(error, AIParseError):
        return Response(status_code=500, ...)
```

**References**:
- `backend/src/api/handler.py` (lines 41-49: imports, line 55-59: service initialization)
- `docs/design/ai-strands-migration/api-endpoints.md` - API specification

---

## Part 4: Design Documents & Architecture

### Architecture Design: StrandsAIService Structure

**File**: `docs/design/ai-strands-migration/architecture.md`

Key design principles:

1. **Protocol-Based Abstraction** (lines 35-51):
   ```
   AIService Protocol
   ├── generate_cards()      # Card generation
   ├── grade_answer()        # Answer grading (Phase 3, raise NotImplementedError)
   └── get_learning_advice() # Learning advice (Phase 3, raise NotImplementedError)

   Implementations:
   ├── BedrockAIService      # Existing boto3 implementation
   └── StrandsAIService      # New Strands Agents implementation
   ```

2. **Environment-Based Provider Selection** (requirements REQ-SM-101, REQ-SM-005):
   - prod/staging: Use BedrockModel (AWS Bedrock)
   - dev: Use OllamaModel (local Ollama server)

3. **Component Responsibility**:
   - `__init__()`: Model provider initialization, Strands Agent setup
   - `_create_model()`: Environment-based model selection
   - `generate_cards()`: Main business logic (Strands Agent invocation)
   - `_parse_generation_result()`: Response parsing (Agent → GenerationResult)

**References**:
- `docs/design/ai-strands-migration/architecture.md` (lines 33-93: component design, lines 95-150: system diagram)

### API Specification & Response Format

**File**: `docs/design/ai-strands-migration/api-endpoints.md`

Response format (must maintain compatibility):

```python
# HTTP 200 OK
{
    "generated_cards": [
        {
            "front": "Question text",
            "back": "Answer text",
            "suggested_tags": ["tag1", "tag2"]
        }
    ],
    "generation_info": {
        "model_used": "strands_bedrock" or "strands_ollama",
        "processing_time_ms": 1500,
        "input_length": 256
    }
}
```

**Requirement**: REQ-SM-402 - API response format compatibility

### Data Flow Design

**File**: `docs/design/ai-strands-migration/dataflow.md`

Card generation flow:

```
1. Frontend → POST /cards/generate
2. Handler → AIServiceFactory.create_ai_service()
3. Handler → ai_service.generate_cards()
4. StrandsAIService.__init__() → Initialize model provider + Strands Agent
5. StrandsAIService.generate_cards():
   a. Get prompt from prompts/generate.py
   b. Invoke Strands Agent (system_prompt + user_prompt)
   c. _parse_generation_result() → GenerationResult
6. Handler → Response mapping → HTTP 200
```

**Error scenarios**:
- Timeout: AITimeoutError → 504 Gateway Timeout
- Provider error: AIProviderError → 503 Service Unavailable
- Parse error: AIParseError → 500 Internal Server Error

---

## Part 5: Key Technical Constraints & Considerations

### Performance Constraints

- **Lambda Timeout**: 30 seconds (global from template.yaml)
- **Lambda Memory**: 256 MB (may need increase for Strands SDK)
- **Bedrock API Timeout**: 30 seconds (default, matching Lambda timeout)
- **Expected Response Time**: Strands Agent processing typically 1-5 seconds (but can vary)

**Note**: Strands Agents SDK may have higher latency than direct Bedrock calls due to multi-step reasoning. Monitor CloudWatch metrics.

**References**:
- `CLAUDE.md` - Performance constraints section
- `docs/spec/ai-strands-migration/requirements.md` - REQ-SM-401 (timeout configurations)

### Security & IAM Requirements

- **IAM Permissions**: Lambda execution role must have:
  - `bedrock:InvokeModel` (for Bedrock provider)
  - `bedrock:InvokeModelWithResponseStream` (if streaming used)
- **Input Validation**: User input must be validated (10-2000 characters) to prevent prompt injection
- **No Secrets in Code**: Model IDs come from environment variables, not hardcoded

**References**:
- `docs/spec/ai-strands-migration/requirements.md` - NFR-SM-101 (IAM), NFR-SM-102 (input sanitization)
- `backend/template.yaml` - IAM role definition

### SDK Stability & Compatibility

- **Strands Agents SDK Status**: Early-stage SDK (v0.1.x), expect potential breaking changes
- **Version Pinning**: `strands-agents>=0.1.0,<2.0.0` prevents major version changes
- **Backwards Compatibility**: `generate_cards()` interface must match BedrockService
- **Fallback Strategy**: Handler has `create_ai_service()` factory to select implementation

**References**:
- `docs/spec/ai-strands-migration/note.md` - SDK stability notes (line 284-285)
- `backend/requirements.txt` - Version constraints

### Existing Test Protection

- **Test Coverage Requirement**: 80% minimum (REQ-SM-404)
- **Existing Tests**: 260+ backend tests must remain passing (REQ-SM-405)
- **Test Framework**: pytest with unittest.mock for mocking
- **No Regressions**: New implementation must not break existing Bedrock tests

**Important**: `backend/tests/unit/test_bedrock.py` must continue to pass. StrandsAIService is an alternative implementation, not a replacement.

---

## Part 6: Test Implementation Strategy

### Test File Location
`backend/tests/unit/test_strands_service.py` (new file)

### Test Categories

#### Category 1: Basic Functionality (TC-001 ~ TC-005)
- Normal case: Valid inputs generate expected cards
- JSON parsing: Valid Agent response → CardGenerated objects
- Missing fields: Required fields validation (question, answer, explanation)
- Invalid JSON: Malformed response handling
- Card count: Verify correct number of cards returned

#### Category 2: Error Handling (TC-006 ~ TC-008)
- Timeout: Strands Agent timeout → AITimeoutError (504)
- Provider error: Bedrock/Ollama error → AIProviderError (503)
- Validation error: Invalid topic → AIValidationError (400)

#### Category 3: Model Provider Selection (TC-009 ~ TC-010)
- Dev environment: ENVIRONMENT=dev → OllamaModel selected
- Prod environment: ENVIRONMENT=prod → BedrockModel selected

#### Category 4: Protocol Compliance (TC-011)
- Method existence: All AIService Protocol methods present
- Signature matching: generate_cards() parameters correct
- Return types: GenerationResult with expected structure

### Mocking Strategy

Use `unittest.mock.patch` for external dependencies:

```python
@patch('services.strands_service.StrandsAgent')
@patch.dict(os.environ, {'ENVIRONMENT': 'dev'})
def test_example(mock_agent):
    # Test implementation
    pass
```

### Test Data Fixtures

Define reusable test fixtures:

```python
@pytest.fixture
def valid_agent_response():
    """Sample Strands Agent response."""
    return {
        'cards': [
            {
                'question': 'What is X?',
                'answer': 'X is Y',
                'explanation': 'Because...'
            }
        ]
    }
```

**References**:
- `docs/tasks/ai-strands-migration/TASK-0057.md` (lines 183-253: test cases)
- `backend/tests/unit/test_bedrock.py` - Existing test patterns to follow

---

## Part 7: Implementation Checklist

### Phase 1: Red Phase - Write Failing Tests
- [ ] Create `backend/tests/unit/test_strands_service.py`
- [ ] Implement all 10+ test cases
- [ ] Verify tests fail (no implementation yet)
- [ ] Ensure pytest can discover and run tests

### Phase 2: Green Phase - Minimal Implementation
- [ ] Create `backend/src/services/strands_service.py`
- [ ] Implement StrandsAIService class
- [ ] Implement `__init__()` with model provider selection
- [ ] Implement `_create_model()` method
- [ ] Implement `generate_cards()` method
- [ ] Implement `_parse_generation_result()` helper
- [ ] Add NotImplementedError stubs for Phase 3 methods
- [ ] Verify all tests pass
- [ ] Check test coverage ≥ 80%
- [ ] Verify no existing tests break

### Phase 3: Refactor Phase
- [ ] Extract common code to helper methods
- [ ] Improve error messages
- [ ] Add type hints consistently
- [ ] Improve docstrings
- [ ] Remove duplication
- [ ] Optimize imports

### Phase 4: Verify Complete
- [ ] Run full test suite: `pytest backend/tests/ -v --cov=backend/src/services/strands_service.py`
- [ ] Check coverage: `pytest ... --cov-report=term-missing`
- [ ] Verify coverage ≥ 80%
- [ ] Review code quality
- [ ] Update TASK-0057.md checklist

---

## Part 8: Key Files & Directory Structure

### Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `backend/src/services/strands_service.py` | **Create** | Main StrandsAIService implementation |
| `backend/tests/unit/test_strands_service.py` | **Create** | Test suite (10+ tests) |
| `docs/tasks/ai-strands-migration/TASK-0057.md` | Modify | Update completion checklist |
| `docs/implements/ai-strands-migration/TASK-0057/note.md` | **Create** | This document |

### Existing Files to Reference (Read-Only)

| File | Purpose |
|------|---------|
| `backend/src/services/ai_service.py` | Protocol definition, error hierarchy |
| `backend/src/services/bedrock.py` | Implementation patterns, error handling |
| `backend/src/services/prompts/__init__.py` | Prompt module structure |
| `backend/src/services/prompts/generate.py` | Card generation prompt |
| `backend/src/api/handler.py` | Factory integration, error mapping |
| `backend/requirements.txt` | Dependencies (Strands Agents SDK) |
| `docs/design/ai-strands-migration/architecture.md` | System design |
| `docs/spec/ai-strands-migration/requirements.md` | Feature requirements |

---

## Part 9: Important Notes for Implementation

### Strands Agent API (Yellow Signal 🟡)

The exact Strands SDK API is documented but may differ from assumptions:
- Agent invocation: Assumed `agent(user_prompt)` format (verify with SDK docs)
- Response structure: Assumed dict with "cards" array (verify actual format)
- Tool integration: Tools are optional (Phase 4+), not needed for card generation

**Action**: When starting implementation, review Strands SDK documentation to confirm:
1. Agent initialization: `from strands_agents import Agent`
2. Agent invocation: Method name and signature
3. Response format: Keys and structure

### Grade Answer & Learning Advice (Phase 3)

These methods must raise `NotImplementedError`:

```python
def grade_answer(self, card_front: str, card_back: str, user_answer: str, language: Language = "ja") -> GradingResult:
    """Grading implementation deferred to Phase 3."""
    raise NotImplementedError("Phase 3 implementation pending")

def get_learning_advice(self, review_summary: dict, language: Language = "ja") -> LearningAdvice:
    """Advice implementation deferred to Phase 3."""
    raise NotImplementedError("Phase 3 implementation pending")
```

### Factory Pattern Integration

Handler already uses `create_ai_service()` factory (TASK-0056 complete):

```python
# In ai_service.py - Factory function
def create_ai_service(use_strands: bool | None = None) -> AIService:
    """Returns StrandsAIService if USE_STRANDS=true, else BedrockService."""
    if use_strands is None:
        use_strands = os.getenv("USE_STRANDS", "false").lower() == "true"

    if use_strands:
        from services.strands_service import StrandsAIService
        return StrandsAIService()
    else:
        from services.bedrock import BedrockService
        return BedrockService()
```

StrandsAIService just needs to implement the Protocol correctly.

---

## Part 10: References & Related Documentation

### Requirement Documents
- `docs/spec/ai-strands-migration/requirements.md` - Feature requirements (REQ-SM-002, 404, 405)
- `docs/spec/ai-strands-migration/acceptance-criteria.md` - Acceptance criteria

### Design Documents
- `docs/design/ai-strands-migration/architecture.md` - System architecture
- `docs/design/ai-strands-migration/dataflow.md` - Data flow & error handling
- `docs/design/ai-strands-migration/api-endpoints.md` - API specification

### Task Files
- `docs/tasks/ai-strands-migration/TASK-0057.md` - Task definition (checklist, test cases)
- `docs/tasks/ai-strands-migration/TASK-0052.md` - Environment & settings (dependency)
- `docs/tasks/ai-strands-migration/TASK-0054.md` - Prompt unification (dependency)
- `docs/tasks/ai-strands-migration/TASK-0056.md` - Handler & factory integration (dependency)

### Project Guidelines
- `CLAUDE.md` - Development workflow, commit rules, testing requirements
- `backend/requirements.txt` - Python dependencies
- `backend/template.yaml` - Lambda configuration, environment variables

### Existing Implementation References
- `backend/src/services/bedrock.py` - Bedrock service (patterns to follow)
- `backend/src/services/ai_service.py` - Protocol & error hierarchy
- `backend/src/services/prompts/` - Prompt management structure
- `backend/tests/unit/test_bedrock.py` - Test patterns

---

## Summary

TASK-0057 implements StrandsAIService, a new AI service using AWS Strands Agents SDK. Key aspects:

1. **Implements AIService Protocol**: Provides `generate_cards()` with same interface as BedrockService
2. **Environment-based Model Selection**: Bedrock for prod/staging, Ollama for dev
3. **Error Handling**: Uses unified AIServiceError hierarchy (not BedrockServiceError)
4. **Backward Compatible**: Existing API responses maintained (REQ-SM-402)
5. **Well-Tested**: 10+ test cases with 80%+ coverage (REQ-SM-404)
6. **Factory Pattern**: Integrated with existing `create_ai_service()` factory

All file paths in this document are relative to project root. Follow TDD phases (Red → Green → Refactor → Verify) as defined in CLAUDE.md.
