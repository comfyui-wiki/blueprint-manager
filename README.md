# Blueprint Manager

A local web UI for managing ComfyUI Core subgraph blueprints — category editing, renaming, bulk operations, JSON editing, import/export, and more.

## Quick Start

```bash
python main.py --blueprints /path/to/ComfyUI/blueprints
```

Then open [http://localhost:8099](http://localhost:8099) in your browser.

You can also set `BLUEPRINTS_DIR` in a `.env` file next to `main.py`:

```
BLUEPRINTS_DIR=/path/to/ComfyUI/blueprints
```

Then just run `python main.py`.

## Usage

```
python main.py [OPTIONS]

Options:
  --blueprints PATH   Path to the ComfyUI blueprints directory
                      (required unless BLUEPRINTS_DIR is set in .env)
  --port PORT         Port to serve on (default: 8099)
```

## macOS Shortcut

Double-click `start-blueprint-manager.command` to open a Terminal window and
launch the server, or add the shell script from `mac_shortcuts/` to a macOS
Shortcut action.

## Features

- **Grid / Table view** — browse all blueprints with category colour-coding
- **Category sidebar** — filter by category tree, spot uncategorised items
- **Inline JSON editor** — view, syntax-highlight, format and save any blueprint file directly in the browser
- **Download** — save any blueprint JSON to disk with one click
- **Import** — drag-and-drop or file-picker import with per-file category assignment
- **Recent imports** — newly imported files are highlighted (ephemeral; resets each server start)
- **Rename** — rename blueprint files from the UI
- **Delete** — remove blueprint files with a confirmation dialog
- **Bulk operations** — select multiple blueprints and assign categories at once
- **Search** — filter by name or category in real time
- **Zero Python dependencies** — uses only the standard library

## Project Structure

```
blueprint-manager/
├── main.py           # Entry point — argument parsing & server startup
├── config.py         # Shared constants (paths, limits)
├── state.py          # Ephemeral runtime state (recent imports)
├── blueprints.py     # Blueprint CRUD operations (scan, import, rename, delete, …)
├── handler.py        # HTTP request handler — API routes & static file serving
├── static/
│   ├── index.html    # Page structure
│   ├── style.css     # All styles
│   └── app.js        # All client-side logic
├── start-blueprint-manager.command   # Double-click launcher for macOS
├── .env.example
└── .gitignore
```

### Runtime state

A `.blueprint-manager-runtime/` directory is created next to `main.py` at
startup and wiped clean on every launch. It holds ephemeral files (e.g. the
recent-imports list) that should not be committed — it is listed in
`.gitignore`.
