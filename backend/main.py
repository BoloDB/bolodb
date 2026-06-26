"""BoloDB entry point."""

import sys
import os
import time
import shutil
import subprocess
import argparse
import uvicorn
from backend.app.server import create_app


def is_ollama_up(url="http://localhost:11434"):
    try:
        import httpx

        httpx.get(f"{url}/api/tags", timeout=3)
        return True
    except Exception:
        return False


def start_ollama(url="http://localhost:11434"):
    exe = shutil.which("ollama")
    if not exe and sys.platform == "win32":
        for c in [
            os.path.join(
                os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe"
            ),
            r"C:\Program Files\Ollama\ollama.exe",
        ]:
            if os.path.exists(c):
                exe = c
                break
    if not exe:
        return False
    print("  Starting Ollama...", end="", flush=True)
    try:
        kw = dict(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if sys.platform == "win32":
            subprocess.Popen(
                [exe, "serve"],
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
                **kw,
            )
        else:
            subprocess.Popen([exe, "serve"], **kw)
        for _ in range(20):
            time.sleep(1)
            print(".", end="", flush=True)
            if is_ollama_up(url):
                print(" ready.")
                return True
        print(" timed out.")
        return False
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser(description="BoloDB")
    ap.add_argument("--db", default="", help="Pre-connect a database URL")
    ap.add_argument("--port", default=4321, type=int)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--allow-writes", action="store_true")
    args = ap.parse_args()

    print("\n  BoloDB  -  Ask your data. Trust the answer.\n")

    from backend.app import config as cfgmod

    cfg = cfgmod.load_config()
    if cfg.get("provider", "ollama") == "ollama":
        if not is_ollama_up(cfg.get("ollama_url", "http://localhost:11434")):
            if not start_ollama(cfg.get("ollama_url", "http://localhost:11434")):
                print(
                    "  Note: Ollama not running. Pick a cloud provider in Settings.\n"
                )

    app = create_app(initial_db_url=args.db, readonly=not args.allow_writes)
    url = f"http://{args.host}:{args.port}"
    print(f"  Open: {url}\n  (Ctrl+C to stop)\n")

    if not args.no_browser:
        import threading
        import webbrowser

        threading.Thread(
            target=lambda: (time.sleep(1.5), webbrowser.open(url)), daemon=True
        ).start()

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
