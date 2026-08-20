"""Patch nikital7's public 1.32.6 C++ simulator to 1.32.7 hinge curves."""

from __future__ import annotations

import argparse
from pathlib import Path


REPLACEMENTS = [
    (
        "enum Shape : uint8_t { F_LINEAR, F_SQ, F_SQRT, F_LOG, F_LOG10 };",
        "enum Shape : uint8_t { F_LINEAR, F_SQ, F_SQRT, F_LOG, F_LOG10, F_HINGE };",
    ),
    (
        "{  35, 10000, 450, F_LOG,    0.20, F_SQRT,   0.70 },  // CARROT",
        "{  35, 10000, 450, F_HINGE,  1.00, F_SQRT,   0.70 },  // CARROT",
    ),
    (
        "{  60, 10000, 200, F_LINEAR, 0.40, F_SQRT,   0.60 },  // TOMATO",
        "{  60, 10000, 200, F_HINGE,  0.40, F_SQRT,   0.60 },  // TOMATO",
    ),
    (
        "{  50, 10000, 332, F_LINEAR, 0.40, F_LOG,    0.20 },  // EGG",
        "{  50, 10000, 332, F_HINGE,  0.40, F_LOG,    0.20 },  // EGG",
    ),
    (
        "inline double shape(Shape f, double x) {",
        "inline double shape(Shape f, double x, double T = 0.0) {",
    ),
    (
        "        case F_LOG10:  return std::log10(1.0 + x);",
        "        case F_LOG10:  return std::log10(1.0 + x);\n"
        "        case F_HINGE: {\n"
        "            if (T <= 0.0) return x;\n"
        "            const double u = x / T;\n"
        "            const double excess = std::max(0.0, u - 1.0);\n"
        "            return u + 8.0 * excess * excess;\n"
        "        }",
    ),
    (
        "shape(MARKET[i].below_f, MARKET[i].T);",
        "shape(MARKET[i].below_f, MARKET[i].T, MARKET[i].T);",
    ),
    (
        "shape(MARKET[i].above_f, MARKET[i].T);",
        "shape(MARKET[i].above_f, MARKET[i].T, MARKET[i].T);",
    ),
    (
        "shape(p.below_f, static_cast<double>(p.I0 - inv));",
        "shape(p.below_f, static_cast<double>(p.I0 - inv), p.T);",
    ),
    (
        "shape(p.above_f, static_cast<double>(inv - p.I0));",
        "shape(p.above_f, static_cast<double>(inv - p.I0), p.T);",
    ),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sim_hpp", type=Path)
    args = parser.parse_args()
    text = args.sim_hpp.read_text(encoding="utf-8")
    for old, new in REPLACEMENTS:
        count = text.count(old)
        if count != 1:
            raise ValueError(f"expected one match, got {count}: {old[:80]!r}")
        text = text.replace(old, new, 1)
    args.sim_hpp.write_text(text, encoding="utf-8")
    print(f"patched {args.sim_hpp}")


if __name__ == "__main__":
    main()
