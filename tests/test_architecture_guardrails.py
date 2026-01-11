"""
Architecture Guardrails - Static analysis tests for the frozen interaction core.

These tests enforce the interaction law declared in docs/dev/interaction-core-frozen.md:

1. Law 1: set_state() only in authorized locations
2. Law 2: Feedback layer consumes IntentResult only, never queries state
3. Law 3: Intent vocabulary matches exports

These tests run during CI and MUST fail on architectural violations.
They scan source code directly - no runtime mocking needed.
"""

import ast
import re
from pathlib import Path

import pytest

# Project root for source scanning
PROJECT_ROOT = Path(__file__).parent.parent
SRC_ROOT = PROJECT_ROOT / "src"


class TestSetStateGuardrails:
    """Law 1: set_state() is only called in authorized locations."""
    
    # Authorized patterns for set_state calls
    # Key: source file (relative to SRC_ROOT)
    # Value: description of why it's authorized
    AUTHORIZED_SET_STATE = {
        "ui/components/workspace/workspace.py": "Workspace owns state transitions",
        "ui/components/workspace/header.py": "Header.set_state for visual updates only",
        "ui/components/main_window/main_window.py": "Orchestration privilege (sync_recording_status_from_engine only)",
    }
    
    def test_no_unauthorized_set_state(self) -> None:
        """No file outside the authorized list may call workspace.set_state()."""
        violations: list[str] = []
        
        # Scan all Python files in src/
        for py_file in SRC_ROOT.rglob("*.py"):
            rel_path = py_file.relative_to(SRC_ROOT).as_posix()
            
            # Skip authorized files
            if rel_path in self.AUTHORIZED_SET_STATE:
                continue
            
            # Read and scan for set_state pattern
            content = py_file.read_text(encoding="utf-8")
            
            # Look for .set_state( pattern (method call on object)
            # This catches: workspace.set_state, self.workspace.set_state, etc.
            pattern = r"\.set_state\s*\("
            matches = list(re.finditer(pattern, content))
            
            if matches:
                for match in matches:
                    # Find line number
                    line_num = content[:match.start()].count("\n") + 1
                    violations.append(f"  {rel_path}:{line_num}: {match.group()}")
        
        if violations:
            msg = (
                "ARCHITECTURE VIOLATION: set_state() called outside authorized locations.\n"
                "The interaction law (docs/dev/interaction-core-frozen.md) restricts set_state\n"
                "to workspace.py, header.py, and main_window.py (orchestration only).\n\n"
                "Unauthorized calls found:\n" + "\n".join(violations) + "\n\n"
                "Fix: Migrate this behavior to handle_intent() with an Intent type."
            )
            pytest.fail(msg)
    
    def test_main_window_set_state_only_in_orchestration(self) -> None:
        """MainWindow's set_state calls must only be in sync_recording_status_from_engine."""
        main_window_path = SRC_ROOT / "ui/components/main_window/main_window.py"
        content = main_window_path.read_text(encoding="utf-8")
        
        # Parse into AST to find function locations
        tree = ast.parse(content)
        
        # Find all method definitions and their line ranges
        class MethodFinder(ast.NodeVisitor):
            def __init__(self):
                self.methods: dict[str, tuple[int, int]] = {}
            
            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                end_line = getattr(node, "end_lineno", node.lineno + 100)
                self.methods[node.name] = (node.lineno, end_line)
                self.generic_visit(node)
        
        finder = MethodFinder()
        finder.visit(tree)
        
        # Find all set_state calls
        pattern = r"\.set_state\s*\("
        violations: list[str] = []
        
        for match in re.finditer(pattern, content):
            line_num = content[:match.start()].count("\n") + 1
            
            # Check if this line is within the orchestration method
            method_range = finder.methods.get("sync_recording_status_from_engine")
            if method_range:
                start, end = method_range
                if start <= line_num <= end:
                    continue  # Authorized
            
            violations.append(f"  Line {line_num}: set_state outside orchestration method")
        
        if violations:
            msg = (
                "ARCHITECTURE VIOLATION: MainWindow calls set_state outside orchestration.\n"
                "Only sync_recording_status_from_engine may call set_state.\n"
                "All other state changes must go through intents.\n\n"
                "Violations:\n" + "\n".join(violations)
            )
            pytest.fail(msg)


class TestFeedbackLayerIsolation:
    """Law 2: Feedback layer consumes IntentResult only, never queries state."""
    
    def test_feedback_handler_no_state_queries(self) -> None:
        """IntentFeedbackHandler must not import WorkspaceState or query state."""
        feedback_path = SRC_ROOT / "ui/components/main_window/intent_feedback.py"
        content = feedback_path.read_text(encoding="utf-8")
        
        violations: list[str] = []
        
        # Check for WorkspaceState import
        if "WorkspaceState" in content:
            # Find the line
            for i, line in enumerate(content.splitlines(), 1):
                if "WorkspaceState" in line:
                    violations.append(f"  Line {i}: references WorkspaceState")
        
        # Check for get_state() calls
        if ".get_state()" in content:
            for i, line in enumerate(content.splitlines(), 1):
                if ".get_state()" in line:
                    violations.append(f"  Line {i}: calls get_state()")
        
        # Check for state property access
        state_patterns = [r"\.state\b", r"\._state\b"]
        for pattern in state_patterns:
            for match in re.finditer(pattern, content):
                line_num = content[:match.start()].count("\n") + 1
                violations.append(f"  Line {line_num}: accesses {match.group()}")
        
        if violations:
            msg = (
                "ARCHITECTURE VIOLATION: IntentFeedbackHandler queries workspace state.\n"
                "The feedback layer (Phase 6) must consume IntentResult ONLY.\n"
                "It NEVER inspects workspace state - all information comes from IntentResult.\n\n"
                "Violations:\n" + "\n".join(violations) + "\n\n"
                "Fix: Extract needed information into IntentResult instead of querying state."
            )
            pytest.fail(msg)
    
    def test_feedback_handler_only_imports_from_interaction(self) -> None:
        """Feedback handler should only import intent types from ui.interaction."""
        feedback_path = SRC_ROOT / "ui/components/main_window/intent_feedback.py"
        content = feedback_path.read_text(encoding="utf-8")
        
        violations: list[str] = []
        
        # Check for imports from workspace module
        workspace_import_patterns = [
            r"from\s+ui\.components\.workspace",
            r"import\s+.*workspace",
            r"from\s+\.\.workspace",
        ]
        
        for pattern in workspace_import_patterns:
            for match in re.finditer(pattern, content):
                line_num = content[:match.start()].count("\n") + 1
                violations.append(f"  Line {line_num}: imports from workspace module")
        
        if violations:
            msg = (
                "ARCHITECTURE VIOLATION: IntentFeedbackHandler imports from workspace module.\n"
                "The feedback layer should only import from ui.interaction (intents, results).\n\n"
                "Violations:\n" + "\n".join(violations)
            )
            pytest.fail(msg)


class TestIntentCatalogGuardrails:
    """Law 3: Intent vocabulary is frozen and tracked."""
    
    # Canonical list of intent types from docs/dev/intent-catalog.md
    CATALOGED_INTENTS = {
        "BeginRecordingIntent",
        "StopRecordingIntent",
        "CancelRecordingIntent",
        "ViewTranscriptIntent",
        "EditTranscriptIntent",
        "CommitEditsIntent",
        "DiscardEditsIntent",
        "DeleteTranscriptIntent",
    }
    
    # Supporting types that are also exported
    SUPPORTING_TYPES = {
        "InteractionIntent",  # Base class (not a user intent)
        "IntentSource",  # Enum for intent sources
        "IntentOutcome",  # Result outcome enum
        "IntentResult",  # Result container
    }
    
    def test_intent_catalog_matches_exports(self) -> None:
        """All exported intents must be in the catalog, and vice versa."""
        init_path = SRC_ROOT / "ui/interaction/__init__.py"
        content = init_path.read_text(encoding="utf-8")
        
        # Parse __all__ to find exports
        tree = ast.parse(content)
        
        exports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        if isinstance(node.value, ast.List):
                            for elt in node.value.elts:
                                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                    exports.add(elt.value)
        
        # Filter to just intent types (ending in Intent, excluding base class)
        exported_intents = {e for e in exports if e.endswith("Intent") and e != "InteractionIntent"}
        
        # Check for mismatches
        missing_from_catalog = exported_intents - self.CATALOGED_INTENTS
        missing_from_exports = self.CATALOGED_INTENTS - exported_intents
        
        violations: list[str] = []
        if missing_from_catalog:
            violations.append(
                f"  Exported but not cataloged: {missing_from_catalog}\n"
                "  → Add to docs/dev/intent-catalog.md"
            )
        if missing_from_exports:
            violations.append(
                f"  Cataloged but not exported: {missing_from_exports}\n"
                "  → Remove from docs/dev/intent-catalog.md or add to exports"
            )
        
        if violations:
            msg = (
                "ARCHITECTURE VIOLATION: Intent catalog does not match exports.\n"
                "The catalog (docs/dev/intent-catalog.md) must be kept in sync with\n"
                "the actual exports from ui.interaction.__init__.py.\n\n"
                "Mismatches:\n" + "\n".join(violations) + "\n\n"
                "Fix: Update the catalog or exports to match."
            )
            pytest.fail(msg)
    
    def test_all_exports_accounted_for(self) -> None:
        """All exports must be either cataloged intents or supporting types."""
        init_path = SRC_ROOT / "ui/interaction/__init__.py"
        content = init_path.read_text(encoding="utf-8")
        
        tree = ast.parse(content)
        
        exports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        if isinstance(node.value, ast.List):
                            for elt in node.value.elts:
                                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                    exports.add(elt.value)
        
        expected = self.CATALOGED_INTENTS | self.SUPPORTING_TYPES
        unknown = exports - expected
        
        if unknown:
            msg = (
                "ARCHITECTURE VIOLATION: Unknown types exported from ui.interaction.\n"
                f"Found: {unknown}\n\n"
                "If this is a new intent type:\n"
                "  1. Add to CATALOGED_INTENTS in this test\n"
                "  2. Add to docs/dev/intent-catalog.md\n"
                "  3. Add _apply_ method to workspace.py\n\n"
                "If this is a supporting type:\n"
                "  1. Add to SUPPORTING_TYPES in this test"
            )
            pytest.fail(msg)


class TestStatusBarGuardrails:
    """Optional guardrail: Status bar messages should go through IntentFeedbackHandler."""
    
    def test_no_direct_status_bar_in_workspace(self) -> None:
        """Workspace should not call statusBar() directly."""
        workspace_path = SRC_ROOT / "ui/components/workspace/workspace.py"
        content = workspace_path.read_text(encoding="utf-8")
        
        # Check for statusBar() calls
        pattern = r"statusBar\s*\(\s*\)"
        matches = list(re.finditer(pattern, content))
        
        if matches:
            violations = []
            for match in matches:
                line_num = content[:match.start()].count("\n") + 1
                violations.append(f"  Line {line_num}: statusBar() call")
            
            msg = (
                "ARCHITECTURE VIOLATION: Workspace calls statusBar() directly.\n"
                "User feedback should flow through IntentResult → IntentFeedbackHandler.\n\n"
                "Violations:\n" + "\n".join(violations) + "\n\n"
                "Fix: Add message to IntentResult or use existing intent feedback patterns."
            )
            pytest.fail(msg)


class TestOrchestrationPrivilege:
    """Validate orchestration method respects edit safety."""
    
    def test_orchestration_method_exists(self) -> None:
        """The orchestration method must exist in MainWindow."""
        main_window_path = SRC_ROOT / "ui/components/main_window/main_window.py"
        content = main_window_path.read_text(encoding="utf-8")
        
        has_method = "def sync_recording_status_from_engine" in content
        
        if not has_method:
            pytest.fail(
                "ARCHITECTURE VIOLATION: Orchestration method not found.\n"
                "MainWindow must have sync_recording_status_from_engine\n"
                "for coordinating engine status → UI state transitions."
            )
    
    def test_orchestration_checks_current_state(self) -> None:
        """Orchestration must check current state before set_state (edit safety)."""
        main_window_path = SRC_ROOT / "ui/components/main_window/main_window.py"
        content = main_window_path.read_text(encoding="utf-8")
        
        # Find the orchestration method
        # Look for the pattern where it checks get_state() before set_state()
        has_idle_check = "get_state() == WorkspaceState.IDLE" in content
        has_recording_check = "get_state() == WorkspaceState.RECORDING" in content
        
        if not (has_idle_check and has_recording_check):
            pytest.fail(
                "ARCHITECTURE VIOLATION: Orchestration lacks edit-safety guards.\n"
                "The orchestration method must check current state before transitioning:\n"
                "  - Only IDLE → RECORDING (not from EDITING/VIEWING)\n"
                "  - Only RECORDING → IDLE (not from EDITING/VIEWING)\n\n"
                "This protects users from losing edits when the engine sends status updates."
            )
