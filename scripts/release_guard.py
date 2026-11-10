"""Legacy writers are prohibited on release layouts, under the same lock."""
import fcntl
import os
from pathlib import Path

# Keep the lock fd alive until process exit (or inherit shell guard fd9).
_LOCK_FD = None

def guard(runtime):
    global _LOCK_FD
    runtime = Path(runtime)
    lock = runtime / ".activation.lock"
    if not runtime.is_dir() or runtime.is_symlink() or lock.is_symlink():
        raise SystemExit("writer: explicit real AI_TOOLS_ROOT directory required")
    inherited = False
    try:
        inherited = os.path.samestat(os.fstat(9), lock.stat())
    except OSError:
        pass
    if _LOCK_FD is not None:
        inherited = os.path.samestat(os.fstat(_LOCK_FD), lock.stat())
    if not inherited:
        fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        if fd != 9:
            os.dup2(fd, 9, inheritable=True)
            os.close(fd)
        else:
            os.set_inheritable(9, True)
    _LOCK_FD = 9
    try:
        fcntl.flock(_LOCK_FD, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit("writer: activation lock busy")
    if (runtime / "skills/current").exists() or (runtime / "skills/current").is_symlink() or (runtime / "skills/releases").is_dir() or (runtime / ".activation/transaction").is_dir() or (runtime / ".activation/preparing").is_dir():
        raise SystemExit("writer: release layout active; legacy writer prohibited; use the owner-gated release transaction")
    if (runtime / "skills").is_symlink() or (runtime / "skills/installed").is_symlink():
        raise SystemExit("writer: indirect skills layout refused")
