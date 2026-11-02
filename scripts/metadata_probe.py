#!/usr/bin/env python3
"""Emit or collect read-only MySQL metadata; generate capability-gated diagnostic SQL."""
import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / 'references/catalog.json').read_text())
IDENT = re.compile(r'^[A-Za-z_][A-Za-z0-9_$]*$')


def quote(name):
    if not isinstance(name, str) or not IDENT.fullmatch(name):
        raise ValueError('invalid SQL identifier')
    return '`' + name + '`'


def statements(domain):
    item = CATALOG[domain]
    result = [('identity', 'SELECT VERSION() AS version, CURRENT_USER() AS account, DATABASE() AS current_database;'),
              ('mode', "SHOW VARIABLES LIKE 'ob_compatibility_mode';")]
    for table in [item['primary'], *item['additional']]:
        result.append((table, 'SHOW COLUMNS FROM oceanbase.' + quote(table) + ';'))
    return result


def classify_error(stderr):
    match = re.search(r'ERROR\s+(\d+)', stderr, re.I)
    code = int(match[1]) if match else None
    category = ('denied' if code in {1044, 1045, 1142, 1227} else
                'missing' if code in {1051, 1109, 1146} else
                'connection' if code in {2002, 2003, 2006, 2013} else 'error')
    return {'status': category, 'error_code': code}


def collect(domain, defaults_file, host, port, user, timeout=10, client='mysql'):
    config = Path(defaults_file).expanduser()
    if not config.is_file() or config.is_symlink():
        raise ValueError('defaults file must be a regular, non-symlink file')
    if os.name == 'posix' and config.stat().st_mode & 0o077:
        raise ValueError('defaults file must not be readable by group/others (use mode 0600)')
    base = [client, '--defaults-extra-file=' + str(config.resolve()), '--batch', '--raw',
            '--connect-timeout=5', '--host=' + host, '--port=' + str(port), '--user=' + user]
    results = {}
    for key, sql in statements(domain):
        try:
            run = subprocess.run(base + ['--execute=' + sql], capture_output=True, text=True,
                                 timeout=timeout, check=False)
        except subprocess.TimeoutExpired:
            results[key] = {'status': 'timeout'}
            break  # Stop at first timeout; do not amplify an overloaded cluster.
        if run.returncode:
            results[key] = classify_error(run.stderr)
            if results[key]['status'] in {'connection', 'denied'} and key in {'identity', 'mode'}:
                break
            continue
        lines = run.stdout.splitlines()
        if key not in {'identity', 'mode'}:
            columns = [line.split('\t')[0].upper() for line in lines[1:] if line]
            if not columns or any(not IDENT.fullmatch(c) for c in columns):
                results[key] = {'status': 'invalid_output'}
            else:
                results[key] = {'status': 'ok', 'columns': columns}
        else:
            # Local identity context can be sensitive; never upload this snapshot by default.
            results[key] = {'status': 'ok', 'rows': [line.split('\t') for line in lines]}
            if key == 'mode' and not any(line.split('\t')[-1].upper() == 'MYSQL' for line in lines[1:]):
                results[key] = {'status': 'invalid_output'}
                break
    return {'format_version': 1, 'captured_at': datetime.now(timezone.utc).isoformat(),
            'domain': domain, 'mode': 'mysql', 'scope': 'connected account only', 'results': results}


def validate_snapshot(snapshot):
    if snapshot.get('format_version') != 1 or snapshot.get('mode') != 'mysql':
        raise ValueError('unsupported metadata format or mode')
    results = snapshot.get('results')
    if not isinstance(results, dict):
        raise ValueError('missing results')
    for table, result in results.items():
        if not isinstance(result, dict) or result.get('status') not in {'ok', 'timeout', 'missing', 'denied', 'connection', 'error', 'invalid_output'}:
            raise ValueError('invalid result status')
        if table not in {'identity', 'mode'}:
            quote(table)
            if result['status'] == 'ok':
                columns = result.get('columns')
                if not isinstance(columns, list) or not columns:
                    raise ValueError('missing column list')
                for column in columns:
                    quote(column)
    return snapshot


def plan(snapshot, domain, tenant_id, start_us, end_us):
    validate_snapshot(snapshot)
    if snapshot.get('domain') != domain:
        raise ValueError('snapshot belongs to another domain; probe the requested domain')
    if tenant_id is None or tenant_id <= 0:
        raise ValueError('a verified positive tenant-id is required')
    item = CATALOG[domain]
    result = snapshot['results'].get(item['primary'], {})
    if result.get('status') != 'ok':
        raise ValueError('primary view unavailable; inspect status, permissions and version; do not infer health')
    available = {c.upper() for c in result['columns']}
    wanted = item['columns']
    missing = set(wanted) - available
    if missing:
        raise ValueError('view differs from this recipe; manually adapt after checking semantics: ' + ', '.join(sorted(missing)))
    filters = []
    if 'TENANT_ID' in available:
        filters.append('`TENANT_ID` = ' + str(tenant_id))
    elif not item['primary'].startswith('DBA_OB_'):
        raise ValueError('cannot enforce tenant scope for this view')
    if domain == 'query':
        if start_us is None or end_us is None or start_us < 0 or not 0 < end_us - start_us <= 3600000000:
            raise ValueError('provide epoch microsecond window of >0 and <=1 hour')
        filters.append(f'`REQUEST_TIME` >= {start_us} AND `REQUEST_TIME` < {end_us}')
    if domain == 'transaction':
        filters.append("`REQUEST` <> 'NONE'")
    sql = 'SELECT ' + ', '.join(quote(c) for c in wanted) + '\nFROM oceanbase.' + quote(item['primary'])
    if filters:
        sql += '\nWHERE ' + ' AND '.join(filters)
    sql += '\nLIMIT 20;'
    return ('-- L0; MySQL mode; verify connected tenant/account and snapshot age before execution.\n'
            '-- DBA views may show only the connected tenant. LIMIT bounds output, not scan cost.\n' + sql)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--emit-sql', action='store_true')
    modes.add_argument('--collect', action='store_true')
    modes.add_argument('--plan', type=Path)
    parser.add_argument('--domain', choices=sorted(CATALOG), required=True)
    parser.add_argument('--defaults-extra-file', type=Path)
    parser.add_argument('--host')
    parser.add_argument('--port', type=int, default=2881)
    parser.add_argument('--user')
    parser.add_argument('--tenant-id', type=int)
    parser.add_argument('--start-us', type=int)
    parser.add_argument('--end-us', type=int)
    args = parser.parse_args()
    try:
        if args.emit_sql:
            print('\n'.join(sql for _, sql in statements(args.domain)))
        elif args.plan:
            print(plan(json.loads(args.plan.read_text()), args.domain, args.tenant_id, args.start_us, args.end_us))
        else:
            if not args.defaults_extra_file or not args.host or not args.user or not 1 <= args.port <= 65535:
                parser.error('--collect requires --defaults-extra-file, --host, --user and a valid port')
            snapshot = collect(args.domain, args.defaults_extra_file, args.host, args.port, args.user)
            print(json.dumps(snapshot, ensure_ascii=False, indent=2))
            return int(any(r['status'] != 'ok' for r in snapshot['results'].values()))
    except (OSError, ValueError) as exc:
        parser.exit(2, str(exc) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
