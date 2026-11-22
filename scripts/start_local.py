"""Start both local services on the next available ports."""
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
env = dict(os.environ)
node = shutil.which("node", path=env["PATH"])
windows_hidden = (
    {"creationflags": subprocess.CREATE_NO_WINDOW}
    if os.name == "nt"
    else {}
)

def available_port(preferred: int) -> int:
    for port in range(preferred, preferred + 50):
        occupied = False
        for family, address in (
            (socket.AF_INET, "127.0.0.1"),
            (socket.AF_INET6, "::1"),
        ):
            with socket.socket(family) as probe:
                if probe.connect_ex((address, port)) == 0:
                    occupied = True
                    break
        if occupied:
            continue
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise SystemExit(f"No free port found near {preferred}")


web_port = available_port(3000)
api_port = available_port(int(os.getenv("ZAOJING_API_PORT", "8010")))
api_url = f"http://127.0.0.1:{api_port}"
env["ZAOJING_API_PORT"] = str(api_port)
env["NEXT_PUBLIC_API_BASE_URL"] = api_url
web_mode = os.getenv("ZAOJING_WEB_MODE", "start").lower()
if web_mode not in {"start", "dev"}:
    raise SystemExit("ZAOJING_WEB_MODE must be 'start' or 'dev'")

python = root / "apps/api/.venv/Scripts/python.exe"
if not python.is_file():
    python = root / "apps/api/.venv/bin/python"
if not python.is_file():
    python = Path(sys.executable)

if not node:
    raise SystemExit("Node.js is not available")

next_bin = root / "apps/web/node_modules/next/dist/bin/next"
if web_mode == "start":
    print("Building Next.js production bundle...", flush=True)
    subprocess.run(
        [node, str(next_bin), "build"],
        cwd=root / "apps/web",
        env=env,
        check=True,
        **windows_hidden,
    )

children = []
try:
    children.append(
        subprocess.Popen(
            [
                str(python),
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(api_port),
            ],
            cwd=root / "apps/api",
            env=env,
            **windows_hidden,
        )
    )
    children.append(
        subprocess.Popen(
            [
                node,
                str(next_bin),
                web_mode,
                "--hostname",
                "127.0.0.1",
                "--port",
                str(web_port),
            ],
            cwd=root / "apps/web",
            env=env,
            **windows_hidden,
        )
    )
    print(
        f"Website: http://127.0.0.1:{web_port} | API: {api_url} | Ctrl+C to stop",
        flush=True,
    )
    while all(child.poll() is None for child in children):
        time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    for child in children:
        if child.poll() is None:
            child.terminate()
    for child in children:
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
