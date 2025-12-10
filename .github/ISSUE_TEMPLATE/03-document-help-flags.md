---
name: "[CREATE] Document user help vs dev help CLI flag structure"
about: "Document the two-tier help system for CLI commands"
title: "[CREATE] Document user help vs dev help CLI flag structure"
labels: documentation, enhancement, cli
assignees: ''
---

## Description

Vociferous should have a two-tier help system to separate user-facing convenience commands from developer/debugging components. This needs to be documented in ARCHITECTURE.md and implemented in the CLI.

## Rationale

### Problem
- End users don't need to see low-level components (decode, vad, condense)
- Developers need access to all components for debugging
- Current help output shows everything (cluttered)

### Solution
Two help flags with different audiences:

## `--help` (User-Facing)

Shows high-level commands for typical use:
- `transcribe` - Main workflow (audio file → transcript)
- `languages` - List supported language codes
- `check` - Verify system prerequisites (ffmpeg, dependencies)

**Example output:**
```bash
$ vociferous --help

Usage: vociferous [OPTIONS] COMMAND

Vociferous - Local-first AI transcription

Commands:
  transcribe  Transcribe audio file to text
  languages   List supported language codes
  check       Verify system prerequisites

Use 'vociferous --dev-help' to see developer commands.
```

## `--dev-help` (Developer-Facing)

Shows all components for manual debugging:
- `decode` - Normalize audio to PCM mono 16kHz
- `vad` - Detect speech boundaries (VAD)
- `condense` - Remove silence using VAD timestamps
- `refine` - Polish transcript grammar/punctuation
- `record` - Capture microphone audio
- Plus all other internal components

**Example output:**
```bash
$ vociferous --dev-help

Usage: vociferous [OPTIONS] COMMAND

Developer Commands (for debugging and manual pipelines):

Audio Components:
  decode     Normalize audio to PCM mono 16kHz
  vad        Detect speech boundaries
  condense   Remove silence using timestamps
  record     Capture microphone audio

Workflow Commands:
  transcribe Main transcription workflow
  refine     Refine transcript text

... (full list)
```

## Documentation Requirements

### 1. Add to ARCHITECTURE.md
- New section: "CLI Design - Two-Tier Help System"
- Explain rationale (UX for users, transparency for developers)
- Show example outputs
- List what goes in each help tier

### 2. Add to README.md
- Show both help flags in usage examples
- Explain when to use each

### 3. Code comments
- Document in CLI module how to categorize commands

## Success Criteria

- [ ] Section added to ARCHITECTURE.md documenting help tiers
- [ ] Clear criteria for what goes in user help vs dev help
- [ ] Example outputs shown in documentation
- [ ] README.md updated with help flag examples
- [ ] Related implementation issue created (separate from docs)

## Related Issues

- Part of: #1 (Rewrite ARCHITECTURE.md)
- Blocks: #15 (Implement help flag system - separate implementation issue)

## Notes

This issue is **documentation-only**. The actual implementation of the help flag system will be tracked in issue #15.
