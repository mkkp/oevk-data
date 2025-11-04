<!--
DOCUMENT METADATA
=================
Title: OpenSpec Standard
Type: Specification
Category: Feature
Status: Implemented
Version: 1.0
Created: 2024-10-01
Last Updated: 2024-10-15
Author: System
Change ID: N/A

Related Documents:
- README.md

Related Code:
- src/etl/

Dependencies:
- DuckDB
- Polars

Keywords: change-specification, feature, implementation

Summary:
Change specification document for feature implementation.

Audience:
Developers, technical leads.
-->

# OpenSpec Standard

**Version**: 1.0.0  
**Last Updated**: 2025-10-13  
**Status**: Active

---

## Table of Contents

1. [Introduction](#introduction)
2. [Core Principles](#core-principles)
3. [Specification Workflow](#specification-workflow)
4. [Document Types](#document-types)
5. [Naming Conventions](#naming-conventions)
6. [Quality Standards](#quality-standards)
7. [Implementation Guide](#implementation-guide)

---

## Introduction

OpenSpec is a specification-driven feature development framework that emphasizes:

- **Business-first thinking**: Define WHAT before HOW
- **User story prioritization**: Incremental, independent delivery
- **Technology-agnostic specifications**: Focus on value, not implementation
- **Test-driven development**: Tests before code
- **Constitution-based governance**: Consistent quality standards

### Philosophy

OpenSpec separates concerns into distinct phases:

1. **Specification** - Business requirements and user needs (WHAT)
2. **Planning** - Technical approach and architecture (HOW)
3. **Tasks** - Actionable implementation steps (DO)
4. **Implementation** - Execution with validation (DELIVER)

---

## Core Principles

### 1. Specification-First Development

All features begin with a technology-agnostic specification that:
- Describes user needs and business value
- Defines measurable success criteria
- Identifies user stories with priorities
- Avoids implementation details

### 2. Independent Testability

Every user story must be:
- Implementable independently
- Testable without other stories
- Deliverable as an MVP increment
- Validated at checkpoints

### 3. User Story Prioritization

Stories are prioritized for incremental delivery:
- **P1**: MVP - Must have for initial launch
- **P2**: Important - Next iteration
- **P3**: Nice to have - Future enhancement

### 4. Technology-Agnostic Success Criteria

Success criteria must be:
- **Measurable**: Specific metrics (time, count, percentage)
- **User-focused**: Outcomes from user/business perspective
- **Verifiable**: Testable without knowing implementation
- **Non-technical**: No frameworks, languages, or tools mentioned

### 5. Constitution-Based Governance

Projects define constitutional principles that:
- Establish quality standards
- Guide technical decisions
- Ensure consistency
- Enable compliance validation

---

## Specification Workflow

### Phase 0: Specification

**Purpose**: Define business requirements and user needs

**Activities**:
1. Extract key concepts from feature description
2. Identify actors, actions, data, constraints
3. Define user stories with priorities (P1, P2, P3)
4. Write functional requirements (testable, measurable)
5. Define success criteria (technology-agnostic)
6. Document edge cases and clarifications
7. Validate specification quality

**Output**: Feature specification document

**Quality Gates**:
- No implementation details present
- All requirements are testable
- Success criteria are measurable
- User stories have independent test criteria
- Maximum 3 critical clarifications needed

### Phase 1: Planning

**Purpose**: Define technical implementation approach

**Activities**:
1. Establish technical context (language, dependencies, platform)
2. Check constitution compliance
3. Research technical unknowns
4. Design data models
5. Define API contracts
6. Create quickstart guide
7. Re-validate constitution compliance

**Output**: Implementation plan, research notes, data models, contracts, quickstart guide

**Quality Gates**:
- All technical unknowns resolved
- Constitution principles satisfied or deviations justified
- Data models support all user stories
- Contracts align with functional requirements

### Phase 2: Task Generation

**Purpose**: Create actionable task list organized by user story

**Activities**:
1. Extract user stories with priorities from specification
2. Generate Setup phase (shared infrastructure)
3. Generate Foundational phase (blocking prerequisites)
4. Generate User Story phases (P1, P2, P3 order)
5. Generate Polish phase (cross-cutting concerns)
6. Identify parallel opportunities
7. Number tasks sequentially
8. Define dependencies and execution order

**Output**: Task breakdown document

**Task Structure**:
```
Phase 1: Setup (shared infrastructure)
Phase 2: Foundational (blocking prerequisites)
Phase 3: User Story 1 (P1) - MVP
Phase 4: User Story 2 (P2)
Phase 5: User Story 3 (P3)
Phase N: Polish (cross-cutting concerns)
```

**Quality Gates**:
- Each user story has complete task set
- Foundational tasks identified correctly
- Parallel tasks marked appropriately
- Dependencies clearly documented

### Phase 3: Implementation

**Purpose**: Execute tasks with tracking and validation

**Activities**:
1. Mark task as in progress
2. Execute implementation
3. Run tests (if applicable)
4. Mark task as completed
5. Validate at checkpoints
6. Report completion per user story

**Output**: Working code with tests

**Quality Gates**:
- Tests pass for completed stories
- Checkpoints validated
- Each story independently functional

---

## Document Types

### 1. Feature Specification

**Purpose**: Define business requirements without implementation details

**Required Sections**:

#### User Scenarios & Testing (mandatory)
- User stories with priorities (P1, P2, P3)
- Independent testability criteria per story
- Acceptance scenarios (Given/When/Then format)
- Edge cases

#### Requirements (mandatory)
- Functional requirements (FR-001, FR-002, ...)
- Non-functional requirements (NFR-001, NFR-002, ...)
- Key entities (if data involved)

#### Success Criteria (mandatory)
- Measurable outcomes (SC-001, SC-002, ...)
- Technology-agnostic metrics
- User-focused measurements

#### Clarifications (as needed)
- Session dates
- Questions and answers
- Decisions made

**Quality Standards**:
- ✅ No implementation details (languages, frameworks, APIs)
- ✅ Focused on user value and business needs
- ✅ Written for non-technical stakeholders
- ✅ All requirements are testable and unambiguous
- ✅ Success criteria are measurable and technology-agnostic

### 2. Implementation Plan

**Purpose**: Define technical implementation approach

**Required Sections**:

#### Summary
- Feature overview
- Technical approach from research

#### Technical Context
- Language/Version
- Primary Dependencies
- Storage (if applicable)
- Testing framework
- Target Platform
- Project Type
- Performance Goals
- Constraints
- Scale/Scope

#### Constitution Check
- List of constitutional principles
- Compliance validation
- Justified deviations (if any)

#### Project Structure
- Documentation layout
- Source code structure
- Structure decision rationale

#### Complexity Tracking
- Only if constitutional violations exist
- Justification for each deviation
- Simpler alternatives considered and rejected

**Quality Standards**:
- ✅ All technical unknowns resolved
- ✅ Constitution compliance validated
- ✅ Structure aligns with project type
- ✅ Complexity deviations justified

### 3. Task Breakdown

**Purpose**: Actionable, dependency-ordered task list

**Required Sections**:

#### Task Format
`[ID] [P?] [Story] Description`
- **[ID]**: Sequential number (T001, T002, ...)
- **[P]**: Parallel flag (different files, no dependencies)
- **[Story]**: User story mapping (US1, US2, US3, ...)
- **Description**: Specific action with file path

#### Phase Structure
1. **Setup**: Shared infrastructure
2. **Foundational**: Blocking prerequisites (MUST complete before any story)
3. **User Story Phases**: One per story in priority order
   - Goal
   - Independent test criteria
   - Tests (if requested)
   - Implementation tasks
   - Checkpoint
4. **Polish**: Cross-cutting concerns

#### Dependencies & Execution Order
- Phase dependencies
- User story dependencies
- Within-story task order
- Parallel opportunities

#### Implementation Strategy
- MVP First (User Story 1 only)
- Incremental Delivery
- Parallel Team Strategy

**Quality Standards**:
- ✅ Each user story has complete task set
- ✅ Foundational phase clearly identified
- ✅ Parallel tasks correctly marked
- ✅ Dependencies explicitly documented
- ✅ Each story independently testable

### 4. Research Notes

**Purpose**: Document technical decisions and alternatives

**Required Sections**:

#### Decision
What was chosen

#### Rationale
Why it was chosen

#### Alternatives Considered
What else was evaluated and why rejected

**Quality Standards**:
- ✅ All technical unknowns resolved
- ✅ Decisions linked to requirements
- ✅ Alternatives documented with reasoning

### 5. Data Model

**Purpose**: Define entities, relationships, and validation rules

**Required Sections**:

#### Entities
- Entity name
- Fields and types
- Relationships to other entities
- Unique constraints

#### Validation Rules
- Field-level validations
- Cross-entity constraints
- Business rules

#### State Transitions
- Valid state changes
- Transition rules
- Invariants

**Quality Standards**:
- ✅ All entities from requirements covered
- ✅ Relationships clearly defined
- ✅ Validation rules testable

### 6. API Contracts

**Purpose**: Define interface specifications

**Format**: OpenAPI, GraphQL schema, or equivalent

**Required Elements**:
- Endpoints/Operations
- Request/Response formats
- Error codes
- Authentication requirements
- Rate limits (if applicable)

**Quality Standards**:
- ✅ Covers all user actions from specification
- ✅ Follows REST/GraphQL standards
- ✅ Error handling defined
- ✅ Security requirements specified

### 7. Quickstart Guide

**Purpose**: Getting started instructions

**Required Sections**:
- Prerequisites
- Installation steps
- Configuration
- First run instructions
- Verification steps

**Quality Standards**:
- ✅ Clear step-by-step instructions
- ✅ Prerequisites explicitly listed
- ✅ Verification criteria included

---

## Naming Conventions

### Feature Identifiers

**Format**: `###-feature-name`
- Example: `001-initial-oevk-transformation`
- Example: `004-cleanup-duplicated-addresses`

### Requirements

**Functional**: `FR-###`
- Example: `FR-001`, `FR-002`

**Non-Functional**: `NFR-###`
- Example: `NFR-001`, `NFR-002`

### Success Criteria

**Format**: `SC-###`
- Example: `SC-001`, `SC-002`

### Tasks

**Format**: `T###`
- Example: `T001`, `T002`

### User Stories

**Format**: `US#`
- Example: `US1`, `US2`, `US3`
- Priority indicated in specification (P1, P2, P3)

### Branches

**Format**: `###-feature-name`
- Matches feature identifier
- Example: `001-initial-oevk-transformation`

---

## Quality Standards

### Specification Quality Checklist

**Content Quality**:
- [ ] No implementation details (languages, frameworks, APIs)
- [ ] Focused on user value and business needs
- [ ] Written for non-technical stakeholders
- [ ] All mandatory sections completed

**Requirement Completeness**:
- [ ] No critical clarifications remain unresolved
- [ ] Requirements are testable and unambiguous
- [ ] Success criteria are measurable
- [ ] Success criteria are technology-agnostic
- [ ] All acceptance scenarios defined
- [ ] Edge cases identified
- [ ] Scope clearly bounded
- [ ] Dependencies and assumptions identified

**Feature Readiness**:
- [ ] All functional requirements have clear acceptance criteria
- [ ] User scenarios cover primary flows
- [ ] Feature meets measurable outcomes
- [ ] No implementation details in specification

### Plan Quality Checklist

**Technical Completeness**:
- [ ] All technical unknowns resolved
- [ ] Language/framework selected with rationale
- [ ] Dependencies identified
- [ ] Storage solution defined (if applicable)
- [ ] Testing approach specified

**Constitution Compliance**:
- [ ] All constitutional principles addressed
- [ ] Violations justified with rationale
- [ ] Simpler alternatives documented

**Structure Clarity**:
- [ ] Project structure documented
- [ ] Source code layout defined
- [ ] Documentation organization clear

### Task Quality Checklist

**Completeness**:
- [ ] All user stories have tasks
- [ ] Foundational phase identified
- [ ] Setup tasks present
- [ ] Polish phase included

**Organization**:
- [ ] Tasks organized by user story
- [ ] Each story independently completable
- [ ] Checkpoints defined
- [ ] Parallel opportunities marked

**Clarity**:
- [ ] Each task has specific file path
- [ ] Dependencies explicitly documented
- [ ] Execution order clear

---

## Implementation Guide

### For Specification Authors

#### Focus on WHAT, not HOW

❌ Bad: "Use PostgreSQL to store user data"  
✅ Good: "System MUST persist user data reliably"

#### Make Requirements Testable

❌ Bad: "System should be fast"  
✅ Good: "System MUST respond within 200ms at p95"

#### Prioritize User Stories

- P1 = MVP (must have for launch)
- P2 = Important (next iteration)
- P3 = Nice to have (future enhancement)

#### Limit Clarifications

- Maximum 3 critical clarifications
- Make informed guesses for non-critical decisions
- Document assumptions

#### Define Independent Testability

- Each user story testable alone
- Clear "Independent Test" criteria per story
- Checkpoints after each story phase

### For Implementation

#### Follow TDD

1. Write tests first
2. Ensure tests fail
3. Implement to pass
4. Refactor

#### Track Tasks

- Mark in_progress before starting
- Mark completed immediately after finishing
- Update progress frequently

#### Complete User Stories

- Finish one story completely before starting next
- Validate at each checkpoint
- Deploy incrementally

#### Maintain Constitution

- Check compliance before and after design
- Justify any deviations
- Document complexity decisions

### For Documentation

#### Keep Specs Updated

- Update spec when requirements change
- Document decisions in Clarifications
- Mark implementation status

#### Link Artifacts

- Cross-reference specs, plans, tasks
- Link to implementation files
- Reference specific line numbers

---

## Best Practices

### Specification Writing

1. **Start with user value**: Why does this feature matter?
2. **Define success first**: How will we know it works?
3. **Use concrete examples**: Given/When/Then scenarios
4. **Avoid technical jargon**: Speak business language
5. **Be specific with metrics**: Numbers, not adjectives

### Planning

1. **Research before deciding**: Evaluate alternatives
2. **Document rationale**: Why this choice over others?
3. **Check constitution**: Align with project principles
4. **Plan for testing**: How will each story be verified?
5. **Consider scale**: Will this work at target volume?

### Task Breakdown

1. **One task, one file**: Enables parallel work
2. **Explicit dependencies**: No hidden prerequisites
3. **Testable increments**: Each task produces verifiable output
4. **Story independence**: Each story stands alone
5. **Clear checkpoints**: Know when stories are done

### Implementation

1. **Tests first**: Red-Green-Refactor cycle
2. **Small commits**: Frequent integration
3. **Story focus**: Complete before moving on
4. **Checkpoint validation**: Verify each story independently
5. **Document decisions**: Update specs with learnings

---

## Common Patterns

### Pattern: MVP-First Delivery

**Problem**: Need to deliver value quickly while building larger feature

**Solution**:
1. Identify User Story 1 (P1) as MVP
2. Complete Setup + Foundational phases
3. Implement only User Story 1
4. Validate independently
5. Deploy/demo
6. Add User Story 2 (P2), then 3 (P3), etc.

**Benefits**:
- Fast time to value
- Early feedback
- Reduced risk
- Incremental complexity

### Pattern: Independent User Stories

**Problem**: Need parallel development or flexible scope

**Solution**:
1. Design each user story to stand alone
2. Define clear boundaries between stories
3. Include independent test criteria
4. Use checkpoints for validation
5. Allow any story to be MVP

**Benefits**:
- Parallel development possible
- Flexible scope management
- Easy story prioritization
- Independent deployment

### Pattern: Foundational Phase

**Problem**: Some infrastructure needed by all stories

**Solution**:
1. Identify truly blocking prerequisites
2. Create Foundational phase (Phase 2)
3. Complete before any story work begins
4. Keep minimal - only what's absolutely needed
5. Story-specific setup goes in story phase

**Benefits**:
- Clear prerequisites
- Parallel story work after foundation
- No duplicate setup tasks
- Explicit blocking relationships

---

## Glossary

**Constitution**: Project governance document defining core principles and quality standards

**Feature**: User-facing capability tracked through specification workflow

**Phase**: Stage in feature development (Specification, Planning, Tasks, Implementation)

**Specification**: Business specification defining WHAT users need (technology-agnostic)

**Plan**: Technical implementation plan defining HOW to build

**Tasks**: Actionable, ordered list of implementation steps

**User Story**: Independent, testable slice of functionality with priority

**MVP**: Minimum Viable Product - typically User Story 1 (P1)

**TDD**: Test-Driven Development - write tests before implementation

**Contract Test**: API contract validation test

**Constitution Check**: Validation that feature complies with project principles

**Independent Testability**: Each user story can be tested without others

**Checkpoint**: Validation point after each user story phase

**[P] Task**: Parallelizable task (different files, no dependencies)

**Foundational Phase**: Blocking prerequisites that must complete before any user story can begin

---

## Version History

**Version 1.0.0** (2025-10-13)
- Initial OpenSpec standard definition
- Established core principles and workflow
- Defined document types and quality standards
- Created implementation guide and best practices

---

**End of OpenSpec Standard**
