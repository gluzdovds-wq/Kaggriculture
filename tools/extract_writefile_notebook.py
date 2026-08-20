"""Extract ``%%writefile`` cells from a downloaded public notebook.

The notebook is parsed as JSON and cell bodies are copied verbatim.  No cell is
executed, so shell commands and arbitrary Python in public notebooks stay inert.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("notebook", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    notebook = json.loads(args.notebook.read_text(encoding="utf-8"))
    extracted = []
    for cell in notebook.get("cells", []):
        source = cell.get("source", "")
        if isinstance(source, list):
            source = "".join(source)
        lines = source.splitlines(keepends=True)
        if not lines or not lines[0].startswith("%%writefile "):
            continue
        relative = Path(lines[0].removeprefix("%%writefile ").strip())
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"unsafe output path: {relative}")
        destination = args.output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("".join(lines[1:]), encoding="utf-8")
        extracted.append(str(relative))

    print(f"extracted {len(extracted)} files into {args.output}")
    for path in extracted:
        print(path)


if __name__ == "__main__":
    main()
