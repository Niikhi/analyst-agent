import argparse
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass

from analyst_agent.config import get_settings

COLOURS = {"mcp": "\033[36m", "api": "\033[35m", "ui": "\033[32m"}
RESET = "\033[0m"


@dataclass
class Service:
    name: str
    command: list[str]
    port: int
    ready_message: str


def services() -> dict[str, Service]:
    settings = get_settings()
    api_port = _port_of(settings.api_url, 8000)
    return {
        "mcp": Service(
            name="mcp",
            command=[sys.executable, "-m", "analyst_agent.mcp_server"],
            port=settings.mcp_port,
            ready_message=f"MCP server  {settings.resolved_mcp_url}",
        ),
        "api": Service(
            name="api",
            command=[
                sys.executable, "-m", "uvicorn", "analyst_agent.api.main:app",
                "--port", str(api_port), "--log-level", "warning",
            ],
            port=api_port,
            ready_message=f"REST API    {settings.api_url}/docs",
        ),
        "ui": Service(
            name="ui",
            command=[
                sys.executable, "-m", "streamlit", "run",
                "src/analyst_agent/ui/app.py",
                "--server.port", "8501",
                "--server.headless", "true",
                "--browser.gatherUsageStats", "false",
            ],
            port=8501,
            ready_message="Streamlit   http://localhost:8501",
        ),
    }


def _port_of(url: str, fallback: int) -> int:
    tail = url.rsplit(":", 1)[-1].split("/")[0]
    return int(tail) if tail.isdigit() else fallback


def port_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex((host, port)) == 0


def wait_for_port(port: int, timeout: float = 45.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if port_open(port):
            return True
        time.sleep(0.3)
    return False


def pump(service: Service, process: subprocess.Popen) -> None:
    colour = COLOURS.get(service.name, "")
    for raw in process.stdout:
        line = raw.rstrip()
        if line:
            print(f"{colour}[{service.name}]{RESET} {line}", flush=True)


def preflight() -> list[str]:
    settings = get_settings()
    problems: list[str] = []

    if not settings.analyst_db_url:
        problems.append("ANALYST_DB_URL is not set. Copy .env.example to .env and fill it in.")
    else:
        try:
            from sqlalchemy import create_engine, text

            engine = create_engine(settings.analyst_db_url, pool_pre_ping=True)
            with engine.connect() as conn:
                companies = conn.execute(text("SELECT count(*) FROM companies")).scalar_one()
            if not companies:
                problems.append(
                    "The database has no companies. Load it with:\n"
                    '      psql -U postgres -d "analyst-agent" -f db/seed/analyst-agent-data.sql'
                )
        except Exception as exc:
            problems.append(
                f"Cannot query Postgres as analyst_ro ({type(exc).__name__}). "
                "Check the database is running and db/schema/*.sql have been applied.\n"
                f"      {str(exc).splitlines()[0][:150]}"
            )

    try:
        from analyst_agent.agent.aws import session

        credentials = session().get_credentials()
        if credentials is None:
            raise RuntimeError("no credentials resolved")
        credentials.get_frozen_credentials()
    except Exception:
        profile = settings.aws_profile or "default"
        problems.append(
            f"AWS credentials for profile '{profile}' are missing or expired, so "
            f"/ask will return 503. Sign in with:"
            + f"{chr(10)}      aws sso login --profile {profile}"
        )
    return problems


def run(names: list[str], skip_checks: bool) -> int:
    registry = services()
    chosen = [registry[n] for n in names]

    if not skip_checks:
        problems = preflight()
        blocking = [p for p in problems if "aws sso login" not in p]
        for problem in problems:
            marker = "ERROR" if problem in blocking else "warn "
            print(f"  {marker}  {problem}")
        if blocking:
            print("\nFix the errors above, or pass --skip-checks to start anyway.")
            return 1
        if problems:
            print()

    running: list[tuple[Service, subprocess.Popen]] = []
    try:
        for service in chosen:
            if port_open(service.port):
                print(f"  port {service.port} is already in use, skipping {service.name}")
                continue

            process = subprocess.Popen(
                service.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            running.append((service, process))
            threading.Thread(target=pump, args=(service, process), daemon=True).start()

            if not wait_for_port(service.port):
                print(f"\n  {service.name} did not open port {service.port}. Output above.")
                raise SystemExit(1)

        print("\n" + "-" * 58)
        for service in chosen:
            print(f"  {service.ready_message}")
        print("-" * 58)
        print("  Ctrl+C to stop everything\n")

        while True:
            for service, process in running:
                if process.poll() is not None:
                    print(f"\n  {service.name} exited with code {process.returncode}")
                    raise SystemExit(process.returncode or 1)
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n  stopping...")
        return 0
    finally:
        for service, process in reversed(running):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
        print("  stopped")


def main() -> int:
    sys.stdout.reconfigure(line_buffering=True)
    parser = argparse.ArgumentParser(
        prog="start", description="Run the MCP server, REST API and Streamlit UI together."
    )
    parser.add_argument(
        "service",
        nargs="*",
        choices=["mcp", "api", "ui"],
        help="which services to run (default: all three)",
    )
    parser.add_argument("--skip-checks", action="store_true")
    args = parser.parse_args()
    names = args.service or ["mcp", "api", "ui"]
    return run(names, args.skip_checks)


if __name__ == "__main__":
    sys.exit(main())
