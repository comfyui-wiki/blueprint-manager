"""Blueprint CRUD operations — all filesystem access for blueprint JSON files lives here."""

import glob
import json
import os
import re
from typing import Optional

import config
import state

# ── Schema constants (derived from ComfyUI frontend workflowSchema.ts) ──────

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

def _is_uuid(value: object) -> bool:
    return isinstance(value, str) and bool(_UUID_RE.match(value))


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
    modified_set = set(state.load_recent_modified_filenames())
    for fpath in sorted(glob.glob(os.path.join(config.BLUEPRINTS_DIR, "*.json"))):
        fname = os.path.basename(fpath)
        if fname.startswith("."):
            continue
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            continue
        extra = data.get("extra") or {}
        subgraphs = data.get("definitions", {}).get("subgraphs", [])
        sg_list = []
        for idx, sg in enumerate(subgraphs):
            # Unique node types used inside this subgraph (enables "search by node" queries)
            node_types = sorted({
                n.get("type", "")
                for n in (sg.get("nodes") or [])
                if isinstance(n, dict) and n.get("type")
            })
            sg_list.append({
                "index": idx,
                "name": sg.get("name", ""),
                "category": sg.get("category", ""),
                "id": sg.get("id", ""),
                "description": sg.get("description", ""),
                "node_types": node_types,
            })
        results.append(
            {
                "filename": fname,
                "mtime": os.path.getmtime(fpath),
                "recent_import": fname in recent_set,
                "recent_modified": fname in modified_set,
                # Blueprint-level searchable metadata
                "description": extra.get("BlueprintDescription") or "",
                "aliases": extra.get("BlueprintSearchAliases") or [],
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
    state.track_modified(filename)
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
    state.track_modified(filename)
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
    state.rename_in_recent_modified(old_name, new_name)
    return True, "OK"


def replace_blueprint(filename: str, new_content: str, preserve_categories: bool = True) -> tuple[bool, str]:
    """Overwrite an existing blueprint file.

    When *preserve_categories* is True, category assignments from the current
    file are carried forward to the new content: matching is tried first by
    subgraph ID, then by position index.
    """
    fpath, err = _safe_blueprint_path(filename)
    if err:
        return False, err
    if not os.path.isfile(fpath):
        return False, "File not found"
    try:
        new_data = json.loads(new_content)
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {e}"

    if preserve_categories:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                old_data = json.load(f)
            old_sgs = old_data.get("definitions", {}).get("subgraphs", [])
            new_sgs = new_data.get("definitions", {}).get("subgraphs", [])
            old_by_id = {s.get("id"): s for s in old_sgs if s.get("id")}
            for i, new_sg in enumerate(new_sgs):
                old_sg = old_by_id.get(new_sg.get("id")) or (old_sgs[i] if i < len(old_sgs) else None)
                if old_sg and old_sg.get("category"):
                    new_sg["category"] = old_sg["category"]
        except (json.JSONDecodeError, OSError):
            pass  # if old file is unreadable, just write the new content as-is

    try:
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(new_data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        return False, str(e)
    state.track_modified(filename)
    return True, "OK"


def validate_blueprint_schema(filename: str) -> dict:
    """Validate a blueprint file against the ComfyUI frontend schema rules.

    Rules are derived from:
      - workflowSchema.ts  → zComfyWorkflow1, zSubgraphDefinition, zSubgraphIO
      - serialisation.ts   → ExportedSubgraph, ExportedSubgraphIONode
      - subgraphStore.ts   → SubgraphBlueprint.validateSubgraph()

    Returns:
        {
          "ok": bool,           # True when there are no error-level issues
          "error_count": int,
          "warning_count": int,
          "issues": [
            { "level": "error"|"warning", "path": str, "message": str }
          ]
        }
    """
    issues: list[dict] = []

    def _err(path: str, msg: str) -> None:
        issues.append({"level": "error", "path": path, "message": msg})

    def _warn(path: str, msg: str) -> None:
        issues.append({"level": "warning", "path": path, "message": msg})

    # ── file / JSON ──────────────────────────────────────────────────────────
    fpath, err = _safe_blueprint_path(filename)
    if err:
        _err("", err)
        return _validation_result(issues)
    if not os.path.isfile(fpath):
        _err("", "File not found")
        return _validation_result(issues)
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        _err("", f"Invalid JSON: {e}")
        return _validation_result(issues)

    if not isinstance(data, dict):
        _err("", "Root value must be a JSON object")
        return _validation_result(issues)

    # ── version ──────────────────────────────────────────────────────────────
    version = data.get("version")
    if version is None:
        _err("version", "Missing required field 'version'")
    elif not isinstance(version, (int, float)):
        _err("version", f"'version' must be a number, got {type(version).__name__}")

    is_v1 = version == 1

    # ── top-level structure ──────────────────────────────────────────────────
    if is_v1:
        state_obj = data.get("state")
        if state_obj is None:
            _err("state", "Missing required field 'state' (required for version 1)")
        elif isinstance(state_obj, dict):
            for field in ("lastGroupId", "lastNodeId", "lastLinkId", "lastRerouteId"):
                if field not in state_obj:
                    _warn(f"state.{field}", f"Missing state counter field '{field}'")
        if "nodes" not in data:
            _err("nodes", "Missing required field 'nodes'")
    else:
        for field in ("last_node_id", "last_link_id", "nodes", "links"):
            if field not in data:
                _warn(field, f"Missing legacy-format field '{field}'")

    # ── definitions.subgraphs ────────────────────────────────────────────────
    definitions = data.get("definitions")
    if definitions is None:
        _err("definitions", "Missing 'definitions' — blueprint files must have this field")
        return _validation_result(issues)

    if not isinstance(definitions, dict):
        _err("definitions", "'definitions' must be an object")
        return _validation_result(issues)

    subgraphs = definitions.get("subgraphs")
    if subgraphs is None:
        _err("definitions.subgraphs", "Missing 'definitions.subgraphs'")
        return _validation_result(issues)
    if not isinstance(subgraphs, list):
        _err("definitions.subgraphs", "'definitions.subgraphs' must be an array")
        return _validation_result(issues)
    if len(subgraphs) == 0:
        _err("definitions.subgraphs", "'definitions.subgraphs' is empty — no subgraph definitions found")

    # ── blueprint-level rule (subgraphStore.ts validateSubgraph) ────────────
    # Root graph must have exactly one node whose type equals a subgraph id.
    subgraph_ids = {
        sg["id"] for sg in subgraphs
        if isinstance(sg, dict) and _is_uuid(sg.get("id", ""))
    }
    root_nodes = data.get("nodes", [])
    if isinstance(root_nodes, list) and subgraphs:
        if len(root_nodes) == 0:
            _warn("nodes", "Root graph 'nodes' is empty — expected one subgraph instance node")
        elif len(root_nodes) > 1:
            _err(
                "nodes",
                f"Root graph must contain exactly 1 node (the subgraph instance), "
                f"found {len(root_nodes)}",
            )
        elif len(root_nodes) == 1 and subgraph_ids:
            root_type = root_nodes[0].get("type") if isinstance(root_nodes[0], dict) else None
            if root_type not in subgraph_ids:
                _err(
                    "nodes[0].type",
                    f"Root node type '{root_type}' does not match any subgraph id in "
                    f"definitions.subgraphs",
                )

    # ── per-subgraph validation ──────────────────────────────────────────────
    for idx, sg in enumerate(subgraphs):
        pfx = f"definitions.subgraphs[{idx}]"

        if not isinstance(sg, dict):
            _err(pfx, "Subgraph definition must be an object")
            continue

        sg_label = sg.get("name") or f"subgraph[{idx}]"

        # id — required, UUID
        sg_id = sg.get("id")
        if not sg_id:
            _err(f"{pfx}.id", f"Missing required 'id' (in '{sg_label}')")
        elif not _is_uuid(sg_id):
            _err(f"{pfx}.id", f"'id' must be a UUID string, got: '{sg_id}' (in '{sg_label}')")

        # name — required string
        if not sg.get("name"):
            _err(f"{pfx}.name", f"Missing required 'name' (in '{sg_label}')")

        # revision — required number
        revision = sg.get("revision")
        if revision is None:
            _err(f"{pfx}.revision", f"Missing required 'revision' (in '{sg_label}')")
        elif not isinstance(revision, (int, float)):
            _err(f"{pfx}.revision", f"'revision' must be a number (in '{sg_label}')")

        # version — should be 1 (subgraph defs always use v1 format)
        sg_ver = sg.get("version")
        if sg_ver is None:
            _err(f"{pfx}.version", f"Missing 'version' field (in '{sg_label}')")
        elif sg_ver != 1:
            _warn(f"{pfx}.version", f"'version' should be 1, got {sg_ver} (in '{sg_label}')")

        # state — required for v1 subgraph defs
        sg_state = sg.get("state")
        if sg_state is None:
            _err(f"{pfx}.state", f"Missing required 'state' (in '{sg_label}')")
        elif isinstance(sg_state, dict):
            for field in ("lastGroupId", "lastNodeId", "lastLinkId", "lastRerouteId"):
                if field not in sg_state:
                    _warn(f"{pfx}.state.{field}", f"Missing state counter '{field}' (in '{sg_label}')")

        # nodes — required list
        if "nodes" not in sg:
            _err(f"{pfx}.nodes", f"Missing required 'nodes' (in '{sg_label}')")

        # inputNode / outputNode — required, must have id + bounding[4]
        for io_key in ("inputNode", "outputNode"):
            io_node = sg.get(io_key)
            if io_node is None:
                _err(f"{pfx}.{io_key}", f"Missing required '{io_key}' (in '{sg_label}')")
            elif isinstance(io_node, dict):
                if "id" not in io_node:
                    _err(f"{pfx}.{io_key}.id", f"'{io_key}' missing 'id' (in '{sg_label}')")
                bounding = io_node.get("bounding")
                if bounding is None:
                    _err(f"{pfx}.{io_key}.bounding", f"'{io_key}' missing 'bounding' (in '{sg_label}')")
                elif not (isinstance(bounding, list) and len(bounding) == 4):
                    _err(
                        f"{pfx}.{io_key}.bounding",
                        f"'{io_key}.bounding' must be a 4-element array, "
                        f"got {len(bounding) if isinstance(bounding, list) else type(bounding).__name__} "
                        f"(in '{sg_label}')",
                    )

        # inputs / outputs — optional, but each slot must have UUID id + string type
        for slot_key in ("inputs", "outputs"):
            slots = sg.get(slot_key)
            if slots is None:
                continue
            if not isinstance(slots, list):
                _err(f"{pfx}.{slot_key}", f"'{slot_key}' must be an array (in '{sg_label}')")
                continue
            for j, slot in enumerate(slots):
                if not isinstance(slot, dict):
                    _err(f"{pfx}.{slot_key}[{j}]", f"Slot must be an object (in '{sg_label}')")
                    continue
                slot_id = slot.get("id")
                if not slot_id:
                    _err(f"{pfx}.{slot_key}[{j}].id", f"Slot missing required 'id' (in '{sg_label}')")
                elif not _is_uuid(slot_id):
                    _err(
                        f"{pfx}.{slot_key}[{j}].id",
                        f"Slot 'id' must be a UUID string, got '{slot_id}' (in '{sg_label}')",
                    )
                if "type" not in slot:
                    _warn(f"{pfx}.{slot_key}[{j}].type", f"Slot missing 'type' field (in '{sg_label}')")

        # category — optional but must be a string if present
        category = sg.get("category")
        if category is not None and not isinstance(category, str):
            _err(f"{pfx}.category", f"'category' must be a string (in '{sg_label}')")

    return _validation_result(issues)


def _validation_result(issues: list[dict]) -> dict:
    errors = sum(1 for i in issues if i["level"] == "error")
    warnings = sum(1 for i in issues if i["level"] == "warning")
    return {
        "ok": errors == 0,
        "error_count": errors,
        "warning_count": warnings,
        "issues": issues,
    }


def validate_all_blueprints() -> list[dict]:
    """Run schema validation on every blueprint file and return a summary list."""
    results = []
    for bp in scan_blueprints():
        result = validate_blueprint_schema(bp["filename"])
        results.append({
            "filename": bp["filename"],
            "ok": result["ok"],
            "error_count": result["error_count"],
            "warning_count": result["warning_count"],
            "issues": result["issues"],
        })
    return results


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
    state.remove_from_recent_modified(filename)
    return True, "OK"
