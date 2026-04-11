#!/usr/bin/env python3
"""
Blueprint Manager — Web UI for managing ComfyUI Core subgraph blueprints.

Usage:
    python main.py [--blueprints PATH] [--port PORT]

BLUEPRINTS_DIR can also be set via the .env file next to this script.
"""

import argparse
import os
import sys
from http.server import HTTPServer

import config
import state
from handler import Handler


def load_dotenv() -> None:
    """Load KEY=value pairs from the .env file located next to this script."""
    env_path = os.path.join(config.SCRIPT_DIR, ".env")
    if not os.path.isfile(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Blueprint Manager Web UI")
    parser.add_argument(
        "--blueprints",
        default=os.environ.get("BLUEPRINTS_DIR"),
        help="Path to the ComfyUI blueprints directory (required, or set BLUEPRINTS_DIR in .env)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", "8099")),
        help="Port to serve on (default: 8099)",
    )
    args = parser.parse_args()

    if not args.blueprints:
        parser.error("--blueprints is required (or set BLUEPRINTS_DIR in .env)")

    config.BLUEPRINTS_DIR = os.path.abspath(args.blueprints)

    if not os.path.isdir(config.BLUEPRINTS_DIR):
        print(f"Error: blueprints directory not found: {config.BLUEPRINTS_DIR}", file=sys.stderr)
        raise SystemExit(1)

    state.reset_runtime_state_dir()

    server = HTTPServer(("0.0.0.0", args.port), Handler)
    print(f"\n  🎨  Blueprint Manager  →  http://localhost:{args.port}\n")
    print(f"  Blueprints : {config.BLUEPRINTS_DIR}")
    print(f"  Static     : {config.STATIC_DIR}")
    print(f"  Runtime    : {config.RUNTIME_STATE_DIR}  (ephemeral)")
    print(f"\n  Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()
