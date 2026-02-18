"""
Domain intent handler classes extracted from ApplicationCoordinator.

Each class is responsible for one cohesive slice of the command surface:
- RecordingSession    — recording state machine + audio/ASR pipeline
- TranscriptHandlers  — delete / clear / commit-edits
- ProjectHandlers     — create / update / delete / assign
- RefinementHandlers  — SLM refinement pipeline
- SystemHandlers      — config updates + engine restart
"""
