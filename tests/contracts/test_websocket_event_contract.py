from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API_APP = ROOT / "src" / "api" / "app.py"
FRONTEND_EVENTS = ROOT / "frontend" / "src" / "lib" / "events.ts"


def _backend_event_types() -> set[str]:
    tree = ast.parse(API_APP.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "event_types" for target in node.targets):
            continue
        if not isinstance(node.value, ast.List):
            continue
        return {item.value for item in node.value.elts if isinstance(item, ast.Constant) and isinstance(item.value, str)}
    raise AssertionError(f"Could not find event_types in {API_APP}")


def _frontend_event_map_keys() -> set[str]:
    source = FRONTEND_EVENTS.read_text(encoding="utf-8")
    match = re.search(r"export interface WSEventMap \{(?P<body>.*?)\n\}", source, re.S)
    assert match, f"Could not find WSEventMap in {FRONTEND_EVENTS}"
    return set(re.findall(r"^\s*([a-z_]+):", match.group("body"), re.M))


def _frontend_validator_keys() -> set[str]:
    source = FRONTEND_EVENTS.read_text(encoding="utf-8")
    match = re.search(r"export const wsEventValidators:[\s\S]*?= \{(?P<body>.*?)\n\};", source, re.S)
    assert match, f"Could not find wsEventValidators in {FRONTEND_EVENTS}"
    return set(re.findall(r"^\s*([a-z_]+):", match.group("body"), re.M))


def test_frontend_websocket_event_map_covers_backend_bridge() -> None:
    backend_events = _backend_event_types()
    frontend_events = _frontend_event_map_keys()

    assert backend_events - frontend_events == set()


def test_frontend_websocket_validators_cover_event_map() -> None:
    frontend_events = _frontend_event_map_keys()
    validator_events = _frontend_validator_keys()

    assert frontend_events - validator_events == set()
    assert validator_events - frontend_events == set()