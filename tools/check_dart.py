#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""APH local sanity check for Dart sources.

فحص سريع دون تثبيت Flutter: توازن الأقواس والسلاسل النصية في ملفات Dart.
يلتقط الأخطاء الشائعة التي تكسر البناء (سلسلة ثلاثية الاقتباس غير مغلقة،
قوس ناقص…) قبل الدفع إلى GitHub Actions.

الاستخدام:  python3 tools/check_dart.py
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

PAIRS = {"(": ")", "[": "]", "{": "}"}
CLOSERS = {")": "(", "]": "[", "}": "{"}


def scan(path: pathlib.Path):
    """Returns a list of problem strings (empty list = OK)."""
    src = path.read_text(encoding="utf-8")
    problems = []
    stack = []  # (char, line)
    i = 0
    line = 1
    n = len(src)
    in_line_comment = False
    in_block_comment = 0
    string = None  # "'''", '"""', "'", '"'
    raw = False
    while i < n:
        c = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if c == "\n":
            line += 1
            if in_line_comment:
                in_line_comment = False
            if string in ("'", '"'):
                problems.append(f"line {line - 1}: unterminated {string} string at end of line")
                string = None
            i += 1
            continue
        if in_line_comment:
            i += 1
            continue
        if in_block_comment:
            if c == "*" and nxt == "/":
                in_block_comment -= 1
                i += 2
                continue
            i += 1
            continue
        if string:
            if raw:
                if src.startswith(string, i):
                    i += len(string)
                    string = None
                    raw = False
                    continue
                i += 1
                continue
            if c == "\\":
                i += 2
                continue
            if src.startswith(string, i):
                i += len(string)
                string = None
                continue
            # interpolation ${ ... } — track braces so the stack stays honest
            if c == "$" and nxt == "{":
                stack.append(("${", line))
                i += 2
                continue
            if c == "}" and stack and stack[-1][0] == "${":
                stack.pop()
                i += 1
                continue
            i += 1
            continue
        # not in string / comment
        if c == "/" and nxt == "/":
            in_line_comment = True
            i += 2
            continue
        if c == "/" and nxt == "*":
            in_block_comment += 1
            i += 2
            continue
        if c == "r" and (src.startswith("r'''", i) or src.startswith('r"""', i)):
            string = src[i + 1:i + 4]
            raw = True
            i += 4
            continue
        if c in ("r",) and nxt in ("'", '"'):
            string = nxt
            raw = True
            i += 2
            continue
        if src.startswith("'''", i) or src.startswith('"""', i):
            string = src[i:i + 3]
            i += 3
            continue
        if c in ("'", '"'):
            string = c
            i += 1
            continue
        if c in PAIRS:
            stack.append((c, line))
            i += 1
            continue
        if c in CLOSERS:
            if not stack:
                problems.append(f"line {line}: unexpected '{c}'")
            else:
                top, tl = stack.pop()
                if top != CLOSERS[c]:
                    problems.append(
                        f"line {line}: '{c}' closes '{top}' opened at line {tl}")
            i += 1
            continue
        i += 1
    if string:
        problems.append(f"unterminated string {string} (opened before EOF)")
    for ch, tl in stack:
        problems.append(f"unclosed '{ch}' opened at line {tl}")
    # a stray '${' interpolation left open is also worth reporting
    
    return problems


def main() -> int:
    files = sorted((ROOT / "lib").rglob("*.dart"))
    bad = 0
    for f in files:
        probs = scan(f)
        if probs:
            bad += 1
            print(f"✗ {f.relative_to(ROOT)}")
            for p in probs[:10]:
                print(f"    {p}")
    print(f"checked {len(files)} dart files — {bad} with problems")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
