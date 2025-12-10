---
name: "[UPDATE] Add module architecture documentation"
about: "Add comprehensive module architecture documentation to ARCHITECTURE.md"
title: "[UPDATE] Add module architecture documentation"
labels: documentation, architecture
assignees: ''
---

## Description

The current ARCHITECTURE.md focuses primarily on components but lacks comprehensive documentation about the module structure. We need to clearly define what constitutes a module and document all modules in the system.

## Problem

- "Module" is used throughout but never formally defined
- Only `audio` and `engines` modules are documented in detail
- 7 other modules exist but are not documented (`refinement`, `cli`, `app`, `config`, `domain`, `sources`, `gui`)
- Unclear which modules contain CLI-accessible components vs infrastructure

## Required Documentation

### 1. Define "Module" formally

```
A module is a logical collection of related functionality. Not all modules need 
CLI-accessible components - some provide infrastructure (config, domain), 
orchestration (app), or interfaces (cli, gui).
```

### 2. Create comprehensive module table

| Module | Purpose | Contains Components? | Key Responsibilities |
|--------|---------|---------------------|---------------------|
| **audio** | Audio preprocessing | ✅ Yes | Decode, VAD, condense, record |
| **engines** | Speech-to-text transcription | ❌ No* | Canary, Whisper, Voxtral (called by workflows) |
| **refinement** | Text post-processing | ✅ Yes | Grammar/punctuation refinement (Canary LLM pass) |
| **cli** | Command-line interface | ✅ Yes | Typer commands, argument parsing |
| **app** | Workflow orchestration | ❌ No | Pipeline coordination, config resolution |
| **config** | Configuration management | ❌ No | Load/validate settings from files/CLI |
| **domain** | Core types and contracts | ❌ No | Models, exceptions, protocols |
| **sources** | Audio input sources | ❌ No | File readers, microphone capture |
| **gui** | Graphical interface | ❌ No | KivyMD application, screens |

*Note: Engines are not directly CLI-accessible. They are infrastructure called by the `transcribe` workflow.

### 3. Document module boundaries
- What belongs in each module
- What does NOT belong in each module
- How modules interact (audio → engines via preprocessed files)

### 4. Clarify infrastructure vs components
- Not all modules need CLI components
- Some modules provide infrastructure (config, domain, sources)
- Some modules provide orchestration (app)
- Some modules provide interfaces (cli, gui)

## Location in ARCHITECTURE.md

Add new section: "Module Architecture" under "Separation of Concerns"

## Success Criteria

- [ ] "Module" formally defined
- [ ] Table listing all 9 modules with purposes
- [ ] Each module's responsibilities documented
- [ ] Clear indication of which modules contain components
- [ ] Module boundaries and interactions explained
- [ ] Infrastructure vs component distinction clarified

## Related Issues

- Part of: #1 (Rewrite ARCHITECTURE.md)
- Related: #8 (Rename polish to refinement)
