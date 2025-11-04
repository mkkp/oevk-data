<!--
DOCUMENT METADATA
=================
Title: Claude AI Assistant Instructions
Type: Guide
Category: AI Configuration
Status: Active
Version: 1.0
Created: 2024-10-01
Last Updated: 2025-10-29
Author: Project Team

Related Documents:
- AGENTS.md (OpenSpec agent instructions)
- README.md

Related Code:
- openspec/ (OpenSpec framework)

Dependencies:
- OpenSpec framework

Keywords: ai-assistant, claude, instructions, openspec, automation, agents

Summary:
Configuration and instructions for Claude AI assistant working on this project. Defines when to use OpenSpec framework for proposals, specifications, and major changes. Instructs AI to consult openspec/AGENTS.md for change management workflow and conventions.

Audience:
Claude AI assistant, developers configuring AI behavior.
-->

<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->