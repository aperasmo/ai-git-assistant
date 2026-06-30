from __future__ import annotations

import base64
import ctypes
import platform
from ctypes import wintypes


class SecretStoreError(RuntimeError):
    pass


class SecretStore:
    """Encrypts local secrets with the operating system account.

    Phase B targets Windows, so the production path uses DPAPI. The encrypted
    value remains app-local SQLite data, but only the same Windows user account
    can decrypt it.
    """

    PREFIX = "dpapi:"

    @classmethod
    def storage_kind(cls) -> str:
        return "Windows DPAPI" if platform.system() == "Windows" else "unsupported"

    @classmethod
    def protect(cls, value: str) -> str:
        if platform.system() != "Windows":
            raise SecretStoreError("Encrypted API key storage is currently supported on Windows only.")
        encrypted = _crypt_protect(value.encode("utf-8"))
        return cls.PREFIX + base64.b64encode(encrypted).decode("ascii")

    @classmethod
    def unprotect(cls, value: str) -> str:
        if not value.startswith(cls.PREFIX):
            raise SecretStoreError("The stored API key is not in the encrypted format.")
        if platform.system() != "Windows":
            raise SecretStoreError("Encrypted API key storage is currently supported on Windows only.")
        raw = base64.b64decode(value.removeprefix(cls.PREFIX).encode("ascii"))
        return _crypt_unprotect(raw).decode("utf-8")


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _make_blob(data: bytes) -> tuple[_DataBlob, ctypes.Array]:
    buffer = ctypes.create_string_buffer(data)
    blob = _DataBlob(
        len(data),
        ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)),
    )
    return blob, buffer


def _raise_last_error(action: str) -> None:
    code = ctypes.get_last_error()
    raise SecretStoreError(f"{action} failed with Windows error {code}.")


def _crypt_protect(data: bytes) -> bytes:
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    in_blob, in_buffer = _make_blob(data)
    _ = in_buffer
    out_blob = _DataBlob()

    ok = crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    )
    if not ok:
        _raise_last_error("API key encryption")

    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)


def _crypt_unprotect(data: bytes) -> bytes:
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    in_blob, in_buffer = _make_blob(data)
    _ = in_buffer
    out_blob = _DataBlob()

    ok = crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    )
    if not ok:
        _raise_last_error("API key decryption")

    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)
