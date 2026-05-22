"""Local secret storage for provider API keys."""

from __future__ import annotations

import base64
import ctypes
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Literal

from src.core.resource_manager import ResourceManager

SecretBackend = Literal["win32_dpapi", "macos_keychain", "libsecret", "unavailable"]

_SERVICE = "vociferous"
_VALID_PROVIDERS = frozenset({"lm_studio", "groq"})


class SecretStoreUnavailable(RuntimeError):
    """Raised when the current platform has no supported local secret backend."""


def get_secret_backend() -> SecretBackend:
    """Return the supported secret backend for this host."""
    if sys.platform == "win32":
        return "win32_dpapi"
    if sys.platform == "darwin" and shutil.which("security"):
        return "macos_keychain"
    if shutil.which("secret-tool"):
        return "libsecret"
    return "unavailable"


def store_provider_api_key(provider_id: str, api_key: str) -> None:
    """Store a provider API key in the platform secret backend."""
    provider_id = _validate_provider(provider_id)
    value = validate_provider_api_key(provider_id, api_key)

    backend = get_secret_backend()
    if backend == "win32_dpapi":
        _dpapi_store(provider_id, value)
    elif backend == "macos_keychain":
        _security_store(provider_id, value)
    elif backend == "libsecret":
        _secret_tool_store(provider_id, value)
    else:
        raise SecretStoreUnavailable(
            "No supported local secret store is available. Set the provider API key through an environment variable instead."
        )


def get_provider_api_key(provider_id: str) -> str | None:
    """Load a provider API key from the platform secret backend, if one exists."""
    provider_id = _validate_provider(provider_id)
    backend = get_secret_backend()
    if backend == "win32_dpapi":
        return normalize_provider_api_key(provider_id, _dpapi_get(provider_id))
    if backend == "macos_keychain":
        return normalize_provider_api_key(provider_id, _security_get(provider_id))
    if backend == "libsecret":
        return normalize_provider_api_key(provider_id, _secret_tool_get(provider_id))
    return None


def delete_provider_api_key(provider_id: str) -> bool:
    """Delete a provider API key from the platform secret backend."""
    provider_id = _validate_provider(provider_id)
    backend = get_secret_backend()
    if backend == "win32_dpapi":
        return _dpapi_delete(provider_id)
    if backend == "macos_keychain":
        return _security_delete(provider_id)
    if backend == "libsecret":
        return _secret_tool_delete(provider_id)
    return False


def has_provider_api_key(provider_id: str) -> bool:
    """Return whether a provider key is stored locally."""
    return get_provider_api_key(provider_id) is not None


def store_audio_vault_key(recording_id: str, key: bytes) -> None:
    """Store a per-recording audio encryption key in the platform secret backend."""
    recording_id = _validate_recording_id(recording_id)
    if not key:
        raise ValueError("Audio vault key cannot be empty.")
    value = base64.b64encode(key).decode("ascii")
    backend = get_secret_backend()
    if backend == "win32_dpapi":
        _dpapi_store_audio_key(recording_id, value)
    elif backend == "macos_keychain":
        _security_store_account(_audio_account(recording_id), value)
    elif backend == "libsecret":
        _secret_tool_store_account(_audio_account(recording_id), f"Vociferous audio vault key {recording_id}", value)
    else:
        raise SecretStoreUnavailable("No supported local secret store is available for encrypted audio recordings.")


def get_audio_vault_key(recording_id: str) -> bytes | None:
    """Load a per-recording audio encryption key from the platform secret backend."""
    recording_id = _validate_recording_id(recording_id)
    backend = get_secret_backend()
    if backend == "win32_dpapi":
        value = _dpapi_get_audio_key(recording_id)
    elif backend == "macos_keychain":
        value = _security_get_account(_audio_account(recording_id))
    elif backend == "libsecret":
        value = _secret_tool_get_account(_audio_account(recording_id))
    else:
        return None
    if not value:
        return None
    try:
        return base64.b64decode(value.encode("ascii"))
    except Exception:
        return None


def delete_audio_vault_key(recording_id: str) -> bool:
    """Delete a stored per-recording audio encryption key."""
    recording_id = _validate_recording_id(recording_id)
    backend = get_secret_backend()
    if backend == "win32_dpapi":
        return _dpapi_delete_audio_key(recording_id)
    if backend == "macos_keychain":
        return _security_delete_account(_audio_account(recording_id))
    if backend == "libsecret":
        return _secret_tool_delete_account(_audio_account(recording_id))
    return False


def normalize_provider_api_key(provider_id: str, api_key: str | None) -> str | None:
    """Normalize user-pasted provider API keys without exposing them."""
    _validate_provider(provider_id)
    if api_key is None:
        return None
    value = api_key.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1].strip()
    if value.lower().startswith("bearer "):
        value = value[7:].strip()
    return value or None


def validate_provider_api_key(provider_id: str, api_key: str | None) -> str:
    """Return a normalized API key or raise with a provider-specific validation error."""
    value = normalize_provider_api_key(provider_id, api_key)
    if not value:
        raise ValueError("API key cannot be empty.")
    if provider_id == "groq" and (not value.startswith("gsk_") or len(value) < 32):
        raise ValueError("Groq API key looks invalid. Paste the full key value from Groq; it should start with 'gsk_' and be much longer.")
    return value


def provider_api_key_is_valid(provider_id: str, api_key: str | None) -> bool:
    """Return whether a provider key passes local shape validation."""
    try:
        validate_provider_api_key(provider_id, api_key)
    except ValueError:
        return False
    return True


def _validate_provider(provider_id: str) -> str:
    if provider_id not in _VALID_PROVIDERS:
        raise ValueError(f"Unknown refinement provider: {provider_id}")
    return provider_id


def _account(provider_id: str) -> str:
    return f"refinement:{provider_id}:api_key"


def _audio_account(recording_id: str) -> str:
    return f"audio:{recording_id}:key"


def _validate_recording_id(recording_id: str) -> str:
    if not recording_id or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for ch in recording_id):
        raise ValueError("Invalid recording id.")
    return recording_id


def _secrets_path() -> Path:
    return ResourceManager.get_user_config_dir() / "secrets.json"


def _read_dpapi_store() -> dict[str, object]:
    path = _secrets_path()
    if not path.is_file():
        return {"version": 1, "backend": "win32_dpapi", "providers": {}}
    try:
        data = json.loads(path.read_text("utf-8"))
    except Exception:
        return {"version": 1, "backend": "win32_dpapi", "providers": {}}
    if not isinstance(data, dict):
        return {"version": 1, "backend": "win32_dpapi", "providers": {}}
    data.setdefault("version", 1)
    data.setdefault("backend", "win32_dpapi")
    data.setdefault("providers", {})
    return data


def _write_dpapi_store(data: dict[str, object]) -> None:
    path = _secrets_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, sort_keys=True).encode("utf-8")
    fd, tmp = tempfile.mkstemp(dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)


def _dpapi_store(provider_id: str, api_key: str) -> None:
    store = _read_dpapi_store()
    providers = store.setdefault("providers", {})
    if not isinstance(providers, dict):
        providers = {}
        store["providers"] = providers
    providers[provider_id] = {"api_key": _dpapi_protect(api_key.encode("utf-8"))}
    _write_dpapi_store(store)


def _dpapi_get(provider_id: str) -> str | None:
    store = _read_dpapi_store()
    providers = store.get("providers")
    if not isinstance(providers, dict):
        return None
    entry = providers.get(provider_id)
    if not isinstance(entry, dict):
        return None
    protected = entry.get("api_key")
    if not isinstance(protected, str):
        return None
    try:
        return _dpapi_unprotect(protected).decode("utf-8")
    except Exception:
        return None


def _dpapi_delete(provider_id: str) -> bool:
    store = _read_dpapi_store()
    providers = store.get("providers")
    if not isinstance(providers, dict) or provider_id not in providers:
        return False
    del providers[provider_id]
    _write_dpapi_store(store)
    return True


def _dpapi_store_audio_key(recording_id: str, value: str) -> None:
    store = _read_dpapi_store()
    audio_keys = store.setdefault("audio_vault_keys", {})
    if not isinstance(audio_keys, dict):
        audio_keys = {}
        store["audio_vault_keys"] = audio_keys
    audio_keys[recording_id] = {"key": _dpapi_protect(value.encode("ascii"))}
    _write_dpapi_store(store)


def _dpapi_get_audio_key(recording_id: str) -> str | None:
    store = _read_dpapi_store()
    audio_keys = store.get("audio_vault_keys")
    if not isinstance(audio_keys, dict):
        return None
    entry = audio_keys.get(recording_id)
    if not isinstance(entry, dict):
        return None
    protected = entry.get("key")
    if not isinstance(protected, str):
        return None
    try:
        return _dpapi_unprotect(protected).decode("ascii")
    except Exception:
        return None


def _dpapi_delete_audio_key(recording_id: str) -> bool:
    store = _read_dpapi_store()
    audio_keys = store.get("audio_vault_keys")
    if not isinstance(audio_keys, dict) or recording_id not in audio_keys:
        return False
    del audio_keys[recording_id]
    _write_dpapi_store(store)
    return True


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_ulong), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _dpapi_blob(data: bytes) -> tuple[_DATA_BLOB, ctypes.Array[ctypes.c_ubyte]]:
    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    return _DATA_BLOB(len(data), buffer), buffer


def _dpapi_protect(data: bytes) -> str:
    in_blob, _buffer = _dpapi_blob(data)
    out_blob = _DATA_BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)):
        raise ctypes.WinError()
    try:
        encrypted = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        return base64.b64encode(encrypted).decode("ascii")
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)


def _dpapi_unprotect(value: str) -> bytes:
    encrypted = base64.b64decode(value.encode("ascii"))
    in_blob, _buffer = _dpapi_blob(encrypted)
    out_blob = _DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)


def _security_store(provider_id: str, api_key: str) -> None:
    _security_store_account(_account(provider_id), api_key)


def _security_store_account(account: str, value: str) -> None:
    subprocess.run(
        ["security", "add-generic-password", "-U", "-s", _SERVICE, "-a", account, "-w", value],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _security_get(provider_id: str) -> str | None:
    return _security_get_account(_account(provider_id))


def _security_get_account(account: str) -> str | None:
    result = subprocess.run(
        ["security", "find-generic-password", "-s", _SERVICE, "-a", account, "-w"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _security_delete(provider_id: str) -> bool:
    return _security_delete_account(_account(provider_id))


def _security_delete_account(account: str) -> bool:
    result = subprocess.run(
        ["security", "delete-generic-password", "-s", _SERVICE, "-a", account],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def _secret_tool_store(provider_id: str, api_key: str) -> None:
    _secret_tool_store_account(_account(provider_id), f"Vociferous {provider_id} API key", api_key)


def _secret_tool_store_account(account: str, label: str, value: str) -> None:
    subprocess.run(
        ["secret-tool", "store", "--label", label, "service", _SERVICE, "account", account],
        input=value,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )


def _secret_tool_get(provider_id: str) -> str | None:
    return _secret_tool_get_account(_account(provider_id))


def _secret_tool_get_account(account: str) -> str | None:
    result = subprocess.run(
        ["secret-tool", "lookup", "service", _SERVICE, "account", account],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _secret_tool_delete(provider_id: str) -> bool:
    return _secret_tool_delete_account(_account(provider_id))


def _secret_tool_delete_account(account: str) -> bool:
    result = subprocess.run(
        ["secret-tool", "clear", "service", _SERVICE, "account", account],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    return result.returncode == 0