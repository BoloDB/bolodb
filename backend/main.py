"""BoloDB entry point."""

import argparse
import time

import uvicorn

from backend.app.server import create_app


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
    if not cfg.get("api_keys", {}).get("gemini"):
        print(
            "  Note: no Gemini API key configured yet. Add one in Settings\n"
            "  (free key: https://aistudio.google.com/app/api-keys) or set the\n"
            "  GEMINI_API_KEY environment variable.\n"
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
