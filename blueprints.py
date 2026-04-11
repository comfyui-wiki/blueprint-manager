"""Blueprint CRUD operations — all filesystem access for blueprint JSON files lives here."""

import glob
import json
import os
from typing import Optional

import config
import state


# ── Path validation ──────────────────────────────────────────────────────────

def _safe_blueprint_path(filename: str) -> tuple[Optional[str], Optional[str]]:
    """Return (absolute_path, None) or (None, error_message)."""
    if not filename or not isinstance(filename, str):
        return None, "Invalid filename"
    if "/" in filename or "\\" in filename or filename.startswith("."):
        return None, "Invalid filename"
    if not filename.endswith(".json"):
        return None, "Filename must end with .json"
    fpath = os.path.join(config.BLUEPRINTS_DIR, filename)
    real_dir = os.path.realpath(config.BLUEPRINTS_DIR)
    real_file = os.path.realpath(fpath)
    if not real_file.startswith(real_dir + os.sep):
        return None, "Invalid path"
    return fpath, None


# ── Read ─────────────────────────────────────────────────────────────────────

def scan_blueprints() -> list[dict]:
    """Return a list of blueprint info dicts for every valid .json in BLUEPRINTS_DIR."""
    results = []
    recent_set = set(state.load_recent_import_filenames())
    for fpath in sorted(glob.glob(os.path.join(config.BLUEPRINTS_DIR, "*.json"))):
        fname = os.path.basename(fpath)
        if fname.startswith("."):
            continue
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            continue
        subgraphs = data.get("definitions", {}).get("subgraphs", [])
        sg_list = [
            {
                "index": idx,
                "name": sg.get("name", ""),
                "category": sg.get("category", ""),
                "id": sg.get("id", ""),
            }
            for idx, sg in enumerate(subgraphs)
        ]
        results.append(
            {
                "filename": fname,
                "mtime": os.path.getmtime(fpath),
                "recent_import": fname in recent_set,
                "subgraphs": sg_list,
            }
        )
    return results


def get_all_categories() -> list[str]:
    """Return sorted unique categories across all blueprints."""
    cats: set[str] = set()
    for bp in scan_blueprints():
        for sg in bp["subgraphs"]:
            if sg["category"]:
                cats.add(sg["category"])
    return sorted(cats)


def read_blueprint_content(filename: str) -> tuple[Optional[str], Optional[str]]:
    """Return (formatted_json_string, None) or (None, error)."""
    fpath, err = _safe_blueprint_path(filename)
    if err:
        return None, err
    if not os.path.isfile(fpath):
        return None, "File not found"
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return json.dumps(data, ensure_ascii=False, indent=2), None
    except (json.JSONDecodeError, OSError) as e:
        return None, str(e)


# ── Write ────────────────────────────────────────────────────────────────────

def update_category(filename: str, sg_index: int, new_category: str) -> tuple[bool, str]:
    fpath, err = _safe_blueprint_path(filename)
    if err:
        return False, err
    if not os.path.isfile(fpath):
        return False, "File not found"
    with open(fpath, "r", encoding="utf-8") as f:
        data = json.load(f)
    subgraphs = data.get("definitions", {}).get("subgraphs", [])
    if sg_index < 0 or sg_index >= len(subgraphs):
        return False, "Subgraph index out of range"
    subgraphs[sg_index]["category"] = new_category
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return True, "OK"


def write_blueprint_content(filename: str, content: str) -> tuple[bool, str]:
    """Validate JSON and overwrite a blueprint file."""
    fpath, err = _safe_blueprint_path(filename)
    if err:
        return False, err
    if not os.path.isfile(fpath):
        return False, "File not found"
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {e}"
    try:
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        return False, str(e)
    return True, "OK"


def import_blueprint(filename: str, content: str, category: str) -> tuple[bool, str]:
    """Write a new blueprint file; optionally set the primary subgraph's category."""
    fpath, err = _safe_blueprint_path(filename)
    if err:
        return False, err
    if os.path.exists(fpath):
        return False, "File already exists"
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return False, "Invalid JSON"
    if category:
        subgraphs = data.get("definitions", {}).get("subgraphs", [])
        if subgraphs:
            subgraphs[0]["category"] = category
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    state.track_import(filename)
    return True, "OK"


def rename_blueprint(old_name: str, new_name: str) -> tuple[bool, str]:
    old_path, e1 = _safe_blueprint_path(old_name)
    if e1:
        return False, e1
    new_path, e2 = _safe_blueprint_path(new_name)
    if e2:
        return False, e2
    if not os.path.isfile(old_path):
        return False, "Source file not found"
    if os.path.exists(new_path):
        return False, "Target file already exists"
    os.rename(old_path, new_path)
    state.rename_in_recent_imports(old_name, new_name)
    return True, "OK"


def delete_blueprint(filename: str) -> tuple[bool, str]:
    fpath, err = _safe_blueprint_path(filename)
    if err:
        return False, err
    if not os.path.isfile(fpath):
        return False, "File not found"
    try:
        os.remove(fpath)
    except OSError as e:
        return False, str(e)
    state.remove_from_recent_imports(filename)
    return True, "OK"
