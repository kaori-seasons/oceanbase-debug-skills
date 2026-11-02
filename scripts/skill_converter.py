#!/usr/bin/env python3
"""Validate the package, or create self-contained Codex/Claude/Cursor/Markdown bundles."""
import argparse
import json
import re
import shutil
import tempfile
from pathlib import Path
from common import ROOT, fences, frontmatter, markdown_files


def check(root=ROOT):
    errors = []
    skills = sorted(root.glob("oceanbase-*/SKILL.md"))
    if len(skills) != 12:
        errors.append(f"expected 12 skills, found {len(skills)}")
    for path in skills:
        try:
            meta = frontmatter(path)
            if set(meta) - {"name", "description", "metadata", "license", "allowed-tools"}:
                errors.append(f"{path}: unsupported frontmatter")
            if meta["name"] != path.parent.name or not re.fullmatch(r"[a-z0-9-]{1,64}", meta["name"]):
                errors.append(f"{path}: name/directory mismatch")
            if not isinstance(meta["description"], str) or not 20 <= len(meta["description"]) <= 1024:
                errors.append(f"{path}: invalid description")
            for key in ("version", "applies_to", "validation", "keywords"):
                if not isinstance(meta["metadata"].get(key), str) or not meta["metadata"][key]:
                    errors.append(f"{path}: missing string metadata.{key}")
            text = path.read_text(encoding="utf-8")
            if len(text.splitlines()) > 300:
                errors.append(f"{path}: entrypoint exceeds 300 lines; use references")
            for phase in range(1, 5):
                if f"## Phase {phase}" not in text:
                    errors.append(f"{path}: missing Phase {phase}")
        except (KeyError, ValueError) as exc:
            errors.append(f"{path}: {exc}")
    for path in markdown_files(root):
        text = path.read_text(encoding="utf-8")
        try:
            blocks = list(fences(text))
        except ValueError as exc:
            errors.append(f"{path}: {exc}")
            continue
        # Remove fenced content to avoid treating code strings as links/tables.
        lines = text.splitlines()
        for line, _, body in reversed(blocks):
            del lines[line - 1:line + len(body.splitlines()) + 1]
        prose = "\n".join(lines)
        for target in re.findall(r"(?<!!)\[[^\]]*\]\(([^)]+)\)", prose):
            if re.match(r"(?:https?://|mailto:|#)", target):
                continue
            relative = target.split("#", 1)[0]
            if not (path.parent / relative).is_file():
                errors.append(f"{path}: broken link {target}")
        previous = None
        for line in lines:
            if line.startswith("|"):
                count = len(re.split(r"(?<!\\)\|", line))
                if previous is not None and previous != count:
                    errors.append(f"{path}: inconsistent Markdown table")
                previous = count
            else:
                previous = None
        if path.name.startswith("case-"):
            try:
                meta = frontmatter(path)
                if meta["origin"] not in {"synthetic", "incident"} or not isinstance(meta["verified"], bool):
                    errors.append(f"{path}: invalid case provenance")
                if meta["origin"] == "synthetic" and meta["verified"]:
                    errors.append(f"{path}: synthetic case cannot be incident-verified")
                if meta["verified"] and not meta.get("verification_record"):
                    errors.append(f"{path}: verified incident lacks review record")
            except (KeyError, ValueError) as exc:
                errors.append(f"{path}: {exc}")
    return errors


def bundle(root, output, tool, force=False):
    """Stage entire output first; reject collisions and symlink targets before writes."""
    output = Path(output).expanduser()
    if output.is_symlink():
        raise ValueError("refusing a symlink target")
    output = output.resolve()
    root = root.resolve()
    if output == root or output.is_relative_to(root) or root.is_relative_to(output):
        raise ValueError("target must be outside the package tree and its ancestors")
    errors = check(root)
    if errors:
        raise ValueError("\n".join(errors))
    with tempfile.TemporaryDirectory(prefix="ob-skills-") as temporary:
        stage = Path(temporary)
        for skill in sorted(root.glob("oceanbase-*/SKILL.md")):
            name = skill.parent.name
            dest = stage / name
            shutil.copytree(skill.parent, dest)
            # Carry canonical shared resources AND related skills, so every handoff resolves.
        for directory in ("references", "guides", "scripts"):
            shutil.copytree(root / directory, stage / directory)
        if tool == "cursor":
            for skill in sorted(root.glob("oceanbase-*/SKILL.md")):
                data = frontmatter(skill)
                # Full content stays in sibling skill folder; all relative references stay valid.
                rule = ("---\n" + "description: " + json.dumps(data["description"], ensure_ascii=False)
                        + "\nalwaysApply: false\n---\n\n"
                        + f"Use [{data['name']}]({data['name']}/SKILL.md) for this symptom. Read its prerequisites before queries.\n")
                (stage / f"{data['name']}.mdc").write_text(rule, encoding="utf-8")
        targets = [(item, output / item.name) for item in stage.iterdir()]
        for _, target in targets:
            if target.is_symlink() or (target.exists() and not force):
                raise ValueError(f"target exists or is a symlink: {target}; review before --force")
        output.mkdir(parents=True, exist_ok=True)
        for source, target in targets:
            if target.exists():
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--sync", action="store_true", help="validate only, never rewrite source")
    modes.add_argument("--convert", choices=["codex", "claude-code", "cursor", "jetbrains"])
    parser.add_argument("--target", type=Path)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.sync:
        errors = check(args.root)
        print("\n".join(errors) if errors else "structure: PASS")
        return bool(errors)
    if not args.target:
        parser.error("--convert requires --target")
    try:
        bundle(args.root, args.target, args.convert, args.force)
    except (OSError, ValueError) as exc:
        print(exc)
        return 1
    print(f"Created {args.convert} bundle in {args.target}")
    if args.convert == "jetbrains":
        print("Markdown bundle only: no undocumented native JetBrains configuration is generated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
