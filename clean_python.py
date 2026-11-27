import ast
import re
from pathlib import Path


def strip_comments(source):
    lines = source.split("\n")
    out = []
    for line in lines:
        if line.lstrip().startswith("#!"):
            out.append(line)
            continue
        in_str = None
        i = 0
        cut = -1
        while i < len(line):
            ch = line[i]
            if in_str:
                if ch == "\\":
                    i += 2
                    continue
                if ch == in_str:
                    in_str = None
            else:
                if ch in "\"'":
                    in_str = ch
                elif ch == "#":
                    cut = i
                    break
            i += 1
        if cut >= 0:
            line = line[:cut].rstrip()
        out.append(line)
    return "\n".join(out)


def strip_docstrings(source):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                node.body.pop(0)
    return ast.unparse(tree)


def clean_text(source):
    source = strip_comments(source)
    source = strip_docstrings(source)
    lines = source.split("\n")
    result = []
    prev_empty = False
    for ln in lines:
        empty = not ln.strip()
        if empty and prev_empty:
            continue
        result.append(ln)
        prev_empty = empty
    while result and not result[0].strip():
        result.pop(0)
    while result and not result[-1].strip():
        result.pop()
    return "\n".join(result) + "\n"


def main():
    roots = [Path("currency_tracker")]
    files = []
    for r in roots:
        files += list(r.rglob("*.py"))
    changed = 0
    for fp in files:
        if "__pycache__" in str(fp):
            continue
        try:
            src = fp.read_text(encoding="utf-8")
            new = clean_text(src)
            if new != src:
                fp.write_text(new, encoding="utf-8")
                changed += 1
        except Exception as e:
            print(f"skip {fp}: {e}")
    print(f"Python files cleaned: {changed}")


if __name__ == "__main__":
    main()