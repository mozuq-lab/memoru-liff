<!--
SYNC IMPACT REPORT:
Version: Template → 1.0.0
Added Principles: I. Test-Driven Development, II. Security First, III. API Contract Integrity, IV. Performance & Scalability, V. Documentation Excellence
Added Sections: Technology Standards, Development Workflow
Templates Status: ✅ All reviewed - no updates needed
Follow-up TODOs: None
-->

# Memoru LIFF Constitution

## Core Principles

### I. Test-Driven Development (NON-NEGOTIABLE)

TDD MUST be followed: Tests written → User approved → Tests fail → Implementation begins. Red-Green-Refactor cycle strictly enforced. Coverage target: 80%+ for all production code. Integration tests required for API contracts, authentication flows, and AI service interactions.

**Rationale**: Complex multi-component system (React frontend, Python Lambda backend, Keycloak auth, AI services) requires rigorous testing to prevent regressions and ensure reliable user experience with personal learning data.

### II. Security First

All user data MUST be protected through established security patterns. Authentication via Keycloak + OIDC mandatory. Personal learning data requires encryption in transit and at rest. Security reviews mandatory for user-facing features.

**Rationale**: Educational platform handles sensitive user learning data and integrates with LINE platform. Security breaches would destroy user trust and violate privacy expectations.

### III. API Contract Integrity

Backend-Frontend API contracts MUST remain stable. Breaking changes require versioning strategy and migration path. OpenAPI specifications mandatory for all endpoints. Frontend TypeScript types must match backend Pydantic models.

**Rationale**: LIFF environment requires seamless integration between React frontend and Python Lambda backend. Contract breaks cause deployment failures and user experience disruption.

### IV. Performance & Scalability

Response times MUST be <500ms p95 for user actions. AI-generated content loading acceptable up to 3 seconds with progress indicators. DynamoDB queries optimized for single-table design. Lambda cold start mitigation required for user-critical paths.

**Rationale**: Mobile-first LINE users expect instant responsiveness. Spaced repetition requires reliable timing. AWS Lambda + DynamoDB architecture demands performance-conscious design patterns.

### V. Documentation Excellence

All features MUST include: implementation documentation, API documentation, deployment guides. Architectural decisions recorded as ADRs. User scenarios documented with acceptance criteria. Troubleshooting guides required for complex integrations.

**Rationale**: Multi-technology stack (AWS SAM, React LIFF, Keycloak, AI services) requires comprehensive documentation for maintenance, onboarding, and operational support.

## Technology Standards

**Backend Stack**: Python 3.12+, AWS SAM, Lambda Powertools, Pydantic v2, DynamoDB single-table design
**Frontend Stack**: React 18+, TypeScript 5+, LIFF SDK, oidc-client-ts, Tailwind CSS
**Authentication**: Keycloak OIDC + PKCE, JWT tokens, LINE Login integration
**AI Services**: Amazon Bedrock (Claude), structured JSON responses, error handling with fallbacks
**Testing**: pytest (backend), Vitest + Playwright (frontend), E2E with Docker Compose local environment
**Infrastructure**: AWS SAM templates, CloudFormation, parameter-based environment configuration

## Development Workflow

**Task Management**: Tsumiki plugin Kairo workflow with TDD (`/tsumiki:tdd-red` → `/tsumiki:tdd-green` → `/tsumiki:tdd-refactor`) or DIRECT tasks (`/tsumiki:direct-setup` → `/tsumiki:direct-verify`)

**Code Review**: All changes require approval. Constitution compliance verification mandatory. Complex features require architectural review.

**Deployment Pipeline**: Automated CI/CD via GitHub Actions. Staging environment deployment required before production. Database migrations tested in staging first.

**Local Development**: Docker-based local environment (DynamoDB Local + Keycloak) for LINE-independent development and testing.

## Governance

This constitution supersedes all other development practices. Amendment requires:

1. Technical impact assessment
2. Migration plan for existing codebase
3. Documentation updates across all affected templates
4. Team approval and version increment

All PRs/reviews must verify compliance with core principles. Technical complexity must be justified against simplicity principle. Use CLAUDE.md for runtime development guidance aligned with constitution.

**Version**: 1.0.0 | **Ratified**: 2026-02-28 | **Last Amended**: 2026-02-28
