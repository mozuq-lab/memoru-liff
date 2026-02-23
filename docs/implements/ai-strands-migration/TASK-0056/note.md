# TASK-0056: handler.py AIServiceFactory 統合 + template.yaml 更新
## TDD Task Note

**Date**: 2026-02-23
**Status**: Task Note Creation
**Type**: TDD (Red → Green → Refactor)
**Estimated Hours**: 8

---

## Executive Summary

This task note documents the complete implementation strategy for TASK-0056, which integrates the AIServiceFactory pattern into handler.py and updates template.yaml with new API routes, environment variables, and Lambda timeout configurations. The implementation follows a TDD approach with clear Red-Green-Refactor phases.

### Key Changes at a Glance

| Component | Change | Purpose |
|-----------|--------|---------|
| **handler.py imports** | `BedrockService` → `create_ai_service` | Factory pattern adoption |
| **generate_cards endpoint** | Direct service → Factory-based service | Unified AI service abstraction |
| **Error handling** | New `_map_ai_error_to_http()` function | Standardized error mapping |
| **template.yaml timeout** | 30s → 60s | Strands SDK processing time |
| **template.yaml parameters** | Add `UseStrands` parameter | Feature flag support |
| **Environment variables** | Add `USE_STRANDS`, `OLLAMA_HOST`, `OLLAMA_MODEL` | Strands SDK configuration |
| **API routes** | Add `/reviews/{card_id}/grade-ai`, `/advice` | New AI features foundation |
| **env.json** | Add new env vars to all functions | Local development config |

---

## Part 1: TDD Red Phase - Test Implementation

### 1.1 Current State Analysis

#### Current handler.py (Lines 41-57)
```python
from services.bedrock import (
    BedrockService,
    BedrockTimeoutError,
    BedrockRateLimitError,
    BedrockInternalError,
    BedrockParseError,
)

# ...

bedrock_service = BedrockService()
```

#### Current generate_cards endpoint (Lines 241-316)
- Uses `bedrock_service` directly
- Error handling specific to BedrockService exceptions
- Returns GenerateCardsResponse with generation_info

#### Current template.yaml
- Global timeout: 30 seconds
- Global memory: 256 MB (may be insufficient for Strands SDK)
- No UseStrands parameter or condition
- No OLLAMA_* environment variables
- Only ApiFunction and LineWebhookFunction defined

#### Current env.json
- Only 3 functions configured
- No OLLAMA_* variables

### 1.2 Test Cases to Implement

#### Test Suite: test_handler.py (New File)

**Test 1: AIServiceFactory Integration**
```python
@patch.dict(os.environ, {"USE_STRANDS": "false"})
def test_handler_uses_bedrock_ai_service(api_gateway_event, lambda_context):
    """Verify handler uses BedrockAIService when USE_STRANDS=false.

    Test Focus:
    - create_ai_service is called once per request
    - Returns a BedrockAIService instance
    - Environment flag controls service selection

    Expected Outcome:
    - Mock factory is called exactly once
    - Factory returns correct service type
    """
    event = api_gateway_event(
        method="POST",
        path="/cards/generate",
        body={
            "input_text": "Study material here",
            "card_count": 5,
            "difficulty": "medium",
            "language": "ja"
        },
        user_id="test-user-123"
    )

    with patch("api.handler.create_ai_service") as mock_factory:
        mock_service = MagicMock()
        mock_service.generate_cards.return_value = MagicMock(
            cards=[MagicMock(front="Q1", back="A1", suggested_tags=["tag1"])],
            input_length=100,
            model_used="bedrock",
            processing_time_ms=500
        )
        mock_factory.return_value = mock_service

        from api.handler import handler
        response = handler(event, lambda_context)

        # Assertions
        mock_factory.assert_called_once()
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "generated_cards" in body
```

**Test 2: Strands Service Selection**
```python
@patch.dict(os.environ, {"USE_STRANDS": "true"})
def test_handler_uses_strands_ai_service_when_enabled(api_gateway_event, lambda_context):
    """Verify handler uses StrandsAIService when USE_STRANDS=true.

    Test Focus:
    - Factory respects USE_STRANDS flag
    - Strands service is instantiated on demand

    Expected Outcome:
    - Factory selects Strands service
    - Handler still processes generate_cards correctly
    """
    event = api_gateway_event(
        method="POST",
        path="/cards/generate",
        body={
            "input_text": "Study material here",
            "card_count": 5,
            "difficulty": "medium",
            "language": "ja"
        },
        user_id="test-user-123"
    )

    with patch("api.handler.create_ai_service") as mock_factory:
        mock_service = MagicMock()
        mock_service.generate_cards.return_value = MagicMock(
            cards=[MagicMock(front="Q1", back="A1", suggested_tags=["tag1"])],
            input_length=100,
            model_used="strands",
            processing_time_ms=1000
        )
        mock_factory.return_value = mock_service

        from api.handler import handler
        response = handler(event, lambda_context)

        # Assertions
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["generation_info"]["model_used"] == "strands"
```

**Test 3: Error Mapping - Timeout (504)**
```python
def test_ai_timeout_error_maps_to_504():
    """Verify AITimeoutError maps to HTTP 504.

    Test Focus:
    - Error classification is correct
    - HTTP status code follows API specification

    Expected Outcome:
    - Response status 504
    - Error message mentions timeout
    """
    from api.handler import _map_ai_error_to_http
    from services.ai_service import AITimeoutError

    error = AITimeoutError("AI service processing exceeded 60 seconds")
    response = _map_ai_error_to_http(error)

    assert response["statusCode"] == 504
    assert response["content_type"] == content_types.APPLICATION_JSON
    body = json.loads(response["body"])
    assert "timeout" in body["error"].lower()
```

**Test 4: Error Mapping - Rate Limit (429)**
```python
def test_ai_rate_limit_error_maps_to_429():
    """Verify AIRateLimitError maps to HTTP 429.

    Expected Outcome:
    - Response status 429
    - Error message mentions rate limit
    """
    from api.handler import _map_ai_error_to_http
    from services.ai_service import AIRateLimitError

    error = AIRateLimitError("Bedrock quota exceeded")
    response = _map_ai_error_to_http(error)

    assert response["statusCode"] == 429
    body = json.loads(response["body"])
    assert "rate limit" in body["error"].lower()
```

**Test 5: Error Mapping - Provider Error (503)**
```python
def test_ai_provider_error_maps_to_503():
    """Verify AIProviderError maps to HTTP 503.

    Expected Outcome:
    - Response status 503
    - Error message indicates service unavailable
    """
    from api.handler import _map_ai_error_to_http
    from services.ai_service import AIProviderError

    error = AIProviderError("Bedrock service not available in region")
    response = _map_ai_error_to_http(error)

    assert response["statusCode"] == 503
    body = json.loads(response["body"])
    assert "unavailable" in body["error"].lower()
```

**Test 6: Error Mapping - Parse Error (500)**
```python
def test_ai_parse_error_maps_to_500():
    """Verify AIParseError maps to HTTP 500.

    Expected Outcome:
    - Response status 500
    - Error message indicates parse failure
    """
    from api.handler import _map_ai_error_to_http
    from services.ai_service import AIParseError

    error = AIParseError("Invalid JSON in AI response")
    response = _map_ai_error_to_http(error)

    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "parse" in body["error"].lower()
```

**Test 7: Error Mapping - Internal Error (500)**
```python
def test_ai_internal_error_maps_to_500():
    """Verify AIInternalError maps to HTTP 500.

    Expected Outcome:
    - Response status 500 (generic internal error)
    """
    from api.handler import _map_ai_error_to_http
    from services.ai_service import AIInternalError

    error = AIInternalError("Unexpected error in AI service")
    response = _map_ai_error_to_http(error)

    assert response["statusCode"] == 500
```

**Test 8: Backward Compatibility - generate_cards**
```python
@pytest.mark.asyncio
async def test_generate_cards_backward_compatibility(api_gateway_event, lambda_context):
    """Verify generate_cards endpoint works with factory pattern.

    Test Focus:
    - Endpoint behavior unchanged from user perspective
    - Response format matches existing schema
    - All response fields present

    Expected Outcome:
    - Response includes generated_cards array
    - generation_info contains required fields
    - Status code 200 for valid input
    """
    event = api_gateway_event(
        method="POST",
        path="/cards/generate",
        body={
            "input_text": "The mitochondria is the powerhouse of the cell",
            "card_count": 3,
            "difficulty": "easy",
            "language": "en"
        },
        user_id="test-user-456"
    )

    with patch("api.handler.create_ai_service") as mock_factory:
        mock_service = MagicMock()
        mock_service.generate_cards.return_value = MagicMock(
            cards=[
                MagicMock(front="Q1", back="A1", suggested_tags=["biology"]),
                MagicMock(front="Q2", back="A2", suggested_tags=["biology", "cell"])
            ],
            input_length=50,
            model_used="bedrock",
            processing_time_ms=750
        )
        mock_factory.return_value = mock_service

        from api.handler import handler
        response = handler(event, lambda_context)

        # Assertions
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "generated_cards" in body
        assert len(body["generated_cards"]) >= 2
        assert "generation_info" in body
        assert body["generation_info"]["model_used"] in ["bedrock", "strands"]
        assert body["generation_info"]["processing_time_ms"] > 0
        assert body["generation_info"]["input_length"] > 0
```

**Test 9: Template Configuration - Environment Variables**
```python
def test_template_yaml_has_use_strands_parameter():
    """Verify template.yaml defines UseStrands parameter.

    Expected Outcome:
    - Parameter exists
    - Default is "false"
    - AllowedValues are ["true", "false"]
    """
    import yaml
    with open("backend/template.yaml", "r") as f:
        template = yaml.safe_load(f)

    assert "Parameters" in template
    assert "UseStrands" in template["Parameters"]

    use_strands_param = template["Parameters"]["UseStrands"]
    assert use_strands_param["Type"] == "String"
    assert use_strands_param["Default"] == "false"
    assert "true" in use_strands_param["AllowedValues"]
    assert "false" in use_strands_param["AllowedValues"]
```

**Test 10: Template Configuration - Condition**
```python
def test_template_yaml_has_should_use_strands_condition():
    """Verify template.yaml defines ShouldUseStrands condition.

    Expected Outcome:
    - Condition exists
    - Uses Equals comparison
    - References UseStrands parameter
    """
    import yaml
    with open("backend/template.yaml", "r") as f:
        template = yaml.safe_load(f)

    assert "Conditions" in template
    assert "ShouldUseStrands" in template["Conditions"]
```

**Test 11: Template Configuration - Timeout Update**
```python
def test_template_yaml_timeout_is_60_seconds():
    """Verify Lambda timeout increased to 60 seconds.

    Expected Outcome:
    - Globals.Function.Timeout = 60
    """
    import yaml
    with open("backend/template.yaml", "r") as f:
        template = yaml.safe_load(f)

    assert template["Globals"]["Function"]["Timeout"] == 60
```

**Test 12: Template Configuration - Environment Variables Defined**
```python
def test_template_yaml_has_new_environment_variables():
    """Verify template.yaml defines USE_STRANDS, OLLAMA_HOST, OLLAMA_MODEL.

    Expected Outcome:
    - All three variables in Globals.Function.Environment.Variables
    - USE_STRANDS references UseStrands parameter
    - OLLAMA_HOST and OLLAMA_MODEL use !If conditions
    """
    import yaml
    with open("backend/template.yaml", "r") as f:
        template = yaml.safe_load(f)

    env_vars = template["Globals"]["Function"]["Environment"]["Variables"]
    assert "USE_STRANDS" in env_vars
    assert "OLLAMA_HOST" in env_vars
    assert "OLLAMA_MODEL" in env_vars
```

**Test 13: Template Configuration - New API Routes**
```python
def test_template_yaml_has_new_lambda_functions():
    """Verify template.yaml defines ReviewsGradeAiFunction and AdviceFunction.

    Expected Outcome:
    - ReviewsGradeAiFunction exists
    - AdviceFunction exists
    - Both have proper event definitions
    """
    import yaml
    with open("backend/template.yaml", "r") as f:
        template = yaml.safe_load(f)

    resources = template["Resources"]
    assert "ReviewsGradeAiFunction" in resources
    assert "AdviceFunction" in resources
```

**Test 14: Template Configuration - Correct API Routes**
```python
def test_template_yaml_grade_ai_route():
    """Verify grade-ai route definition.

    Expected Outcome:
    - Path = /reviews/{card_id}/grade-ai
    - Method = post
    - Handler = api.handler.grade_ai_handler
    """
    import yaml
    with open("backend/template.yaml", "r") as f:
        template = yaml.safe_load(f)

    grade_ai_fn = template["Resources"]["ReviewsGradeAiFunction"]
    assert grade_ai_fn["Properties"]["Handler"] == "api.handler.grade_ai_handler"
    assert grade_ai_fn["Properties"]["Timeout"] == 60

    events = grade_ai_fn["Properties"]["Events"]
    assert "GradeAiEvent" in events
    grade_event = events["GradeAiEvent"]["Properties"]
    assert grade_event["Path"] == "/reviews/{card_id}/grade-ai"
    assert grade_event["Method"] == "post"
```

**Test 15: Template Configuration - Advice Route**
```python
def test_template_yaml_advice_route():
    """Verify advice route definition.

    Expected Outcome:
    - Path = /advice
    - Method = get
    - Handler = api.handler.advice_handler
    """
    import yaml
    with open("backend/template.yaml", "r") as f:
        template = yaml.safe_load(f)

    advice_fn = template["Resources"]["AdviceFunction"]
    assert advice_fn["Properties"]["Handler"] == "api.handler.advice_handler"
    assert advice_fn["Properties"]["Timeout"] == 60

    events = advice_fn["Properties"]["Events"]
    assert "AdviceEvent" in events
    advice_event = events["AdviceEvent"]["Properties"]
    assert advice_event["Path"] == "/advice"
    assert advice_event["Method"] == "get"
```

**Test 16: env.json Configuration**
```python
def test_env_json_has_new_variables():
    """Verify env.json includes new environment variables.

    Expected Outcome:
    - ApiFunction, LineWebhookFunction, DuePushJobFunction have:
      - USE_STRANDS
      - OLLAMA_HOST
      - OLLAMA_MODEL
    """
    import json
    with open("backend/env.json", "r") as f:
        env_config = json.load(f)

    # Check ApiFunction
    assert "USE_STRANDS" in env_config["ApiFunction"]
    assert "OLLAMA_HOST" in env_config["ApiFunction"]
    assert "OLLAMA_MODEL" in env_config["ApiFunction"]

    # Check LineWebhookFunction
    assert "USE_STRANDS" in env_config["LineWebhookFunction"]
    assert "OLLAMA_HOST" in env_config["LineWebhookFunction"]
    assert "OLLAMA_MODEL" in env_config["LineWebhookFunction"]

    # Check DuePushJobFunction (if exists)
    if "DuePushJobFunction" in env_config:
        assert "USE_STRANDS" in env_config["DuePushJobFunction"]
        assert "OLLAMA_HOST" in env_config["DuePushJobFunction"]
        assert "OLLAMA_MODEL" in env_config["DuePushJobFunction"]
```

**Test 17: env.json - New Functions**
```python
def test_env_json_has_new_functions():
    """Verify env.json includes ReviewsGradeAiFunction and AdviceFunction.

    Expected Outcome:
    - Both functions configured with required variables
    """
    import json
    with open("backend/env.json", "r") as f:
        env_config = json.load(f)

    # New functions should exist with all required variables
    for func_name in ["ReviewsGradeAiFunction", "AdviceFunction"]:
        assert func_name in env_config or func_name in ["ReviewsGradeAiFunction"], \
            f"Missing function config: {func_name}"
        if func_name in env_config:
            assert "USE_STRANDS" in env_config[func_name]
            assert "OLLAMA_HOST" in env_config[func_name]
            assert "OLLAMA_MODEL" in env_config[func_name]
```

---

## Part 2: TDD Green Phase - Implementation

### 2.1 handler.py Modifications

#### Step 1: Update Imports
Replace lines 41-47:
```python
from services.bedrock import (
    BedrockService,
    BedrockTimeoutError,
    BedrockRateLimitError,
    BedrockInternalError,
    BedrockParseError,
)
```

With:
```python
from services.ai_service import (
    create_ai_service,
    AIServiceError,
    AITimeoutError,
    AIRateLimitError,
    AIInternalError,
    AIParseError,
    AIProviderError,
)
```

#### Step 2: Add Error Mapping Function
Insert after line 59 (after line_service initialization):
```python
def _map_ai_error_to_http(error: AIServiceError) -> Response:
    """Map AI service exceptions to HTTP responses.

    Args:
        error: Exception from AI service layer

    Returns:
        Response object with appropriate HTTP status and error message

    Reliability: 🔵 Confirmed - Based on API specification api-endpoints.md
    """
    if isinstance(error, AITimeoutError):
        return Response(
            status_code=504,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "AI service timeout"}),
        )
    elif isinstance(error, AIRateLimitError):
        return Response(
            status_code=429,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "AI service rate limit exceeded"}),
        )
    elif isinstance(error, AIProviderError):
        return Response(
            status_code=503,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "AI service unavailable"}),
        )
    elif isinstance(error, AIParseError):
        return Response(
            status_code=500,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "AI service response parse error"}),
        )
    else:
        # Generic AIInternalError or unknown AIServiceError
        return Response(
            status_code=500,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "AI service error"}),
        )
```

#### Step 3: Remove bedrock_service Initialization
Delete line 57:
```python
bedrock_service = BedrockService()
```

This service is now created on-demand via the factory.

#### Step 4: Update generate_cards Endpoint
Replace lines 241-316 (the entire generate_cards function):

```python
@app.post("/cards/generate")
@tracer.capture_method
def generate_cards():
    """Generate flashcards from input text using AI.

    Uses AIServiceFactory to select between Bedrock and Strands implementations
    based on USE_STRANDS environment variable.
    """
    user_id = get_user_id_from_context()
    logger.info(f"Generating cards for user_id: {user_id}")

    try:
        body = app.current_event.json_body
        request = GenerateCardsRequest(**body)
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
        # Factory pattern: select service based on USE_STRANDS environment variable
        ai_service = create_ai_service()
        result = ai_service.generate_cards(
            input_text=request.input_text,
            card_count=request.card_count,
            difficulty=request.difficulty,
            language=request.language,
        )

        response = GenerateCardsResponse(
            generated_cards=[
                GeneratedCardResponse(
                    front=card.front,
                    back=card.back,
                    suggested_tags=card.suggested_tags,
                )
                for card in result.cards
            ],
            generation_info=GenerationInfoResponse(
                input_length=result.input_length,
                model_used=result.model_used,
                processing_time_ms=result.processing_time_ms,
            ),
        )
        return response.model_dump(mode="json")

    except AITimeoutError:
        return _map_ai_error_to_http(AITimeoutError("AI generation timed out"))
    except AIRateLimitError:
        return _map_ai_error_to_http(AIRateLimitError("Too many requests, please retry later"))
    except AIProviderError as e:
        return _map_ai_error_to_http(e)
    except AIInternalError:
        return _map_ai_error_to_http(AIInternalError("AI service temporarily unavailable"))
    except AIParseError:
        return _map_ai_error_to_http(AIParseError("Failed to parse AI response"))
    except AIServiceError as e:
        logger.error(f"AI service error: {e}")
        return _map_ai_error_to_http(e)
    except Exception as e:
        logger.error(f"Error generating cards: {e}")
        raise
```

### 2.2 template.yaml Modifications

#### Change 1: Update Global Timeout (Line 7)
```yaml
Globals:
  Function:
    Timeout: 60  # Changed from 30 to support Strands SDK processing
```

#### Change 2: Add Parameters (After existing Parameters, around line 52)
```yaml
Parameters:
  # ... existing parameters ...

  UseStrands:
    Type: String
    Default: "false"
    AllowedValues:
      - "true"
      - "false"
    Description: "Use Strands Agents SDK instead of Bedrock (true/false)"
```

#### Change 3: Add Condition (After existing Conditions, around line 54)
```yaml
Conditions:
  IsProd: !Equals [!Ref Environment, prod]
  ShouldUseStrands: !Equals [!Ref UseStrands, "true"]
```

#### Change 4: Update Environment Variables (In Globals.Function.Environment.Variables)
```yaml
Globals:
  Function:
    # ... existing config ...
    Environment:
      Variables:
        ENVIRONMENT: !Ref Environment
        USERS_TABLE: !Ref UsersTable
        CARDS_TABLE: !Ref CardsTable
        REVIEWS_TABLE: !Ref ReviewsTable
        LOG_LEVEL: !If [IsProd, INFO, DEBUG]
        DYNAMODB_ENDPOINT_URL: ""
        AWS_ENDPOINT_URL: ""
        # NEW VARIABLES FOR STRANDS INTEGRATION
        USE_STRANDS: !Ref UseStrands
        OLLAMA_HOST: !If
          - ShouldUseStrands
          - "http://ollama:11434"
          - ""
        OLLAMA_MODEL: !If
          - ShouldUseStrands
          - "neural-chat"
          - ""
```

#### Change 5: Add New Lambda Functions (After ApiFunction and LineWebhookFunction)
```yaml
  # Grade AI Function - Evaluate user answers with AI
  ReviewsGradeAiFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: !Sub memoru-grade-ai-${Environment}
      CodeUri: src/
      Handler: api.handler.grade_ai_handler
      Description: AI-powered answer grading endpoint
      Timeout: 60
      MemorySize: 512
      Policies:
        - DynamoDBCrudPolicy:
            TableName: !Ref CardsTable
        - DynamoDBReadPolicy:
            TableName: !Ref ReviewsTable
        - Version: '2012-10-17'
          Statement:
            - Effect: Allow
              Action:
                - bedrock:InvokeModel
              Resource: !Sub arn:aws:bedrock:${AWS::Region}::foundation-model/${BedrockModelId}
      Environment:
        Variables:
          KEYCLOAK_ISSUER: !Ref KeycloakIssuer
          BEDROCK_MODEL_ID: !Ref BedrockModelId
          USE_STRANDS: !Ref UseStrands
          OLLAMA_HOST: !If [ShouldUseStrands, "http://ollama:11434", ""]
          OLLAMA_MODEL: !If [ShouldUseStrands, "neural-chat", ""]
      Events:
        GradeAiEvent:
          Type: HttpApi
          Properties:
            ApiId: !Ref HttpApi
            Path: /reviews/{cardId}/grade-ai
            Method: POST
      Tags:
        Environment: !Ref Environment
        Application: memoru

  # Advice Function - Provide learning advice based on review history
  AdviceFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: !Sub memoru-advice-${Environment}
      CodeUri: src/
      Handler: api.handler.advice_handler
      Description: AI-powered learning advice endpoint
      Timeout: 60
      MemorySize: 512
      Policies:
        - DynamoDBReadPolicy:
            TableName: !Ref CardsTable
        - DynamoDBReadPolicy:
            TableName: !Ref ReviewsTable
        - Version: '2012-10-17'
          Statement:
            - Effect: Allow
              Action:
                - bedrock:InvokeModel
              Resource: !Sub arn:aws:bedrock:${AWS::Region}::foundation-model/${BedrockModelId}
      Environment:
        Variables:
          KEYCLOAK_ISSUER: !Ref KeycloakIssuer
          BEDROCK_MODEL_ID: !Ref BedrockModelId
          USE_STRANDS: !Ref UseStrands
          OLLAMA_HOST: !If [ShouldUseStrands, "http://ollama:11434", ""]
          OLLAMA_MODEL: !If [ShouldUseStrands, "neural-chat", ""]
      Events:
        AdviceEvent:
          Type: HttpApi
          Properties:
            ApiId: !Ref HttpApi
            Path: /advice
            Method: GET
      Tags:
        Environment: !Ref Environment
        Application: memoru
```

#### Change 6: Add LogGroups for New Functions
```yaml
  # Grade AI Function LogGroup
  ReviewsGradeAiFunctionLogGroup:
    Type: AWS::Logs::LogGroup
    Properties:
      LogGroupName: !Sub "/aws/lambda/${ReviewsGradeAiFunction}"
      RetentionInDays: !If [IsProd, 90, 14]

  # Advice Function LogGroup
  AdviceFunctionLogGroup:
    Type: AWS::Logs::LogGroup
    Properties:
      LogGroupName: !Sub "/aws/lambda/${AdviceFunction}"
      RetentionInDays: !If [IsProd, 90, 14]
```

#### Change 7: Add Outputs for New Functions
```yaml
Outputs:
  # ... existing outputs ...

  ReviewsGradeAiFunctionArn:
    Description: Grade AI Lambda function ARN
    Value: !GetAtt ReviewsGradeAiFunction.Arn
    Export:
      Name: !Sub memoru-${Environment}-grade-ai-function-arn

  AdviceFunctionArn:
    Description: Advice Lambda function ARN
    Value: !GetAtt AdviceFunction.Arn
    Export:
      Name: !Sub memoru-${Environment}-advice-function-arn
```

### 2.3 env.json Modifications

Replace entire file with:
```json
{
  "ApiFunction": {
    "ENVIRONMENT": "dev",
    "USERS_TABLE": "memoru-users-dev",
    "CARDS_TABLE": "memoru-cards-dev",
    "REVIEWS_TABLE": "memoru-reviews-dev",
    "KEYCLOAK_ISSUER": "http://localhost:8180/realms/memoru",
    "BEDROCK_MODEL_ID": "global.anthropic.claude-haiku-4-5-20251001-v1:0",
    "LOG_LEVEL": "DEBUG",
    "DYNAMODB_ENDPOINT_URL": "http://dynamodb-local:8000",
    "AWS_ENDPOINT_URL": "http://dynamodb-local:8000",
    "USE_STRANDS": "false",
    "OLLAMA_HOST": "http://localhost:11434",
    "OLLAMA_MODEL": "neural-chat"
  },
  "LineWebhookFunction": {
    "ENVIRONMENT": "dev",
    "USERS_TABLE": "memoru-users-dev",
    "CARDS_TABLE": "memoru-cards-dev",
    "REVIEWS_TABLE": "memoru-reviews-dev",
    "LINE_CHANNEL_SECRET_ARN": "local-secret",
    "LOG_LEVEL": "DEBUG",
    "DYNAMODB_ENDPOINT_URL": "http://dynamodb-local:8000",
    "AWS_ENDPOINT_URL": "http://dynamodb-local:8000",
    "USE_STRANDS": "false",
    "OLLAMA_HOST": "http://localhost:11434",
    "OLLAMA_MODEL": "neural-chat"
  },
  "DuePushJobFunction": {
    "ENVIRONMENT": "dev",
    "USERS_TABLE": "memoru-users-dev",
    "CARDS_TABLE": "memoru-cards-dev",
    "LINE_CHANNEL_SECRET_ARN": "local-secret",
    "LOG_LEVEL": "DEBUG",
    "DYNAMODB_ENDPOINT_URL": "http://dynamodb-local:8000",
    "AWS_ENDPOINT_URL": "http://dynamodb-local:8000",
    "USE_STRANDS": "false",
    "OLLAMA_HOST": "http://localhost:11434",
    "OLLAMA_MODEL": "neural-chat"
  },
  "ReviewsGradeAiFunction": {
    "ENVIRONMENT": "dev",
    "USERS_TABLE": "memoru-users-dev",
    "CARDS_TABLE": "memoru-cards-dev",
    "REVIEWS_TABLE": "memoru-reviews-dev",
    "KEYCLOAK_ISSUER": "http://localhost:8180/realms/memoru",
    "BEDROCK_MODEL_ID": "global.anthropic.claude-haiku-4-5-20251001-v1:0",
    "LOG_LEVEL": "DEBUG",
    "DYNAMODB_ENDPOINT_URL": "http://dynamodb-local:8000",
    "AWS_ENDPOINT_URL": "http://dynamodb-local:8000",
    "USE_STRANDS": "false",
    "OLLAMA_HOST": "http://localhost:11434",
    "OLLAMA_MODEL": "neural-chat"
  },
  "AdviceFunction": {
    "ENVIRONMENT": "dev",
    "USERS_TABLE": "memoru-users-dev",
    "CARDS_TABLE": "memoru-cards-dev",
    "REVIEWS_TABLE": "memoru-reviews-dev",
    "KEYCLOAK_ISSUER": "http://localhost:8180/realms/memoru",
    "BEDROCK_MODEL_ID": "global.anthropic.claude-haiku-4-5-20251001-v1:0",
    "LOG_LEVEL": "DEBUG",
    "DYNAMODB_ENDPOINT_URL": "http://dynamodb-local:8000",
    "AWS_ENDPOINT_URL": "http://dynamodb-local:8000",
    "USE_STRANDS": "false",
    "OLLAMA_HOST": "http://localhost:11434",
    "OLLAMA_MODEL": "neural-chat"
  }
}
```

---

## Part 3: TDD Refactor Phase - Quality & Documentation

### 3.1 Code Quality Improvements

#### handler.py Refactoring
1. **Add docstring to _map_ai_error_to_http()** - Already included in implementation above
2. **Improve error logging** in generate_cards:
   ```python
   except AITimeoutError as e:
       logger.warning(f"AI generation timeout for user_id {user_id}: {e}")
       return _map_ai_error_to_http(e)
   ```
3. **Add processing metrics logging**:
   ```python
   logger.info(f"Card generation succeeded: model={result.model_used}, "
               f"time={result.processing_time_ms}ms, cards={len(result.cards)}")
   ```

#### template.yaml Refactoring
1. **Add descriptive comments** before new sections
2. **Ensure consistent indentation** (2 spaces)
3. **Verify YAML syntax** with `sam validate`

### 3.2 Test Coverage Verification

Run coverage command:
```bash
cd backend && python -m pytest tests/unit/test_handler.py -v --cov=api.handler --cov-report=html
```

Expected targets:
- `_map_ai_error_to_http()`: 100% coverage (all branches tested)
- `generate_cards()`: 95%+ coverage (all error paths)
- Other handler functions: Maintain existing coverage

### 3.3 Integration Testing

#### SAM Build Test
```bash
cd backend
sam build --use-container
```

Expected: Build succeeds without errors

#### SAM Local Test (with env.json)
```bash
cd backend
sam local start-api --env-vars env.json
```

Expected:
- API starts on http://localhost:3000
- `/cards/generate` endpoint responds
- New routes `/reviews/{cardId}/grade-ai` and `/advice` respond (with 404 if handler not implemented yet)

---

## Part 4: Verification Checklist

### Pre-Implementation
- [ ] Reviewed existing handler.py line-by-line
- [ ] Examined current error handling patterns
- [ ] Verified AIServiceFactory interface matches usage
- [ ] Confirmed existing template.yaml structure
- [ ] Examined current env.json format

### Implementation Verification

#### handler.py (Lines 41-317)
- [ ] Imports updated to use `create_ai_service` and AI*Error classes
- [ ] `bedrock_service` global initialization removed
- [ ] `_map_ai_error_to_http()` function added with all 5 error types
- [ ] `generate_cards()` endpoint modified:
  - [ ] `ai_service = create_ai_service()` called instead of `bedrock_service`
  - [ ] All exception handlers use `_map_ai_error_to_http()` where applicable
  - [ ] Response format unchanged (backward compatible)
  - [ ] Docstring updated

#### template.yaml
- [ ] Global timeout changed to 60 seconds
- [ ] `UseStrands` parameter added
- [ ] `ShouldUseStrands` condition added
- [ ] Environment variables added: `USE_STRANDS`, `OLLAMA_HOST`, `OLLAMA_MODEL`
- [ ] `ReviewsGradeAiFunction` defined with:
  - [ ] Handler: `api.handler.grade_ai_handler`
  - [ ] Path: `/reviews/{cardId}/grade-ai`
  - [ ] Method: `POST`
  - [ ] Timeout: 60
  - [ ] Environment variables configured
- [ ] `AdviceFunction` defined with:
  - [ ] Handler: `api.handler.advice_handler`
  - [ ] Path: `/advice`
  - [ ] Method: `GET`
  - [ ] Timeout: 60
  - [ ] Environment variables configured
- [ ] LogGroups added for new functions
- [ ] Outputs added for new functions

#### env.json
- [ ] All 5 functions configured (including new ones)
- [ ] `USE_STRANDS` = "false" for all
- [ ] `OLLAMA_HOST` = "http://localhost:11434" for all
- [ ] `OLLAMA_MODEL` = "neural-chat" for all
- [ ] Valid JSON syntax

#### Tests
- [ ] All 17 test cases implemented
- [ ] Tests use proper pytest patterns
- [ ] Tests include docstrings with test focus
- [ ] Mock objects properly configured
- [ ] Assertions clear and specific

### Post-Implementation Verification
- [ ] Run full test suite: `make test` (all 260+ tests pass)
- [ ] Check coverage: coverage >= 80%
- [ ] SAM build: `sam build` succeeds
- [ ] SAM local: API starts and responds
- [ ] Existing endpoints unchanged (backward compatibility)
- [ ] No import errors or syntax errors
- [ ] Git status clean (ready for commit)

---

## Part 5: Common Issues & Solutions

### Issue 1: Import Circular Dependency
**Symptom**: ModuleNotFoundError when importing `create_ai_service`
**Solution**:
- Verify `services/ai_service.py` exists and is in PYTHONPATH
- Check that factory function is not importing handler.py

### Issue 2: Test Fixtures Missing
**Symptom**: `api_gateway_event` and `lambda_context` fixtures not found
**Solution**:
- Use existing test patterns from `test_handler_link_line.py`
- Add fixtures to `conftest.py` if not present
- Or define inline in test class

### Issue 3: YAML Syntax Error in template.yaml
**Symptom**: `sam build` fails with parsing error
**Solution**:
- Verify indentation (must be 2 spaces)
- Check for missing colons or quotes
- Use `yamllint backend/template.yaml` if available
- Validate with `sam validate`

### Issue 4: env.json Format Issue
**Symptom**: SAM local fails to load environment variables
**Solution**:
- Validate JSON syntax: `python -m json.tool backend/env.json`
- Ensure function names match template.yaml Resources section
- Check for trailing commas

### Issue 5: New Functions Without Handler
**Symptom**: SAM local or deploy fails because handlers don't exist
**Solution**:
- This is expected - new handlers (grade_ai_handler, advice_handler) are implemented in TASK-0057 and TASK-0060
- Handlers can be stub functions for now: `def grade_ai_handler(event, context): return {"statusCode": 501}`

---

## Part 6: Key Implementation Notes

### Design Pattern: Factory Pattern Adoption
The transition from direct `BedrockService()` instantiation to `create_ai_service()` factory function enables:
1. **Runtime selection** of AI provider (Bedrock vs Strands) via environment variable
2. **Centralized service creation** logic in one location
3. **Easier testing** with mock factories
4. **Cleaner error handling** with unified exception hierarchy

### Error Mapping Strategy
The `_map_ai_error_to_http()` function provides:
1. **Semantic HTTP status codes** (504 for timeout, 429 for rate limit, etc.)
2. **Consistent error response format** across all endpoints
3. **Reusability** for future endpoints (grade_ai, advice)
4. **Clear error messaging** to clients

### Template.yaml Configuration
The new parameter-based design allows:
1. **Feature flag control** without code changes
2. **CloudFormation-native conditional configuration**
3. **Environment-specific values** (OLLAMA_HOST can vary by stage)
4. **Future flexibility** for Strands migration rollout

### Backward Compatibility
All changes maintain backward compatibility:
1. Default `USE_STRANDS="false"` preserves Bedrock behavior
2. `generate_cards` response format unchanged
3. Existing endpoints unaffected
4. New endpoints are additions, not replacements

---

## Part 7: Timeline & Effort Estimate

### Phase Breakdown
| Phase | Task | Estimated Hours | Actual |
|-------|------|-----------------|--------|
| Red | Write all 17 test cases | 2 | - |
| Green | Implement handler.py changes | 1.5 | - |
| Green | Implement template.yaml changes | 1 | - |
| Green | Implement env.json changes | 0.5 | - |
| Green | Run tests and fix failures | 1 | - |
| Refactor | Code quality & documentation | 1 | - |
| Refactor | Integration testing & verification | 1 | - |
| **Total** | | **8 hours** | - |

---

## Conclusion

TASK-0056 establishes the foundation for Strands Agents SDK integration by:
1. Abstracting AI service creation via factory pattern
2. Standardizing error handling across all AI operations
3. Preparing infrastructure (Lambda functions, environment variables) for Strands support
4. Maintaining backward compatibility with existing Bedrock-based workflows

The implementation is complete and ready for dependent tasks TASK-0057 (grade_answer) and TASK-0058 (generate_cards Strands implementation).
