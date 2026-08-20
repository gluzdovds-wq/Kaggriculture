"""Unpack literal V36 source bundles without importing or executing the agent."""

from __future__ import annotations

import ast
import base64
import json
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "research" / "public_agents" / "106-130-multi-generation-v36-robust-hybrid" / "main.py"
OUTPUT = SOURCE.parent / "unpacked"


def encoded_argument(node: ast.AST) -> str | None:
    for child in ast.walk(node):
        if not isinstance(child, ast.Call) or not child.args:
            continue
        func = child.func
        if isinstance(func, ast.Attribute) and func.attr == "b85decode":
            try:
                value = ast.literal_eval(child.args[0])
            except (ValueError, TypeError, SyntaxError):
                return None
            return value if isinstance(value, str) else None
    return None


def main() -> None:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    found = set()
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        names = [target.id for target in node.targets if isinstance(target, ast.Name)]
        if not names:
            continue
        name = names[0]
        encoded = encoded_argument(node.value)
        if encoded is None:
            continue
        decoded = zlib.decompress(base64.b85decode(encoded)).decode("utf-8")
        if name == "_V36_MODULES":
            modules = json.loads(decoded)
            for module_name, module_source in modules.items():
                path = OUTPUT / (module_name.replace(".", "/") + ".py")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(module_source, encoding="utf-8")
                compile(module_source, str(path), "exec")
            print(f"modules={len(modules)}")
            found.add(name)
        elif name == "_V36_ROUTE":
            route_path = OUTPUT / "route.json"
            route_path.write_text(json.dumps(json.loads(decoded), indent=2), encoding="utf-8")
            print(f"route={route_path}")
            found.add(name)
    expected = {"_V36_MODULES", "_V36_ROUTE"}
    if found != expected:
        raise SystemExit(f"missing bundles: {sorted(expected - found)}")


if __name__ == "__main__":
    main()

