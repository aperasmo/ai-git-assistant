from __future__ import annotations

import base64
import ctypes
import getpass
import hashlib
import hmac
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
    PORTABLE_PREFIX = "portable-v1:"

    @classmethod
    def storage_kind(cls) -> str:
        return "Windows DPAPI" if platform.system() == "Windows" else "Portable local encryption"

    @classmethod
    def protect(cls, value: str) -> str:
        if platform.system() != "Windows":
            return cls.PORTABLE_PREFIX + _portable_encrypt(value)
        encrypted = _crypt_protect(value.encode("utf-8"))
        return cls.PREFIX + base64.b64encode(encrypted).decode("ascii")

    @classmethod
    def unprotect(cls, value: str) -> str:
        if value.startswith(cls.PORTABLE_PREFIX):
            return _portable_decrypt(value.removeprefix(cls.PORTABLE_PREFIX))
        if not value.startswith(cls.PREFIX):
            raise SecretStoreError("The stored secret is not in a supported encrypted format.")
        if platform.system() != "Windows":
            raise SecretStoreError("Windows DPAPI secrets can only be decrypted on Windows.")
        raw = base64.b64decode(value.removeprefix(cls.PREFIX).encode("ascii"))
        return _crypt_unprotect(raw).decode("utf-8")


def _portable_key() -> bytes:
    material = "|".join(
        [
            "ai-git-assistant",
            platform.system(),
            platform.node(),
            getpass.getuser(),
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).digest()


def _portable_keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    chunks: list[bytes] = []
    counter = 0
    while sum(len(chunk) for chunk in chunks) < length:
        counter_bytes = counter.to_bytes(4, "big")
        chunks.append(hmac.new(key, nonce + counter_bytes, hashlib.sha256).digest())
        counter += 1
    return b"".join(chunks)[:length]


def _portable_encrypt(value: str) -> str:
    key = _portable_key()
    nonce = hashlib.sha256(value.encode("utf-8") + key).digest()[:16]
    plain = value.encode("utf-8")
    stream = _portable_keystream(key, nonce, len(plain))
    cipher = bytes(a ^ b for a, b in zip(plain, stream, strict=True))
    signature = hmac.new(key, nonce + cipher, hashlib.sha256).digest()[:16]
    return base64.b64encode(nonce + signature + cipher).decode("ascii")


def _portable_decrypt(payload: str) -> str:
    key = _portable_key()
    try:
        raw = base64.b64decode(payload.encode("ascii"))
    except ValueError as exc:
        raise SecretStoreError("The stored portable secret is not valid base64.") from exc
    if len(raw) < 32:
        raise SecretStoreError("The stored portable secret is incomplete.")

    nonce = raw[:16]
    signature = raw[16:32]
    cipher = raw[32:]
    expected = hmac.new(key, nonce + cipher, hashlib.sha256).digest()[:16]
    if not hmac.compare_digest(signature, expected):
        raise SecretStoreError("The stored portable secret cannot be verified for this user.")

    stream = _portable_keystream(key, nonce, len(cipher))
    plain = bytes(a ^ b for a, b in zip(cipher, stream, strict=True))
    return plain.decode("utf-8")


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
