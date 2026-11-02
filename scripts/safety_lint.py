#!/usr/bin/env python3
"""Conservative command review gate; never a SQL parser or an execution firewall."""
import re
from common import ROOT, fences, markdown_files, run_cli

L3 = re.compile(r"\b(?:force_\w*|remove_ls_replica|debug_sync|errsim|tracepoint|rm\s+-[^\n]*r|mkfs\w*|dd\s+if=)\b|\btrx_tool\b[^\n;]*\b(?:kill|modify)\b|\b(?:TRUNCATE|DROP)\s+(?:TABLE|DATABASE|TENANT)\b", re.I)
L2 = re.compile(r"\b(?:ALTER|INSERT|UPDATE|DELETE|REPLACE|CREATE|GRANT|REVOKE|KILL|SET|MERGE|CALL)\b|\b(?:gdb|pstack|gstack|perf|kill|sudo|ob_admin)\b", re.I)
SQL_COMMENT = re.compile(r"/\*.*?\*/|--[^\n]*", re.S)
STRING = re.compile(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"")


def inspect(info, body):
    """Return review errors for a fenced block (including unknown languages)."""
    lang = info.split()[0] if info else ""
    if lang in {"json", "yaml", "text", "markdown"}:
        # Executable-looking dangerous examples may not hide behind a text label.
        if L3.search(body) or re.search(r"^\s*(?:ALTER\s+SYSTEM|KILL\s+\d|DELETE\s+FROM|SET\s+\w+\s*=)", body, re.I | re.M):
            return ["executable command disguised as data"]
        return []
    if lang == "sql":
        # Inspect versioned comments too: removing /*!...*/ would hide executable SQL.
        versioned = re.sub(r"/\*!\d*\s*(.*?)\*/", r"\1", body, flags=re.S)
        executable = STRING.sub("''", SQL_COMMENT.sub(" ", versioned))
    else:
        executable = "\n".join(l for l in body.splitlines() if not l.lstrip().startswith("#"))
    if not executable.strip():
        return []
    if L3.search(executable):
        return ["L3 executable examples are forbidden; describe the escalation in prose"]
    level = re.search(r"(?:^|\s)safety=(L[0-3])(?:\s|$)", info)
    if not level:
        return ["command block lacks safety=L0/L1/L2"]
    if lang == "sql" and not re.search(r"\bcontext=\S+", info):
        return ["SQL block lacks tenant context"]
    if L2.search(executable) and level[1] not in {"L1", "L2"}:
        return ["mutation or intrusive diagnostic mislabeled L0"]
    if level[1] == "L1" and not re.fullmatch(r"\s*SET\s+(?:SESSION\s+)?ob_enable_trace_log\s*=\s*(?:1|0|ON|OFF)\s*;?\s*", executable, re.I):
        return ["L1 allowlist covers only session ob_enable_trace_log"]
    if level[1] in {"L1", "L2"}:
        required = ("approval=required", "impact=", "rollback=", "verify=", "⚠")
        if any(item not in info for item in required):
            return ["L1/L2 requires warning, approval, impact, rollback and verification metadata"]
    if lang == "sql":
        for statement in executable.split(";"):
            if re.search(r"\b(?:UPDATE|DELETE)\b", statement, re.I) and not re.search(r"\bWHERE\b", statement, re.I):
                return ["unscoped DML is forbidden"]
        if re.search(r"\b(?:OUTFILE|DUMPFILE|LOAD_FILE|SLEEP|BENCHMARK|GET_LOCK)\b", executable, re.I):
            return ["read-shaped SQL has side effects or unbounded load"]
    return []


def check(root=ROOT, source_root=None):
    """Scan all Markdown fences, not just those marked sql/bash."""
    errors = []
    for path in markdown_files(root):
        try:
            for line, info, body in fences(path.read_text(encoding="utf-8")):
                errors.extend(f"{path}:{line}: {e}" for e in inspect(info, body))
        except ValueError as exc:
            errors.append(f"{path}: {exc}")
    return errors


if __name__ == "__main__":
    run_cli(check)
