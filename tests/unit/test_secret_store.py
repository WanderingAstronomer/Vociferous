from __future__ import annotations

import subprocess

import pytest

from src.core import secret_store
from src.core.resource_manager import ResourceManager
from src.core.secret_store import (
    SecretStoreUnavailable,
    delete_provider_api_key,
    get_provider_api_key,
    get_secret_backend,
    normalize_provider_api_key,
    provider_api_key_is_valid,
    store_provider_api_key,
)

VALID_GROQ_KEY = "gsk_test_secret_123456789012345678901234567890"


def test_secret_backend_name_is_known() -> None:
    assert get_secret_backend() in {"win32_dpapi", "macos_keychain", "libsecret", "unavailable"}


def test_invalid_provider_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown refinement provider"):
        store_provider_api_key("not-a-provider", "secret")

    with pytest.raises(ValueError, match="Unknown refinement provider"):
        delete_provider_api_key("not-a-provider")


def test_groq_key_validation_rejects_obviously_bad_values() -> None:
    assert provider_api_key_is_valid("groq", VALID_GROQ_KEY) is True
    assert provider_api_key_is_valid("groq", "gsk_test_secret") is False


def test_provider_key_normalization_strips_bearer_prefix() -> None:
    assert normalize_provider_api_key("groq", f"Bearer {VALID_GROQ_KEY}") == VALID_GROQ_KEY


def test_linux_secret_backend_requires_secret_tool(monkeypatch) -> None:
    monkeypatch.setattr(secret_store.sys, "platform", "linux")
    monkeypatch.setattr(secret_store.shutil, "which", lambda _name: None)
    assert get_secret_backend() == "unavailable"

    monkeypatch.setattr(
        secret_store.shutil,
        "which",
        lambda name: "/usr/bin/secret-tool" if name == "secret-tool" else None,
    )
    assert get_secret_backend() == "libsecret"


def test_linux_secret_tool_store_failure_raises_secret_store_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(secret_store.sys, "platform", "linux")
    monkeypatch.setattr(
        secret_store.shutil,
        "which",
        lambda name: "/usr/bin/secret-tool" if name == "secret-tool" else None,
    )

    def fake_run(*_args, **_kwargs):
        raise subprocess.CalledProcessError(returncode=1, cmd=["secret-tool", "store"])

    monkeypatch.setattr(secret_store.subprocess, "run", fake_run)

    with pytest.raises(SecretStoreUnavailable, match="libsecret-tools"):
        store_provider_api_key("groq", VALID_GROQ_KEY)


def test_windows_dpapi_roundtrip(monkeypatch, tmp_path) -> None:
    if get_secret_backend() != "win32_dpapi":
        pytest.skip("DPAPI roundtrip is Windows-only")

    monkeypatch.setattr(ResourceManager, "get_user_config_dir", lambda: tmp_path)

    store_provider_api_key("groq", VALID_GROQ_KEY)

    assert get_provider_api_key("groq") == VALID_GROQ_KEY
    assert delete_provider_api_key("groq") is True
    assert get_provider_api_key("groq") is None
