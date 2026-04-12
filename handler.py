"""HTTP request handler — routes all API and static-file requests."""

import json
import mimetypes
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler

import blueprints
import config
import state


_STATIC_MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json",
    ".ico": "image/x-icon",
}


class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):  # silence default access log
        pass

    # ── Low-level helpers ────────────────────────────────────────────────────

    def _send(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode()
        self._send(body, "application/json", status)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length else {}

    def _serve_static(self, rel_path: str) -> None:
        """Serve a file from the static/ directory."""
        safe_rel = os.path.normpath(rel_path).lstrip("/\\")
        fpath = os.path.join(config.STATIC_DIR, safe_rel)
        # Prevent path traversal outside STATIC_DIR
        if not os.path.realpath(fpath).startswith(os.path.realpath(config.STATIC_DIR)):
            self.send_error(403)
            return
        if not os.path.isfile(fpath):
            self.send_error(404)
            return
        ext = os.path.splitext(fpath)[1].lower()
        mime = _STATIC_MIME.get(ext, "application/octet-stream")
        with open(fpath, "rb") as f:
            body = f.read()
        self._send(body, mime)

    # ── Blueprint filename extraction ────────────────────────────────────────

    @staticmethod
    def _bp_filename(path: str, suffix: str) -> str:
        """Extract and URL-decode the blueprint filename from a route like
        /api/blueprints/<filename>/<suffix>."""
        inner = path[len("/api/blueprints/") : -len(suffix)]
        return urllib.parse.unquote(inner)

    # ── GET ──────────────────────────────────────────────────────────────────

    def do_GET(self) -> None:
        path = self.path.split("?")[0]

        if path == "/":
            self._serve_static("index.html")
        elif path.startswith("/static/"):
            self._serve_static(path[len("/static/"):])
        elif path == "/api/blueprints":
            self._json(blueprints.scan_blueprints())
        elif path == "/api/categories":
            self._json(blueprints.get_all_categories())
        elif path.startswith("/api/blueprints/") and path.endswith("/content"):
            filename = self._bp_filename(path, "/content")
            content, err = blueprints.read_blueprint_content(filename)
            if err:
                self._json({"ok": False, "error": err}, 400)
            else:
                self._json({"ok": True, "content": content})
        elif path.startswith("/api/blueprints/") and path.endswith("/validate"):
            filename = self._bp_filename(path, "/validate")
            self._json(blueprints.validate_blueprint_schema(filename))
        elif path == "/api/validate-all":
            self._json(blueprints.validate_all_blueprints())
        else:
            self.send_error(404)

    # ── POST ─────────────────────────────────────────────────────────────────

    def do_POST(self) -> None:
        path = self.path.split("?")[0]

        if path == "/api/import":
            body = self._read_body()
            ok, msg = blueprints.import_blueprint(
                body.get("filename", ""),
                body.get("content", ""),
                body.get("category", ""),
            )
            self._json({"ok": ok, "error": msg}, 200 if ok else 400)
        elif path == "/api/clear-recent-imports":
            state.clear_recent_import_marks()
            self._json({"ok": True})
        elif path == "/api/clear-recent-modified":
            state.clear_recent_modified_marks()
            self._json({"ok": True})
        else:
            self.send_error(404)

    # ── PUT ──────────────────────────────────────────────────────────────────

    def do_PUT(self) -> None:
        path = self.path.split("?")[0]
        body = self._read_body()

        if path.startswith("/api/blueprints/") and path.endswith("/content"):
            filename = self._bp_filename(path, "/content")
            ok, msg = blueprints.write_blueprint_content(filename, body.get("content", ""))
            self._json({"ok": ok, "error": msg}, 200 if ok else 400)
        elif path.startswith("/api/blueprints/") and path.endswith("/category"):
            filename = self._bp_filename(path, "/category")
            ok, msg = blueprints.update_category(
                filename, body.get("sg_index", 0), body.get("category", "")
            )
            self._json({"ok": ok, "message": msg}, 200 if ok else 400)
        elif path.startswith("/api/blueprints/") and path.endswith("/rename"):
            filename = self._bp_filename(path, "/rename")
            ok, msg = blueprints.rename_blueprint(filename, body.get("new_name", ""))
            self._json({"ok": ok, "error": msg}, 200 if ok else 400)
        elif path.startswith("/api/blueprints/") and path.endswith("/replace"):
            filename = self._bp_filename(path, "/replace")
            ok, msg = blueprints.replace_blueprint(
                filename,
                body.get("content", ""),
                bool(body.get("preserve_categories", True)),
            )
            self._json({"ok": ok, "error": msg}, 200 if ok else 400)
        else:
            self.send_error(404)

    # ── DELETE ───────────────────────────────────────────────────────────────

    def do_DELETE(self) -> None:
        path = self.path.split("?")[0]

        if path.startswith("/api/blueprints/"):
            filename = urllib.parse.unquote(path[len("/api/blueprints/"):])
            if "/" in filename or "\\" in filename:
                self._json({"ok": False, "error": "Invalid filename"}, 400)
                return
            ok, msg = blueprints.delete_blueprint(filename)
            self._json({"ok": ok, "error": msg}, 200 if ok else 400)
        else:
            self.send_error(404)
