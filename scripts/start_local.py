"""Start both local services; Ctrl+C stops only these child processes."""
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
env = dict(os.environ)
env["PATH"] = (
    str(Path.home() / ".local/opt/node-v24.20.0/bin")
    + os.pathsep
    + env.get("PATH", "")
)
for port in (3000, 8000):
    with socket.socket() as sock:
        if sock.connect_ex(("127.0.0.1", port)) == 0:
            raise SystemExit(
                f"Port {port} is already running. Open http://127.0.0.1:3000 "
                "or stop the previous services first."
            )
node = shutil.which("node", path=env["PATH"])
if not node:
    raise SystemExit("Node.js is not available")
children = []
try:
    children.append(
        subprocess.Popen(
            [
                str(root / "apps/api/.venv/bin/python"),
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            cwd=root / "apps/api",
            env=env,
        )
    )
    children.append(
        subprocess.Popen(
            [
                node,
                "node_modules/next/dist/bin/next",
                "dev",
                "--hostname",
                "127.0.0.1",
                "--port",
                "3000",
            ],
            cwd=root / "apps/web",
            env=env,
        )
    )
    print("Website: http://127.0.0.1:3000 | Ctrl+C to stop", flush=True)
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
