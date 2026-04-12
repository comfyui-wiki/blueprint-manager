"""Runtime state management — tracks recently imported blueprint filenames.

State is stored in .blueprint-manager-runtime/ (gitignored) and wiped fresh
at every server startup, so it behaves like a per-session cache.
"""

import json
import os

import config

RECENT_MODIFIED_FILE = "recent-modified.json"


def _recent_state_path() -> str:
    return os.path.join(config.RUNTIME_STATE_DIR, config.RECENT_IMPORTS_FILE)


def _recent_modified_path() -> str:
    return os.path.join(config.RUNTIME_STATE_DIR, RECENT_MODIFIED_FILE)


def reset_runtime_state_dir() -> None:
    """Create the runtime dir and delete any leftover files from the last run."""
    try:
        os.makedirs(config.RUNTIME_STATE_DIR, exist_ok=True)
        for name in os.listdir(config.RUNTIME_STATE_DIR):
            p = os.path.join(config.RUNTIME_STATE_DIR, name)
            try:
                if os.path.isfile(p) or os.path.islink(p):
                    os.remove(p)
            except OSError:
                pass
    except OSError:
        pass


def load_recent_import_filenames() -> list[str]:
    """Return filenames in order (most recently imported first)."""
    path = _recent_state_path()
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        names = data.get("filenames", [])
        return names if isinstance(names, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_recent_import_filenames(filenames: list[str]) -> None:
    path = _recent_state_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {"filenames": filenames[: config.MAX_RECENT_IMPORTS]},
                f,
                ensure_ascii=False,
                indent=2,
            )
    except OSError:
        pass


def track_import(filename: str) -> None:
    """Mark a blueprint file as recently imported (moves to front if already present)."""
    cur = [f for f in load_recent_import_filenames() if f != filename]
    cur.insert(0, filename)
    save_recent_import_filenames(cur)


def clear_recent_import_marks() -> None:
    save_recent_import_filenames([])


def remove_from_recent_imports(filename: str) -> None:
    cur = [f for f in load_recent_import_filenames() if f != filename]
    save_recent_import_filenames(cur)


def rename_in_recent_imports(old_name: str, new_name: str) -> None:
    cur = [new_name if f == old_name else f for f in load_recent_import_filenames()]
    save_recent_import_filenames(cur)


# ── Recently modified ────────────────────────────────────────────────────────

def _load_recent_modified() -> list[str]:
    path = _recent_modified_path()
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        names = data.get("filenames", [])
        return names if isinstance(names, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_recent_modified(filenames: list[str]) -> None:
    path = _recent_modified_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"filenames": filenames[:config.MAX_RECENT_IMPORTS]}, f,
                      ensure_ascii=False, indent=2)
    except OSError:
        pass


def track_modified(filename: str) -> None:
    """Mark a blueprint file as recently modified (moves to front if already present)."""
    cur = [f for f in _load_recent_modified() if f != filename]
    cur.insert(0, filename)
    _save_recent_modified(cur)


def clear_recent_modified_marks() -> None:
    _save_recent_modified([])


def remove_from_recent_modified(filename: str) -> None:
    cur = [f for f in _load_recent_modified() if f != filename]
    _save_recent_modified(cur)


def rename_in_recent_modified(old_name: str, new_name: str) -> None:
    cur = [new_name if f == old_name else f for f in _load_recent_modified()]
    _save_recent_modified(cur)


def load_recent_modified_filenames() -> list[str]:
    return _load_recent_modified()
