"""Shared offline validation. No connection to an OceanBase server is made."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLE_PATTERN = re.compile(r"\b(?:G?V\$[A-Z][A-Z0-9_$]*|(?:DBA|CDB)_OB_[A-Z0-9_]+|__all_virtual_[a-z0-9_]+)\b", re.I)


def frontmatter(path):
    # JSON is a YAML 1.2 subset. Deliberately require this subset for dependency-free tooling.
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) != 3 or parts[0].strip():
        raise ValueError(f"{path}: missing frontmatter")
    data = json.loads(parts[1])
    if not isinstance(data, dict):
        raise ValueError(f"{path}: frontmatter must be a mapping")
    return data


def fences(text):
    """Yield (opening line, info, body), including tilde and long fences."""
    opened = None
    body = []
    for line_number, line in enumerate(text.splitlines(), 1):
        match = re.match(r"^\s{0,3}(`{3,}|~{3,})(.*)$", line)
        if match and opened is None:
            opened = (line_number, match[1], match[2].strip())
            body = []
        elif opened and match and match[1][0] == opened[1][0] and len(match[1]) >= len(opened[1]) and not match[2].strip():
            yield opened[0], opened[2], "\n".join(body)
            opened = None
        elif opened:
            body.append(line)
    if opened:
        raise ValueError(f"unclosed fence at line {opened[0]}")


def markdown_files(root=ROOT):
    return sorted(root.rglob("*.md"))


def run_cli(check):
    import argparse
    parser = argparse.ArgumentParser(description=check.__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        errors = check(args.root.resolve())
    except (OSError, ValueError, KeyError) as exc:
        errors = [str(exc)]
    for error in errors:
        print(error)
    print(f"{check.__name__}: {'FAIL' if errors else 'PASS'}")
    raise SystemExit(bool(errors))
