"""Provenance helpers (env, git, file hashes) to keep pipeline small."""
import hashlib
import importlib.metadata
import os
import platform
import socket
import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def command_record():
    orig = list(getattr(sys, "orig_argv", sys.argv))
    import shlex

    try:
        shell = shlex.join(orig)
    except (TypeError, ValueError, AttributeError):
        shell = " ".join(orig)
    return {
        "shell": shell,
        "argv": list(sys.argv),
        "orig_argv": orig,
        "cwd": os.getcwd(),
    }


def environment_record():
    dists = sorted(
        f"{d.metadata['Name']}=={d.version}"
        for d in importlib.metadata.distributions()
        if d.metadata["Name"]
    )
    return {
        "python_version": sys.version,
        "python_version_info": list(sys.version_info),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "hostname": socket.gethostname(),
        "distributions": dists,
    }


def git_record(cwd: str):
    def run(args):
        try:
            out = subprocess.run(
                ["git", *args],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError) as e:
            raise RuntimeError(f"git {' '.join(args)} failed: {e}") from e
        if out.returncode != 0:
            raise RuntimeError(
                f"git {' '.join(args)} exited {out.returncode}: {out.stderr.rstrip(chr(10))}"
            )
        return out.stdout.rstrip("\n")

    return {
        "head": run(["rev-parse", "HEAD"]),
        "branch": run(["rev-parse", "--abbrev-ref", "HEAD"]),
        "status_porcelain": run(["status", "--porcelain", "--untracked-files=all"]),
    }


WHITELIST = (
    "src/reliable_alerting/__init__.py",
    "src/reliable_alerting/loading.py",
    "src/reliable_alerting/scoring.py",
    "src/reliable_alerting/splitting.py",
    "src/reliable_alerting/calibration.py",
    "src/reliable_alerting/policy.py",
    "src/reliable_alerting/writing.py",
    "src/reliable_alerting/pipeline.py",
    "src/reliable_alerting/provenance.py",
    "src/reliable_alerting/evidence.py",
    "configs/day01-synthetic.json",
    "tests/test_pipeline.py",
    "tests/test_source.py",
    "tests/test_decisions.py",
    "tests/test_evidence.py",
    "README.md",
    "pyproject.toml",
)


def file_hashes(repo: Path):
    repo = Path(repo)
    repo_resolved = repo.resolve()
    out = {}
    for rel in WHITELIST:
        p = repo / rel
        # refuse symlinks on the target or any parent up to the repo
        cur = p
        while True:
            if cur.is_symlink():
                raise RuntimeError(f"symlink refused: {rel}")
            if cur == repo or cur == cur.parent:
                break
            cur = cur.parent
            try:
                cur.relative_to(repo)
            except ValueError:
                break
        try:
            resolved = p.resolve()
        except OSError as e:
            raise RuntimeError(f"cannot resolve {rel}: {e}") from e
        try:
            resolved.relative_to(repo_resolved)
        except ValueError as e:
            raise RuntimeError(f"path escapes repo: {rel}") from e
        if not p.is_file():
            raise FileNotFoundError(f"required provenance file missing: {rel}")
        try:
            h = hashlib.sha256()
            with open(p, "rb") as fh:
                for chunk in iter(lambda: fh.read(65536), b""):
                    h.update(chunk)
        except OSError as e:
            raise RuntimeError(f"cannot hash {rel}: {e}") from e
        out[rel] = h.hexdigest()
    return out
