"""Run a Lityra product's API services and Vite frontend without Docker."""
from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import venv
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
BACKEND = PROJECT / "backend"
FRONTEND = PROJECT / "frontend"
PROJECT_NAME = PROJECT.name.removeprefix("Lityra-").lower()
PRODUCT = {"lms": "learn", "hire": "hire"}.get(PROJECT_NAME, PROJECT_NAME)
FRONTEND_PORT = {"learn": 5174, "hire": 5175}.get(PRODUCT, 0)
if not FRONTEND_PORT:
    raise RuntimeError("Place this script in a Lityra-learn or Lityra-hire project")
DEFAULT_PORT_OFFSET = 10_000 if PRODUCT == "hire" else 0
UPSTREAM_ENV = {
    "auth": "AUTH_URL", "candidate": "CANDIDATE_URL", "drive": "DRIVE_URL",
    "questionbank": "QUESTIONBANK_URL", "exam": "EXAM_URL", "submission": "SUBMISSION_URL",
    "anticheat": "ANTICHEAT_URL", "coding": "CODING_URL", "evaluation": "EVALUATION_URL",
    "interview": "INTERVIEW_URL", "result": "RESULT_URL", "notification": "NOTIFY_URL",
    "files": "FILES_URL", "analytics": "ANALYTICS_URL", "audit": "AUDIT_URL",
    "ai_orchestration": "AI_ORCH_URL", "organization": "ORG_URL", "evidence": "EVIDENCE_URL",
    "competency": "COMPETENCY_URL", "decision": "DECISION_URL", "action": "ACTION_URL",
    "recruit_ai": "RECRUIT_AI_URL",
}


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def schema_for(service: str) -> str:
    name = service.replace("-", "_")
    if name in {"coding", "notification", "files", "analytics", "audit", "ai_orchestration", "organization"}:
        return f"{PRODUCT}_{name}"
    if name in {"auth", "storage", "realtime", "graphql", "vault", "cron", "net", "extensions"}:
        return f"lare_{name}"
    return name


def run(command: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    result = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True)
    if result.returncode:
        details = (result.stdout + "\n" + result.stderr).replace(env.get("DATABASE_URL", "\0"), "<DATABASE_URL>")
        print(details[-5000:], file=sys.stderr)
        raise RuntimeError(f"Command failed with exit code {result.returncode}: {command[1] if len(command) > 1 else command[0]}")


def ensure_python() -> Path:
    local = BACKEND / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if local.is_file():
        python = local
    else:
        print("Creating the product Python environment…")
        venv.EnvBuilder(with_pip=True).create(BACKEND / ".venv")
        python = local
    probe_env = os.environ.copy()
    probe_env["PYTHONPATH"] = str(BACKEND / "libs")
    probe = subprocess.run(
        [str(python), "-c", "import flask, sqlalchemy, lare_common"],
        cwd=PROJECT, env=probe_env, capture_output=True, text=True,
    )
    if probe.returncode:
        print("Installing backend dependencies (first run only)…")
        run([str(python), "-m", "pip", "install", "-r", str(BACKEND / "requirements.txt")], cwd=PROJECT, env=probe_env)
        run([str(python), "-m", "pip", "install", str(BACKEND / "libs")], cwd=PROJECT, env=probe_env)
    return python


def load_services() -> list[tuple[str, str, int]]:
    registry = BACKEND / "services.txt"
    if not registry.is_file():
        raise RuntimeError(f"Missing product service registry: {registry}")
    services = []
    for raw in registry.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 3:
            raise RuntimeError(f"Malformed service registry row: {line}")
        name, directory, port = parts
        if not (BACKEND / "services" / directory / "manage.py").is_file():
            raise RuntimeError(f"Registered service is missing: {name}")
        services.append((name, directory, int(port)))
    return services


def free_port(port: int) -> bool:
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def stop_processes(processes: list[tuple[str, subprocess.Popen, object]]) -> None:
    for _, proc, _ in reversed(processes):
        if proc.poll() is None:
            proc.terminate()
    for _, proc, _ in reversed(processes):
        if proc.poll() is None:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--init-db", action="store_true", help="Create/update this product's service tables before starting")
    parser.add_argument("--backend-only", action="store_true", help="Do not start the frontend dev server")
    parser.add_argument("--port-offset", type=int, default=DEFAULT_PORT_OFFSET,
                        help=f"Add this value to every backend registry port (default: {DEFAULT_PORT_OFFSET})")
    args = parser.parse_args()
    if args.port_offset < 0:
        raise RuntimeError("--port-offset must be zero or greater")

    env = os.environ.copy()
    env.update(read_env(PROJECT / ".env"))
    configured_product = env.get("APP_PRODUCT", PRODUCT).lower()
    if configured_product != PRODUCT:
        raise RuntimeError(f"{PROJECT / '.env'} must set APP_PRODUCT={PRODUCT}")
    env.update(APP_PRODUCT=PRODUCT, AUTH_ALLOWED_PRODUCT=PRODUCT, APP_ENV="development", HOST="127.0.0.1")
    if not env.get("DATABASE_URL"):
        raise RuntimeError(f"Set DATABASE_URL in {PROJECT / '.env'} before starting this product")

    services = [(name, directory, port + args.port_offset) for name, directory, port in load_services()]
    if any(port > 65535 for _, _, port in services):
        raise RuntimeError("--port-offset produces a port above 65535")
    service_ports = {name: port for name, _, port in services}
    gateway_port = service_ports.get("gateway", 8000 + args.port_offset)
    ports = [port for _, _, port in services]
    if not args.backend_only:
        ports.append(FRONTEND_PORT)
    busy = [port for port in ports if not free_port(port)]
    if busy:
        raise RuntimeError(f"These local ports are already in use: {', '.join(map(str, busy))}. Stop the other product or service first.")

    python = ensure_python()
    env["PYTHONPATH"] = str(BACKEND / "libs") + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    run_dir = BACKEND / ".run"
    run_dir.mkdir(exist_ok=True)

    if args.init_db:
        for name, directory, port in services:
            if name == "gateway":
                continue
            init_env = env.copy()
            init_env.update(DB_SCHEMA=schema_for(name), SERVICE_NAME=name, PORT=str(port))
            if name == "auth":
                init_env["AUTH_ALLOWED_PRODUCT"] = PRODUCT
            print(f"Initializing {name}…", flush=True)
            run([str(python), "manage.py", "init-db"], cwd=BACKEND / "services" / directory, env=init_env)
        print("Database initialization completed.", flush=True)

    processes: list[tuple[str, subprocess.Popen, object]] = []
    try:
        for name, directory, port in services:
            service_env = env.copy()
            service_env.update(DB_SCHEMA=schema_for(name), SERVICE_NAME=name, PORT=str(port))
            if name == "auth":
                service_env["AUTH_ALLOWED_PRODUCT"] = PRODUCT
            if name == "gateway":
                service_env.update(HOST="127.0.0.1", PORT=str(gateway_port))
                for service_name, env_name in UPSTREAM_ENV.items():
                    if service_name in service_ports:
                        service_env[env_name] = f"http://127.0.0.1:{service_ports[service_name]}"
            if name == "anticheat" and "exam" in service_ports:
                service_env["EXAM_URL"] = f"http://127.0.0.1:{service_ports['exam']}"
            log = (run_dir / f"{name}.log").open("a", encoding="utf-8")
            proc = subprocess.Popen(
                [str(python), "manage.py", "serve"],
                cwd=BACKEND / "services" / directory,
                env=service_env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            processes.append((name, proc, log))
            print(f"Started {name} on :{service_env['PORT']} (log: {log.name})", flush=True)

        if not args.backend_only:
            npm = shutil.which("npm.cmd" if os.name == "nt" else "npm") or shutil.which("npm")
            if not npm:
                raise RuntimeError("Node.js/npm is required for the frontend")
            if not (FRONTEND / "node_modules" / ".bin" / ("vite.cmd" if os.name == "nt" else "vite")).exists():
                print("Installing frontend dependencies (first run only)…", flush=True)
                run([npm, "ci"], cwd=FRONTEND, env=env)
            log = (run_dir / "frontend.log").open("a", encoding="utf-8")
            frontend_env = env.copy()
            frontend_env["VITE_API_TARGET"] = f"http://127.0.0.1:{gateway_port}"
            proc = subprocess.Popen(
                [npm, "run", "dev", "--", "--host", "127.0.0.1"],
                cwd=FRONTEND, env=frontend_env, stdout=log, stderr=subprocess.STDOUT,
            )
            processes.append(("frontend", proc, log))

        gateway_url = f"http://127.0.0.1:{gateway_port}/health"
        for _ in range(60):
            gateway = next((proc for name, proc, _ in processes if name == "gateway"), None)
            if gateway and gateway.poll() is not None:
                raise RuntimeError("Gateway exited during startup; inspect backend/.run/gateway.log")
            try:
                with urllib.request.urlopen(gateway_url, timeout=1) as response:
                    if response.status == 200:
                        break
            except (urllib.error.URLError, TimeoutError, OSError):
                time.sleep(1)
        else:
            raise RuntimeError("Gateway did not become healthy; inspect backend/.run/gateway.log")

        print(f"\n{PRODUCT.title()} API: {gateway_url}", flush=True)
        if not args.backend_only:
            print(f"{PRODUCT.title()} app: http://127.0.0.1:{FRONTEND_PORT}", flush=True)
        print("Keep this terminal open; press Ctrl+C to stop the product.", flush=True)
        while True:
            exited = [(name, proc.returncode) for name, proc, _ in processes if proc.poll() is not None]
            if exited:
                name, code = exited[0]
                raise RuntimeError(f"{name} stopped unexpectedly (exit {code}); see backend/.run/{name}.log")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping product services…", flush=True)
    except Exception as exc:
        print(f"Startup/runtime error: {exc}", file=sys.stderr)
        return 1
    finally:
        stop_processes(processes)
        for _, _, log in processes:
            log.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
