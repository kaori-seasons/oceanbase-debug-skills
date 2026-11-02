#!/usr/bin/env python3
"""Validate a runtime capability snapshot. No OceanBase source checkout is needed."""
import argparse
import json
from metadata_probe import validate_snapshot

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metadata', required=True, help='JSON produced by metadata_probe.py --collect')
    args = parser.parse_args()
    try:
        with open(args.metadata, encoding='utf-8') as handle:
            snapshot = validate_snapshot(json.load(handle))
        for name, result in snapshot['results'].items():
            print(name + ': ' + result['status'])
        raise SystemExit(int(any(r['status'] != 'ok' for r in snapshot['results'].values())))
    except (OSError, ValueError) as exc:
        parser.exit(2, str(exc) + '\n')
