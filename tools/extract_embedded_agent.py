"""Safely extract a compressed Python agent embedded in a public notebook.

The notebook is treated as data: no notebook cell is executed.  String-part
lists are decoded with the standard Base64/Base85 codecs and zlib, then the
result is accepted only when it is valid Python and matches a SHA-256 literal
present in the same cell.
"""

from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import json
import re
import zlib
from pathlib import Path


SHA256_RE = re.compile(r"[0-9a-fA-F]{64}")


def literal_string_parts(node: ast.AST) -> list[str] | None:
    """Return literal string parts without evaluating notebook code.

    Besides a bare list/tuple, public notebooks commonly spell large payloads
    as ``"".join(("part 1", "part 2"))``.  Recognising that AST shape keeps the
    extractor data-only while avoiding execution of the surrounding cell.
    """
    if (
        isinstance(node, ast.Call)
        and len(node.args) == 1
        and not node.keywords
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "join"
        and isinstance(node.func.value, ast.Constant)
        and node.func.value.value == ""
    ):
        node = node.args[0]
    try:
        value = ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError):
        return None
    if isinstance(value, (list, tuple)) and value and all(isinstance(x, str) for x in value):
        return list(value)
    return None


def decoded_candidates(encoded: str):
    raw_ascii = encoded.encode("ascii")
    for codec_name, decoder in (("b64", base64.b64decode), ("b85", base64.b85decode)):
        try:
            compressed = decoder(raw_ascii)
        except (ValueError, TypeError):
            continue
        for compression_name, decompress in (("zlib", zlib.decompress),):
            try:
                yield f"{codec_name}+{compression_name}", decompress(compressed)
            except zlib.error:
                continue


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("notebook", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    payload = json.loads(args.notebook.read_text(encoding="utf-8"))
    matches: list[tuple[int, str, bytes, str]] = []
    for index, cell in enumerate(payload.get("cells", [])):
        if cell.get("cell_type") != "code":
            continue
        source = "".join(cell.get("source", []))
        expected_hashes = {item.lower() for item in SHA256_RE.findall(source)}
        if not expected_hashes:
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value_node = node.value
            if value_node is None:
                continue
            parts = literal_string_parts(value_node)
            if not parts:
                continue
            try:
                encoded = "".join(parts)
            except TypeError:
                continue
            for method, raw in decoded_candidates(encoded):
                digest = hashlib.sha256(raw).hexdigest()
                if digest not in expected_hashes:
                    continue
                try:
                    compile(raw, str(args.output), "exec")
                except (SyntaxError, ValueError, TypeError):
                    continue
                matches.append((index, method, raw, digest))

    if not matches:
        raise SystemExit("no hash-verified compressed Python artifact found")
    # The last matching cell is normally the notebook's selected final artifact.
    index, method, raw, digest = matches[-1]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(raw)
    print(
        f"extracted cell={index} method={method} bytes={len(raw)} "
        f"sha256={digest} output={args.output} matches={len(matches)}"
    )


if __name__ == "__main__":
    main()
