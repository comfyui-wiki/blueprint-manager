"""Global configuration — all modules import from here.

main.py sets BLUEPRINTS_DIR at startup; all other modules read config.BLUEPRINTS_DIR
so they always see the current value.
"""

import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

STATIC_DIR = os.path.join(SCRIPT_DIR, "static")

# Ephemeral service state – wiped each process start; gitignored.
RUNTIME_STATE_DIR = os.path.join(SCRIPT_DIR, ".blueprint-manager-runtime")
RECENT_IMPORTS_FILE = "recent-imports.json"
MAX_RECENT_IMPORTS = 200

# Set at startup by main.py after argument parsing.
BLUEPRINTS_DIR: str = ""
