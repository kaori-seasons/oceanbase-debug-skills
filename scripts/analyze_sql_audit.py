#!/usr/bin/env python3
"""Stream a CSV/TSV SQL_AUDIT export into bounded TOP-N; emit no SQL or client identifiers."""
import argparse
import csv
import heapq
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

METRICS = ("elapsed_time", "execute_time", "queue_time", "get_plan_time", "request_memory_used", "return_rows", "affected_rows", "disk_reads")


def analyze(path, metric="elapsed_time", top=20, delimiter=None):
    if metric not in METRICS or not 1 <= top <= 10000:
        raise ValueError("unsupported metric or top outside 1..10000")
    heap = []
    count = 0
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        if delimiter is None:
            # Header only: embedded SQL commas/tabs/newlines must not influence sniffing.
            header = handle.readline()
            delimiter = "\t" if header.count("\t") > header.count(",") else ","
            handle.seek(0)
        reader = csv.DictReader(handle, delimiter=delimiter)
        if not reader.fieldnames:
            raise ValueError("empty export")
        fields = [f.strip().lower() for f in reader.fieldnames]
        if len(set(fields)) != len(fields) or metric not in fields:
            raise ValueError("duplicate headers or metric column missing")
        for row_number, raw in enumerate(reader, 2):
            if None in raw or any(value is None for value in raw.values()):
                raise ValueError(f"malformed record {row_number}")
            row = dict(zip(fields, raw.values()))
            try:
                value = Decimal(row[metric])
                if not value.is_finite() or value < 0:
                    raise ValueError()
            except (InvalidOperation, ValueError):
                raise ValueError(f"invalid {metric} at record {row_number}") from None
            count += 1
            # Only retain numeric score + a local row index. Source may contain customer data.
            item = (value, -row_number)
            if len(heap) < top:
                heapq.heappush(heap, item)
            elif item > heap[0]:
                heapq.heapreplace(heap, item)
    return {"metric": metric, "unit": "us" if metric.endswith("_time") else ("bytes" if metric == "request_memory_used" else "count"),
            "records": count, "top": [{"record": -row, "value": str(value)} for value, row in sorted(heap, reverse=True)],
            "scope": "exported rows only; no inference about lost audit records or the full incident"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--metric", choices=METRICS, default="elapsed_time")
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--delimiter", choices=["csv", "tsv"])
    args = parser.parse_args()
    try:
        result = analyze(args.path, args.metric, args.top, {"csv": ",", "tsv": "\t"}.get(args.delimiter))
    except (OSError, ValueError, csv.Error) as exc:
        parser.exit(2, f"{exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
