import re
from pathlib import Path


def strip_ts(source):
    source = re.sub(r"/\*\*[\s\S]*?\*/", "", source)
    source = re.sub(r"/\*[\s\S]*?\*/", "", source)
    lines = source.split("\n")
    out = []
    for line in lines:
        in_s = None
        i = 0
        cut = -1
        while i < len(line):
            ch = line[i]
            if in_s:
                if ch == "\\":
                    i += 2
                    continue
                if ch == in_s:
                    in_s = None
            else:
                if ch in "\"'`":
                    in_s = ch
                elif ch == "/" and i + 1 < len(line) and line[i + 1] == "/":
                    cut = i
                    break
            i += 1
        if cut >= 0:
            line = line[:cut].rstrip()
        out.append(line)
    source = "\n".join(out)
    result = []
    prev_empty = False
    for ln in source.split("\n"):
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
    base = Path("frontend/src")
    files = list(base.rglob("*.ts")) + list(base.rglob("*.tsx"))
    changed = 0
    for fp in files:
        if "node_modules" in str(fp):
            continue
        try:
            src = fp.read_text(encoding="utf-8")
            new = strip_ts(src)
            if new != src:
                fp.write_text(new, encoding="utf-8")
                changed += 1
        except Exception as e:
            print(f"skip {fp}: {e}")
    print(f"Frontend files cleaned: {changed}")


if __name__ == "__main__":
    main()