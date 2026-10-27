"""
VoxentraAI — Combined Full-Stack Development Server Launcher
Starts both the FastAPI Backend and Vite Frontend concurrently with unified logging.
"""

import sys
import os
import subprocess
import signal
import time
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    reconfig = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfig):
        try:
            reconfig(encoding="utf-8")
        except Exception:
            pass

ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"

# Locate Python in venv or system
VENV_PYTHON = BACKEND_DIR / "venv" / "Scripts" / "python.exe"
if not VENV_PYTHON.exists():
    VENV_PYTHON = BACKEND_DIR / "venv" / "bin" / "python"
PYTHON_EXE = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable

def main():
    print("=" * 70)
    print("  VoxentraAI - Starting Combined Full-Stack Services")
    print("=" * 70)
    print(f"  Backend Dir  : {BACKEND_DIR}")
    print(f"  Frontend Dir : {FRONTEND_DIR}")
    print(f"  Python Path  : {PYTHON_EXE}")
    print("  Backend API  : http://localhost:8000")
    print("  Frontend UI  : http://localhost:5173")
    print("  Press Ctrl+C to stop both servers.")
    print("=" * 70)

    processes = []

    try:
        # Start Backend Uvicorn Server
        backend_cmd = [
            PYTHON_EXE,
            "-m", "uvicorn",
            "app.main:app",
            "--host", "127.0.0.1",
            "--port", "8000",
            "--reload"
        ]
        print("\n[LAUNCH] Starting FastAPI Backend on port 8000...")
        p_backend = subprocess.Popen(
            backend_cmd,
            cwd=str(BACKEND_DIR),
            shell=False
        )
        processes.append(("Backend", p_backend))

        # Give backend a moment to bind port
        time.sleep(1.5)

        # Start Frontend Vite Dev Server
        npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
        frontend_cmd = [npm_cmd, "run", "dev"]
        print("[LAUNCH] Starting Vite Frontend on port 5173...")
        p_frontend = subprocess.Popen(
            frontend_cmd,
            cwd=str(FRONTEND_DIR),
            shell=sys.platform == "win32"
        )
        processes.append(("Frontend", p_frontend))

        # Wait for any process to terminate or interrupt
        while True:
            for name, proc in processes:
                poll = proc.poll()
                if poll is not None:
                    print(f"\n[ALERT] {name} exited unexpectedly with code {poll}.")
                    return poll
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[STOP] Shutting down VoxentraAI combined servers...")
    finally:
        for name, proc in processes:
            if proc.poll() is None:
                print(f"[CLEANUP] Stopping {name}...")
                try:
                    if sys.platform == "win32":
                        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
                    else:
                        proc.terminate()
                except Exception:
                    pass
        print("[DONE] Both services terminated.")

if __name__ == "__main__":
    sys.exit(main() or 0)
