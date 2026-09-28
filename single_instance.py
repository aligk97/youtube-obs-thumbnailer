from __future__ import annotations

import ctypes
import ctypes.wintypes
import hashlib
import os
import tempfile
from pathlib import Path


ERROR_ALREADY_EXISTS = 183


def make_instance_name(prefix: str, identity_path: str | os.PathLike[str]) -> str:
    identity = str(Path(identity_path).resolve()).lower()
    digest = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:16]
    safe_prefix = "".join(ch for ch in prefix if ch.isalnum() or ch in "-_")
    if os.name == "nt":
        return f"Local\\{safe_prefix}-{digest}"
    return f"{safe_prefix}-{digest}"


class SingleInstance:
    def __init__(self, name: str) -> None:
        self.name = name
        self._handle: int | None = None
        self._fallback_fd: int | None = None
        self._fallback_path: Path | None = None

    def acquire(self) -> bool:
        if os.name == "nt":
            return self._acquire_windows()
        return self._acquire_lock_file()

    def release(self) -> None:
        if os.name == "nt":
            if self._handle:
                kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
                close_handle = kernel32.CloseHandle
                close_handle.argtypes = [ctypes.wintypes.HANDLE]
                close_handle.restype = ctypes.wintypes.BOOL
                close_handle(self._handle)
                self._handle = None
            return

        if self._fallback_fd is not None:
            os.close(self._fallback_fd)
            self._fallback_fd = None
        if self._fallback_path:
            try:
                self._fallback_path.unlink()
            except FileNotFoundError:
                pass
            self._fallback_path = None

    def __enter__(self) -> "SingleInstance":
        if not self.acquire():
            raise RuntimeError("Another instance is already running.")
        return self

    def __exit__(self, *_exc: object) -> None:
        self.release()

    def _acquire_windows(self) -> bool:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_mutex = kernel32.CreateMutexW
        create_mutex.argtypes = [
            ctypes.c_void_p,
            ctypes.wintypes.BOOL,
            ctypes.wintypes.LPCWSTR,
        ]
        create_mutex.restype = ctypes.wintypes.HANDLE

        ctypes.set_last_error(0)
        handle = create_mutex(None, False, self.name)
        last_error = ctypes.get_last_error()
        if not handle:
            raise ctypes.WinError(last_error)

        if last_error == ERROR_ALREADY_EXISTS:
            close_handle = kernel32.CloseHandle
            close_handle.argtypes = [ctypes.wintypes.HANDLE]
            close_handle.restype = ctypes.wintypes.BOOL
            close_handle(handle)
            return False

        self._handle = handle
        return True

    def _acquire_lock_file(self) -> bool:
        safe_name = self.name.replace("\\", "_").replace("/", "_").replace(":", "_")
        lock_path = Path(tempfile.gettempdir()) / f"{safe_name}.lock"
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
        except FileExistsError:
            return False

        os.write(fd, str(os.getpid()).encode("ascii", errors="ignore"))
        self._fallback_fd = fd
        self._fallback_path = lock_path
        return True
