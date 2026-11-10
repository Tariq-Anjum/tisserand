"""Bootstrap the repository's tiny Python dependency set without touching system Python."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"
MARKER = "MY_AI_SKILLS_BOOTSTRAPPED"


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def ensure_yaml() -> None:
    # Guard before even testing dependencies; this function can venv/pip/exec.
    from release_guard import guard
    guard(os.environ.get("AI_TOOLS_ROOT", str(ROOT.parent)))
    try:
        import yaml  # noqa: F401
        return
    except ImportError:
        pass

    vp = venv_python()
    if vp.exists():
        check = subprocess.run([str(vp), "-c", "import yaml"], check=False)
        if check.returncode == 0:
            env = os.environ.copy()
            env[MARKER] = "1"
            os.execvpe(str(vp), [str(vp), *sys.argv], env)

    if os.environ.get(MARKER) == "1":
        raise SystemExit(
            "PyYAML is unavailable in the private environment. "
            f"Install it with: {vp} -m pip install -r {ROOT / 'requirements.txt'}"
        )

    if not vp.exists():
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV)])

    try:
        subprocess.check_call([
            str(vp), "-m", "pip", "install", "--disable-pip-version-check",
            "-r", str(ROOT / "requirements.txt"),
        ])
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            "Could not install PyYAML for tisserand. "
            f"The private environment is {VENV}. "
            f"Run '{vp} -m pip install -r {ROOT / 'requirements.txt'}' "
            "when package access is available, then retry."
        ) from exc

    env = os.environ.copy()
    env[MARKER] = "1"
    os.execvpe(str(vp), [str(vp), *sys.argv], env)
