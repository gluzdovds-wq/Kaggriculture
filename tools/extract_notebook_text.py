"""Print selected source cells from one or more Jupyter notebooks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("notebooks", nargs="+", type=Path)
    parser.add_argument("--type", choices=("markdown", "code", "all"), default="all")
    parser.add_argument("--contains", help="case-insensitive source substring filter")
    args = parser.parse_args()
    needle = args.contains.casefold() if args.contains else None
    for notebook in args.notebooks:
        payload = json.loads(notebook.read_text(encoding="utf-8"))
        print(f"\n===== {notebook} =====")
        for index, cell in enumerate(payload.get("cells", [])):
            cell_type = str(cell.get("cell_type", "unknown"))
            if args.type != "all" and cell_type != args.type:
                continue
            source = "".join(cell.get("source", []))
            if needle and needle not in source.casefold():
                continue
            print(f"\n--- cell {index} [{cell_type}] ---")
            print(source.rstrip())


if __name__ == "__main__":
    main()
