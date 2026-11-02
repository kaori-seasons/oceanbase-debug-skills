import copy
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from metadata_probe import CATALOG, collect, plan, quote, statements, validate_snapshot, classify_error
from analyze_sql_audit import analyze
from skill_converter import bundle, check
from safety_lint import inspect


def snapshot(domain='transaction'):
    item = CATALOG[domain]
    return {'format_version': 1, 'mode': 'mysql', 'domain': domain,
            'results': {item['primary']: {'status': 'ok', 'columns': item['columns']}}}


class MetadataTests(unittest.TestCase):
    def test_probe_is_metadata_only(self):
        for domain in CATALOG:
            for _, sql in statements(domain):
                self.assertTrue(sql.startswith(('SELECT VERSION()', 'SHOW ')))
                self.assertNotIn('src/', sql)

    def test_all_domain_plans(self):
        for domain in CATALOG:
            sql = plan(snapshot(domain), domain, 1001, 100, 1000)
            self.assertIn('LIMIT 20', sql)
            if 'TENANT_ID' in CATALOG[domain]['columns']:
                self.assertIn('`TENANT_ID` = 1001', sql)

    def test_lock_plan(self):
        sql = plan(snapshot(), 'transaction', 1001, None, None)
        self.assertIn("`REQUEST` <> 'NONE'", sql)
        self.assertNotIn('need_wait', sql)

    def test_missing_column_stops(self):
        data = snapshot(); data['results'][CATALOG['transaction']['primary']]['columns'] = ['TRANS_ID']
        with self.assertRaises(ValueError): plan(data, 'transaction', 1001, None, None)

    def test_missing_or_denied_stops(self):
        for status in ['missing', 'denied', 'timeout', 'connection']:
            data = snapshot(); data['results'][CATALOG['transaction']['primary']] = {'status': status}
            with self.assertRaises(ValueError): plan(data, 'transaction', 1001, None, None)

    def test_window_and_scope(self):
        for tenant, start, end in [(0, 1, 2), (1001, 2, 1), (1001, 0, 3600000001), (1001, None, None)]:
            with self.assertRaises(ValueError): plan(snapshot('query'), 'query', tenant, start, end)

    def test_wrong_domain(self):
        with self.assertRaises(ValueError): plan(snapshot(), 'write', 1001, None, None)

    def test_oracle_rejected(self):
        data = snapshot(); data['mode'] = 'oracle'
        with self.assertRaises(ValueError): validate_snapshot(data)

    def test_identifier_injection(self):
        for value in ['x; DROP TABLE t', 'x`', 'x.y', '', None]:
            with self.assertRaises(ValueError): quote(value)

    def test_error_categories(self):
        for code, expected in [(1146, 'missing'), (1142, 'denied'), (2003, 'connection'), (9999, 'error')]:
            self.assertEqual(classify_error(f'ERROR {code} sensitive details')['status'], expected)
            self.assertNotIn('sensitive', str(classify_error(f'ERROR {code} sensitive details')))

    def test_timeout_stops_collection(self):
        with tempfile.TemporaryDirectory() as temp:
            cfg = Path(temp) / 'my.cnf'; cfg.write_text('[client]\n'); cfg.chmod(0o600)
            with patch('metadata_probe.subprocess.run', side_effect=subprocess.TimeoutExpired('mysql', 10)) as call:
                result = collect('query', cfg, 'example.invalid', 2881, 'diag')
                self.assertEqual(call.call_count, 1)
                self.assertEqual(result['results']['identity']['status'], 'timeout')

    def test_collect_parses_columns(self):
        with tempfile.TemporaryDirectory() as temp:
            cfg = Path(temp) / 'my.cnf'; cfg.write_text('[client]\n'); cfg.chmod(0o600)
            response = subprocess.CompletedProcess([], 0, 'Field\tType\nTENANT_ID\tbigint\n', '')
            mode = subprocess.CompletedProcess([], 0, 'Variable_name\tValue\nob_compatibility_mode\tMYSQL\n', '')
            with patch('metadata_probe.subprocess.run', side_effect=[response, mode, response, response]) as call:
                result = collect('query', cfg, 'example.invalid', 2881, 'diag')
                self.assertEqual(result['results']['GV$OB_SQL_AUDIT']['columns'], ['TENANT_ID'])
                self.assertNotIn('shell', call.call_args.kwargs)


class AuditTests(unittest.TestCase):
    def test_multiline_and_large_integer(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'audit.csv'
            with path.open('w', newline='') as handle:
                writer = csv.writer(handle); writer.writerow(['ELAPSED_TIME', 'QUERY_SQL'])
                writer.writerows([['9007199254740993', 'private\nselect'], ['9007199254740992', 'secret']])
            result = analyze(path, top=1)
            self.assertEqual(result['top'][0]['value'], '9007199254740993')
            self.assertNotIn('private', str(result))

    def test_reject_bad_numeric(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'audit.csv'
            for value in ['NaN', 'Infinity', '-1', 'garbage']:
                path.write_text('elapsed_time\n' + value + '\n')
                with self.assertRaises(ValueError): analyze(path)

    def test_tsv_and_duplicates(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'a.tsv'; path.write_text('ELAPSED_TIME\tSQL_ID\n12\tx\n')
            self.assertEqual(analyze(path)['records'], 1)
            path.write_text('elapsed_time,ELAPSED_TIME\n1,2\n')
            with self.assertRaises(ValueError): analyze(path)


class PackageTests(unittest.TestCase):
    def test_package_structure(self):
        self.assertEqual(check(ROOT), [])

    def test_install_without_source_checkout(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'skills'
            bundle(ROOT, target, 'codex')
            self.assertEqual(check(target), [])
            run = subprocess.run([sys.executable, str(target / 'scripts/metadata_probe.py'), '--emit-sql', '--domain', 'write'], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn('SHOW COLUMNS', run.stdout)
            with self.assertRaises(ValueError): bundle(ROOT, target, 'codex')

    def test_installer_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'link'; target.symlink_to(ROOT, target_is_directory=True)
            with self.assertRaises(ValueError): bundle(ROOT, target, 'codex')

    def test_safety_mutations(self):
        for sql in ['ALTER SYSTEM SET x=1;', 'DELETE FROM t;', '/*!50000 DROP TABLE t */;', 'SELECT SLEEP(20);']:
            self.assertTrue(inspect('sql safety=L0 context=user', sql))
        self.assertEqual(inspect('sql safety=L0 context=user', "SHOW VARIABLES LIKE 'ob_query_timeout';"), [])

    def test_safety_unknown_language(self):
        self.assertTrue(inspect('text', 'ALTER SYSTEM SET x=1;'))
        self.assertTrue(inspect('bash safety=L0', 'ob_admin force_remove'))


if __name__ == '__main__':
    unittest.main()
