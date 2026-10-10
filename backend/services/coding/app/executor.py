"""Code execution abstraction — multi-language judge.

Languages: python, javascript (node), java (javac+java), cpp (g++). Each entry
declares how to write, (optionally) compile, run, and report the toolchain
version. Compilation logs and runtime stderr are captured separately.

Isolation:
* `SubprocessExecutor` (dev): separate process + hard wall-clock timeout. No
  strong isolation.
* `SandboxedExecutor` (prod): wraps BOTH compile and run in nsjail/bubblewrap
  (network-off, seccomp, rlimits, read-only rootfs).

A missing toolchain (e.g. no javac on the host) yields a clear
"toolchain unavailable" result rather than a crash — so Python/JS run anywhere
and Java/C++ light up wherever the compilers are installed.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RunResult:
    stdout: str
    stderr: str
    exit_code: int | None
    time_ms: int
    timed_out: bool
    compile_log: str = ""
    compile_failed: bool = False
    oom: bool = False


def _rlimit_preexec(mem_mb: int, cap_as: bool = True):
    """POSIX preexec that caps address space (RLIMIT_AS) so runaway solutions get
    killed instead of exhausting the host. No-op on Windows (no `resource`).

    ``cap_as=False`` skips the address-space cap (kept for Node/V8, which
    reserves a huge virtual region that RLIMIT_AS would abort); the CPU cap
    still applies and the JS heap is bounded via ``--max-old-space-size``."""
    try:
        import resource  # POSIX only
    except Exception:  # noqa: BLE001
        return None

    def _apply():
        cap = mem_mb * 1024 * 1024
        try:
            if cap_as:
                resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
            resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
        except Exception:  # noqa: BLE001
            pass

    return _apply


# Per-language toolchain. {file, compile?, run, version, bin}
def _langs() -> dict[str, dict]:
    return {
        "python": {
            "file": "main.py", "bin": sys.executable,
            "run": [sys.executable, "-I", "main.py"],
            "version": [sys.executable, "--version"],
        },
        "javascript": {
            "file": "main.js", "bin": "node",
            # RLIMIT_AS is skipped for node (see run()); bound the JS heap here.
            "run": ["node", "--max-old-space-size=256", "main.js"],
            "version": ["node", "--version"],
        },
        "java": {
            "file": "Main.java", "bin": "javac",
            "compile": ["javac", "Main.java"],
            # RLIMIT_AS is skipped for the JVM (see run()); bound heap + code
            # cache with flags instead so it initialises under memory limits.
            "run": ["java", "-Xmx256m", "-XX:ReservedCodeCacheSize=64m", "Main"],
            "version": ["javac", "-version"],
        },
        "cpp": {
            "file": "main.cpp", "bin": "g++",
            "compile": ["g++", "-O2", "-std=c++17", "-o", "prog", "main.cpp"],
            "run": [os.path.join(".", "prog")], "version": ["g++", "--version"],
        },
        "c": {
            "file": "main.c", "bin": "gcc",
            "compile": ["gcc", "-O2", "-std=c11", "-o", "prog", "main.c", "-lm"],
            "run": [os.path.join(".", "prog")], "version": ["gcc", "--version"],
        },
    }


class Executor:
    SUPPORTED = {"python", "javascript", "java", "cpp", "c"}

    def run(self, language: str, code: str, stdin: str, timeout_sec: int) -> RunResult:
        raise NotImplementedError

    def language_versions(self) -> dict[str, str | None]:
        out = {}
        for name, spec in _langs().items():
            if shutil.which(spec["bin"]):
                try:
                    p = subprocess.run(spec["version"], capture_output=True, timeout=5)
                    out[name] = (p.stdout or p.stderr).decode("utf-8", "replace").strip().splitlines()[0]
                except Exception:  # noqa: BLE001
                    out[name] = "installed"
            else:
                out[name] = None
        return out


class _BaseRunner(Executor):
    """Shared compile/run driver; subclasses only provide the sandbox wrap."""

    def _wrap(self, workdir: str, argv: list[str]) -> list[str]:
        return argv  # dev: no wrapping

    @staticmethod
    def _execution_env(workdir: str) -> dict[str, str]:
        """Pass only non-secret runtime settings to untrusted code/toolchains."""
        if os.name == "nt":
            env = {k: os.environ[k] for k in ("SYSTEMROOT", "WINDIR") if k in os.environ}
            env.update({"PATH": os.environ.get("PATH", os.defpath),
                        "TEMP": workdir, "TMP": workdir, "HOME": workdir})
            return env
        env = {"PATH": os.pathsep.join((os.path.join(sys.prefix, "bin"), os.defpath)),
               "HOME": workdir, "TMPDIR": workdir, "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
        return env

    def run(self, language: str, code: str, stdin: str, timeout_sec: int,
            mem_mb: int = 256) -> RunResult:
        spec = _langs().get(language)
        if not spec:
            return RunResult("", f"language '{language}' unsupported", None, 0, False)
        if not shutil.which(spec["bin"]):
            return RunResult("", f"toolchain '{spec['bin']}' not available on this host",
                             None, 0, False)
        # Node/V8 and the JVM both reserve a large virtual region that RLIMIT_AS
        # would abort, so skip the address-space cap for them (heap bounded via
        # runtime flags); the CPU cap and wall-clock timeout still apply.
        preexec = _rlimit_preexec(mem_mb, cap_as=language not in ("javascript", "java"))

        with tempfile.TemporaryDirectory() as d:
            (Path(d) / spec["file"]).write_text(code, encoding="utf-8")
            clean_env = self._execution_env(d)

            # compile step (java/cpp)
            compile_log = ""
            if "compile" in spec:
                try:
                    cp = subprocess.run(self._wrap(d, spec["compile"]), cwd=d,
                                        capture_output=True, timeout=max(timeout_sec, 15),
                                        env=clean_env)
                    compile_log = cp.stderr.decode("utf-8", "replace")
                    if cp.returncode != 0:
                        return RunResult("", "Compilation failed", cp.returncode, 0,
                                         False, compile_log=compile_log, compile_failed=True)
                except subprocess.TimeoutExpired:
                    return RunResult("", "Compilation timed out", None, 0, True,
                                     compile_log="timeout", compile_failed=True)

            # run step
            start = time.perf_counter()
            try:
                # Inherit the full environment (Windows executables need
                # SYSTEMROOT etc.); the SandboxedExecutor's wrap provides the
                # real isolation + clean env inside nsjail/bubblewrap in prod.
                # preexec_fn (POSIX) applies the RLIMIT_AS memory cap.
                kw = {"preexec_fn": preexec} if preexec else {}
                proc = subprocess.run(
                    self._wrap(d, spec["run"]), input=stdin.encode("utf-8"),
                    capture_output=True, timeout=timeout_sec, cwd=d,
                    env=clean_env, **kw,
                )
                ms = int((time.perf_counter() - start) * 1000)
                err = proc.stderr.decode("utf-8", "replace")
                # RLIMIT_AS breach commonly surfaces as MemoryError / bad_alloc / SIGKILL.
                oom = proc.returncode not in (0, None) and (
                    "MemoryError" in err or "bad_alloc" in err or proc.returncode == -9)
                return RunResult(proc.stdout.decode("utf-8", "replace"), err,
                                 proc.returncode, ms, False, compile_log=compile_log, oom=oom)
            except subprocess.TimeoutExpired:
                ms = int((time.perf_counter() - start) * 1000)
                return RunResult("", "Time limit exceeded", None, ms, True,
                                 compile_log=compile_log)


class SubprocessExecutor(_BaseRunner):
    """Dev executor — no OS sandbox."""


class SandboxedExecutor(_BaseRunner):
    """Production executor — wraps compile + run in nsjail/bubblewrap."""

    def __init__(self, mem_mb: int = 256):
        self.mem_mb = mem_mb
        self.nsjail = shutil.which("nsjail")
        self.bwrap = shutil.which("bwrap")
        if not (self.nsjail or self.bwrap):
            raise RuntimeError("no OS sandbox (nsjail/bwrap) available")

    def _wrap(self, workdir: str, argv: list[str]) -> list[str]:
        if self.nsjail:
            return [self.nsjail, "-Mo", "--quiet", "--disable_proc", "--iface_no_lo",
                    "--rlimit_as", str(self.mem_mb), "--rlimit_cpu", "10", "--cwd", workdir,
                    "--bindmount_ro", "/usr", "--bindmount", f"{workdir}:{workdir}", "--", *argv]
        return [self.bwrap, "--unshare-all", "--die-with-parent", "--new-session",
                "--clearenv", "--setenv", "PATH",
                os.pathsep.join((os.path.join(sys.prefix, "bin"), os.defpath)),
                "--setenv", "HOME", workdir, "--setenv", "TMPDIR", workdir,
                "--setenv", "LANG", "C.UTF-8", "--setenv", "LC_ALL", "C.UTF-8",
                "--ro-bind", "/usr", "/usr", "--ro-bind", "/lib", "/lib",
                "--ro-bind", "/lib64", "/lib64",
                # /etc resolves update-alternatives symlinks (javac/java) and
                # provides CA certs / JVM config; sys.prefix mounts the Python
                # venv so the interpreter is reachable inside the sandbox.
                "--ro-bind", "/etc", "/etc",
                "--ro-bind", sys.prefix, sys.prefix,
                "--proc", "/proc", "--dev", "/dev",
                "--bind", workdir, workdir, "--chdir", workdir, "--", *argv]


class DisabledExecutor(Executor):
    def run(self, language, code, stdin, timeout_sec):  # noqa: ANN001
        return RunResult("", "execution disabled", None, 0, False)


def build_executor(mode: str) -> Executor:
    production = os.getenv("APP_ENV") == "production"
    if mode == "disabled":
        return DisabledExecutor()
    if mode == "subprocess":
        if production:
            raise RuntimeError("unsandboxed code execution is forbidden in production")
        return SubprocessExecutor()
    if mode == "sandbox":
        try:
            return SandboxedExecutor()
        except RuntimeError:
            if production:
                raise
            return SubprocessExecutor()
    raise ValueError(f"unsupported executor mode: {mode}")
