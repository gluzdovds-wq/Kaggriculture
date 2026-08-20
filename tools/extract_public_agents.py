"""Safely extract public Kaggriculture agents from downloaded notebooks.

The notebook itself is never executed.  We only parse literal Python strings,
decode known Base64/Base85+zlib containers, and compile the recovered main.py.
Raw public notebooks and extracted agents are research inputs ignored by Git.
"""

from __future__ import annotations

import ast
import base64
import hashlib
import json
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_ROOT = ROOT / "research" / "public_notebooks"
OUTPUT_ROOT = ROOT / "research" / "public_agents"


def _source(cell: dict) -> str:
    source = cell.get("source", "")
    return "".join(source) if isinstance(source, list) else str(source)


def _literal_assignments(cells: list[dict]) -> dict[str, object]:
    values: dict[str, object] = {}
    for cell in cells:
        if cell.get("cell_type") != "code":
            continue
        source = _source(cell)
        if source.lstrip().startswith("%%"):
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            try:
                value = ast.literal_eval(node.value)
            except (ValueError, TypeError, SyntaxError):
                continue
            for target in targets:
                if isinstance(target, ast.Name):
                    values[target.id] = value
    return values


def _decode_notebook(path: Path) -> bytes:
    notebook = json.loads(path.read_text(encoding="utf-8"))
    cells = notebook.get("cells", [])

    for cell in cells:
        source = _source(cell)
        first, separator, body = source.partition("\n")
        if first.strip() == "%%writefile main.py" and separator:
            return body.encode("utf-8")

    # Some public notebooks name the emitted file differently even though the
    # cell is a self-contained competition agent.  Read the literal cell body;
    # never execute the notebook.
    for cell in cells:
        source = _source(cell)
        first, separator, body = source.partition("\n")
        if (first.strip().startswith("%%writefile ") and
                first.strip().endswith(".py") and separator and
                "def agent(" in body):
            return body.encode("utf-8")

    agentfile_parts = []
    for cell in cells:
        source = _source(cell)
        first, separator, body = source.partition("\n")
        if first.strip().startswith("%%agentfile") and separator:
            agentfile_parts.append(body)
    if agentfile_parts:
        return "".join(agentfile_parts).encode("utf-8")

    values = _literal_assignments(cells)
    embedded = values.get("TOP_AGENT_FILES")
    if isinstance(embedded, dict) and isinstance(embedded.get("main.py"), str):
        return embedded["main.py"].encode("utf-8")

    for key in ("AGENT_PAYLOAD", "PAYLOAD", "payload"):
        encoded_b85 = values.get(key)
        if isinstance(encoded_b85, str):
            return zlib.decompress(base64.b85decode(encoded_b85))

    encoded_b85 = values.get("SOURCE_B85")
    if isinstance(encoded_b85, str):
        decoded = base64.b85decode(encoded_b85)
        try:
            return zlib.decompress(decoded)
        except zlib.error:
            return decoded

    encoded_b64 = values.get("AGENT_B64")
    if isinstance(encoded_b64, str):
        return base64.b64decode(encoded_b64)

    # Last safe fallback for transparent notebooks: concatenate code cells up
    # to the last top-level `def agent`, excluding magics.  Compilation below
    # validates syntax but no extracted statement is executed here.
    last_agent_cell = -1
    accepted_sources: list[str] = []
    for cell in cells:
        if cell.get("cell_type") != "code":
            continue
        source = _source(cell)
        if source.lstrip().startswith(("%", "!")):
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        accepted_sources.append(source)
        if any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and
               node.name == "agent" for node in tree.body):
            last_agent_cell = len(accepted_sources) - 1
    if last_agent_cell >= 0:
        return ("\n\n".join(accepted_sources[: last_agent_cell + 1]) + "\n").encode(
            "utf-8"
        )

    raise ValueError("no supported literal main.py container found")


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    failures = []
    for notebook_path in sorted(NOTEBOOK_ROOT.rglob("*.ipynb")):
        slug = notebook_path.parent.name
        try:
            payload = _decode_notebook(notebook_path)
            compile(payload, f"{slug}/main.py", "exec")
            output_dir = OUTPUT_ROOT / slug
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "main.py"
            output_path.write_bytes(payload)
            digest = hashlib.sha256(payload).hexdigest()
            print(f"OK {slug}: {len(payload):,} bytes sha256={digest}")
        except Exception as exc:  # each public notebook is an independent input
            failures.append((slug, str(exc)))
            print(f"FAIL {slug}: {exc}")

    if failures:
        raise SystemExit(f"{len(failures)} notebook(s) could not be extracted")


if __name__ == "__main__":
    main()
