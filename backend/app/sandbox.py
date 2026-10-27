"""Containerized, resource-constrained execution boundary for generated tests.

Security model: Docker is the boundary. validate_test_code() is only a guardrail
against obviously unwanted generated code; it is NOT a security control.
"""
import ast
import os
import shutil
import stat
import subprocess
import tempfile
import uuid
from pathlib import Path

SANDBOX_IMAGE = os.getenv("SANDBOX_IMAGE", "github-dna-sandbox:latest")
TIMEOUT_SECONDS = int(os.getenv("SANDBOX_TIMEOUT_SEC", "20"))
MAX_OUTPUT_CHARS = 8000
FORBIDDEN_IMPORTS = {"subprocess", "socket", "http", "urllib", "requests", "shutil"}
SKIP_NAMES = {".git", "__pycache__", "venv", ".venv", ".pytest_cache", "test_dna_verification.py"}


class SecurityViolation(Exception):
    pass


def validate_test_code(code: str):
    """Guardrail: valid Python and no obvious network/shell imports. Not a security boundary."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise ValueError(f"Generated test has invalid syntax: {e}")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = alias.name.split(".")[0]
                if mod in FORBIDDEN_IMPORTS:
                    raise SecurityViolation(f"Import of '{mod}' is forbidden in test code")
        elif isinstance(node, ast.ImportFrom):
            mod = (node.module or "").split(".")[0]
            if mod in FORBIDDEN_IMPORTS:
                raise SecurityViolation(f"Import of '{mod}' is forbidden in test code")


def is_docker_available() -> bool:
    try:
        res = subprocess.run(["docker", "info"], capture_output=True, timeout=5)
        return res.returncode == 0
    except Exception:
        return False


def _copy_ignore(dirpath, names):
    """Skip junk, symlinks and special files (fifos, sockets, devices) while copying."""
    skipped = set()
    for name in names:
        full = os.path.join(dirpath, name)
        if name in SKIP_NAMES or os.path.islink(full):
            skipped.add(name)
            continue
        try:
            mode = os.lstat(full).st_mode
        except OSError:
            skipped.add(name)
            continue
        if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            skipped.add(name)
    return skipped


def _remove_container(name: str):
    try:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=15)
    except Exception:
        pass


def _result(status, stdout="", stderr="", exit_code=None, sandboxed=True, applied_patch=False):
    return {
        "status": status,
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": exit_code,
        "sandboxed": sandboxed,
        "applied_patch": applied_patch,
    }


def run_test_in_sandbox(
    repo_path: Path,
    test_code: str,
    patch_file: str | None = None,
    patch_content: str | None = None,
    timeout_sec: int = TIMEOUT_SECONDS,
) -> dict:
    """
    Run a generated test inside a disposable Docker container: no network, read-only
    filesystem and repo mount, all capabilities dropped, non-root user, memory/CPU/pid
    limits, and a hard timeout that removes the container.

    Returns: {status: passed|failed|error|timeout|verification_unavailable,
              stdout, stderr, exit_code, sandboxed, applied_patch}
    """
    validate_test_code(test_code)

    if not is_docker_available():
        return _result(
            "verification_unavailable",
            stderr="Docker daemon is not available to run tests securely.",
            sandboxed=False,
        )

    uid = os.getuid() if hasattr(os, "getuid") else 1000
    gid = os.getgid() if hasattr(os, "getgid") else 1000

    with tempfile.TemporaryDirectory(prefix="dna_sandbox_", ignore_cleanup_errors=True) as tmpdir:
        target_repo = (Path(tmpdir) / "repo").resolve()

        # Copy into a disposable directory so the original is never touched.
        # Symlinks and special files are skipped, never followed.
        try:
            shutil.copytree(repo_path, target_repo, symlinks=False, ignore=_copy_ignore)
        except Exception as e:
            return _result("error", stderr=f"Failed to prepare sandbox directory: {e}", exit_code=1)

        # Apply patch (whole-file replacement), only to an existing regular file inside the copy
        applied_patch = False
        if patch_file and patch_content is not None:
            candidate = target_repo / patch_file
            if candidate.is_symlink():
                return _result("error", stderr=f"Refusing to patch '{patch_file}': symlink.", exit_code=1)
            target_file = candidate.resolve()
            if target_repo not in target_file.parents or not target_file.is_file():
                return _result(
                    "error",
                    stderr=f"Patch target '{patch_file}' is not a file inside the repository; nothing was verified.",
                    exit_code=1,
                )
            try:
                target_file.write_text(patch_content, encoding="utf-8")
                applied_patch = True
            except Exception as e:
                return _result("error", stderr=f"Failed to apply patch to {patch_file}: {e}", exit_code=1)

        # Write the test file (any existing file was already skipped by the copy)
        try:
            (target_repo / "test_dna_verification.py").write_text(test_code, encoding="utf-8")
        except Exception as e:
            return _result("error", stderr=f"Failed to write test file: {e}", exit_code=1,
                           applied_patch=applied_patch)

        container_name = f"dna-{uuid.uuid4().hex[:12]}"
        cmd = [
            "docker", "run", "--rm",
            "--name", container_name,
            "--user", f"{uid}:{gid}",
            "--network", "none",
            "--memory", "256m", "--memory-swap", "256m",
            "--cpus", "1.0",
            "--pids-limit", "64",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--read-only",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
            "-e", "PYTHONDONTWRITEBYTECODE=1",
            "-e", "HOME=/tmp",
            "-e", "PYTHONPATH=/workspace",
            "-v", f"{target_repo}:/workspace:ro",
            "-w", "/workspace",
            SANDBOX_IMAGE,
            "python3", "-m", "pytest", "-v", "-p", "no:cacheprovider",
            "test_dna_verification.py",
        ]

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
            stdout = proc.stdout[:MAX_OUTPUT_CHARS]
            stderr = proc.stderr[:MAX_OUTPUT_CHARS]
            exit_code = proc.returncode
            combined = stdout + stderr

            if exit_code == 0:
                status = "passed"
            elif exit_code == 1:
                status = "failed"
                if "No module named pytest" in combined:
                    status = "error"
                    stderr = "The sandbox image has no pytest installed.\n" + stderr
            elif exit_code == 5:
                status = "error"
                stderr = "No tests were collected, so nothing was verified.\n" + stderr
            elif exit_code in (125, 126, 127):
                status = "error"
                stderr = (f"Docker could not start the container (is image '{SANDBOX_IMAGE}' built?).\n"
                          + stderr)
            else:
                status = "error"

            return _result(status, stdout, stderr, exit_code, applied_patch=applied_patch)

        except subprocess.TimeoutExpired:
            # Killing the docker CLI does not stop the container; remove it explicitly.
            _remove_container(container_name)
            return _result(
                "timeout",
                stderr=f"Execution timed out after {timeout_sec}s and the container was removed.",
                applied_patch=applied_patch,
            )
        except Exception as e:
            _remove_container(container_name)
            return _result("error", stderr=f"Sandbox execution error: {e}", exit_code=1,
                           applied_patch=applied_patch)
