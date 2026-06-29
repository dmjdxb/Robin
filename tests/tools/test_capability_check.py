"""Per-product capability check — the guard against silently shipping a dead tool.

The CI-mode test (registration) is the one that would have caught the office-tools
bug (registered inside try/except → never discovered → never callable).
"""

from __future__ import annotations

import pytest

from tools.capability_check import (
    CapabilityReport,
    audit_required_tools,
    tool_status,
)


def test_audit_classifies_missing_gated_available(monkeypatch):
    # Fake registry: 'good' available, 'keyed' gated (check_fn False), 'ghost' missing.
    class _E:
        def __init__(self, name, check):
            self.name = name
            self.check_fn = check

    entries = {
        "good": _E("good", None),
        "keyed": _E("keyed", lambda: False),
    }
    import tools.capability_check as cc
    monkeypatch.setattr(cc, "_registered_entries", lambda: entries)
    monkeypatch.setattr(cc, "_model_visible", lambda n: True)  # isolate the backend dimension
    import tools.registry as reg
    monkeypatch.setattr(reg, "_check_fn_cached", lambda fn: fn())

    rep = audit_required_tools(["good", "keyed", "ghost"], check_availability=True)
    assert rep.available == ["good"]
    assert rep.gated == ["keyed"]
    assert rep.missing == ["ghost"]
    assert rep.ok is False
    assert "GATED" in rep.summary() and "MISSING" in rep.summary()


def test_invisible_when_registered_but_not_core(monkeypatch):
    """The deliver_artifact bug class: registered + working, but not core → model can't see it."""
    class _E:
        def __init__(self, name):
            self.name = name
            self.check_fn = lambda: True
    import tools.capability_check as cc
    monkeypatch.setattr(cc, "_registered_entries", lambda: {"t": _E("t")})
    monkeypatch.setattr(cc, "_model_visible", lambda n: False)  # not in core
    rep = audit_required_tools(["t"], check_availability=False)  # caught even in CI mode
    assert rep.invisible == ["t"] and not rep.ok
    assert "INVISIBLE" in rep.summary()


def test_registration_mode_ignores_backend(monkeypatch):
    class _E:
        def __init__(self, name, check):
            self.name = name
            self.check_fn = check

    entries = {"keyed": _E("keyed", lambda: False)}
    import tools.capability_check as cc
    monkeypatch.setattr(cc, "_registered_entries", lambda: entries)
    monkeypatch.setattr(cc, "_model_visible", lambda n: True)  # core; isolate the backend dimension
    # registration-only: a registered-but-gated tool counts as OK (CI can't probe keys)
    rep = audit_required_tools(["keyed"], check_availability=False)
    assert rep.ok and rep.available == ["keyed"]


def test_ok_report_summary():
    rep = CapabilityReport(required=["a"], available=["a"])
    assert rep.ok and "OK" in rep.summary()


def test_robin_required_tools_are_registered():
    """CI guard: every tool Robin declares as required MUST be registered (callable).

    This is exactly the check that would have caught build_document/render_check
    being registered inside try/except and silently never discovered.
    """
    from tools.registry import discover_builtin_tools
    discover_builtin_tools()
    from robin.config import load_config
    required = load_config().get("required_tools") or []
    assert required, "Robin should declare a required_tools manifest"
    rep = audit_required_tools(required, check_availability=False)
    assert rep.ok, rep.summary()  # registration-level: all required tools exist in the registry


def test_office_tools_are_in_required():
    """The office builders are Robin's reason-for-being — guard them explicitly."""
    from robin.config import load_config
    required = set(load_config().get("required_tools") or [])
    for t in ("build_document", "build_presentation", "render_check"):
        assert t in required, f"{t} should be a required capability for the document coworker"
