# Blueprint Manager

A web UI for visually managing ComfyUI Core subgraph blueprints — category management, renaming, bulk editing, and more.

## Quick Start

```bash
python blueprint_manager.py --blueprints /path/to/ComfyUI/blueprints
```

Then open [http://localhost:8099](http://localhost:8099) in your browser.

## Usage

```
python blueprint_manager.py [OPTIONS]

Options:
  --blueprints PATH   Path to the ComfyUI blueprints directory (required)
  --port PORT         Port to serve on (default: 8099)
```

## Features

- **Grid / Table view** — browse all blueprints with category color-coding
- **Category sidebar** — filter by category tree, spot uncategorized items
- **Inline editing** — click to change category with suggestions from existing categories
- **Bulk operations** — select multiple blueprints and assign categories at once
- **Rename** — rename blueprint files directly from the UI
- **Search** — filter blueprints by name or category
- **Zero dependencies** — uses only Python stdlib
