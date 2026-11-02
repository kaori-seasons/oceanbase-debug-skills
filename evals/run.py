#!/usr/bin/env python3
"""Prepare blind replay inputs and aggregate evidence-backed human reviews; never call a model or database."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def suite(path=HERE / 'scenarios.json'):
    data = read(path)
    if data.get('schema_version') != 1 or len(data.get('scenarios', [])) != 20:
        raise ValueError('expected version 1 suite with 20 scenarios')
    seen = set()
    covered = set()
    for item in data['scenarios']:
        if not item.get('id') or item['id'] in seen or item.get('origin') != 'synthetic':
            raise ValueError('duplicate/missing scenario id or unsupported provenance')
        seen.add(item['id'])
        for key in ('prompt', 'environment', 'evidence'):
            if not isinstance(item['input'].get(key), str) or not item['input'][key].strip():
                raise ValueError('missing input ' + key)
        expected = item['expected']
        criteria = expected['criteria']
        if len({c['id'] for c in criteria}) != 3 or any(not c['description'].strip() for c in criteria):
            raise ValueError('expected three unique criteria')
        if not expected['critical_failures'] or not expected['acceptable_primary_skills']:
            raise ValueError('missing route or critical failure criteria')
        for name in expected['acceptable_primary_skills'] + expected['handoffs']:
            if not (HERE.parent / name / 'SKILL.md').is_file():
                raise ValueError('unknown skill: ' + name)
        covered.update(expected['acceptable_primary_skills'])
    if len(covered) != 12:
        raise ValueError('all 12 primary domains must be covered')
    return data


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def prepare(data):
    # Do not expose expected routes or rubric to the model under test.
    return {'suite_id': data['suite_id'], 'instructions': '在独立会话中加载技能包，对每项返回自然语言回答；保留原始回答。禁止联网、连接生产或执行变更。',
            'scenarios': [{'id': s['id'], **s['input']} for s in data['scenarios']]}


def index(items, allowed, kind):
    result = {}
    for item in items:
        ident = item.get('id')
        if ident not in allowed or ident in result:
            raise ValueError('unknown/duplicate ' + kind + ' id: ' + str(ident))
        result[ident] = item
    return result


def review_template(data, responses):
    ids = {s['id'] for s in data['scenarios']}
    by_id = index(responses['responses'], ids, 'response')
    if responses.get('suite_id') != data['suite_id'] or not responses.get('model') or not responses.get('run_id'):
        raise ValueError('responses require matching suite_id, model and run_id')
    reviews = []
    for scenario in data['scenarios']:
        if scenario['id'] not in by_id:
            continue
        answer = by_id[scenario['id']]['answer']
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError('empty answer')
        keys = ['routing'] + [c['id'] for c in scenario['expected']['criteria']]
        reviews.append({'id': scenario['id'], 'answer_sha256': digest(answer),
                        'reviewer': '', 'checks': {k: {'pass': None, 'evidence': ''} for k in keys},
                        'critical_failures': None, 'critical_review_evidence': ''})
    return {'suite_id': data['suite_id'], 'run_id': responses['run_id'], 'reviews': reviews}


def score(data, responses, reviews):
    template = review_template(data, responses)
    expected = {r['id']: r for r in template['reviews']}
    if reviews.get('suite_id') != data['suite_id'] or reviews.get('run_id') != responses['run_id']:
        raise ValueError('review suite/run mismatch')
    by_id = index(reviews['reviews'], {s['id'] for s in data['scenarios']}, 'review')
    results = []
    for scenario in data['scenarios']:
        ident = scenario['id']
        review = by_id.get(ident)
        if ident not in expected or not review:
            results.append({'id': ident, 'status': 'missing'})
            continue
        if review.get('answer_sha256') != expected[ident]['answer_sha256']:
            raise ValueError('review does not match raw answer: ' + ident)
        checks = review.get('checks', {})
        if set(checks) != set(expected[ident]['checks']):
            raise ValueError('missing/unknown review criteria: ' + ident)
        if not isinstance(review.get('reviewer'), str) or not review['reviewer'].strip():
            raise ValueError('reviewer required: ' + ident)
        for value in checks.values():
            if type(value.get('pass')) is not bool or not isinstance(value.get('evidence'), str) or not value['evidence'].strip():
                raise ValueError('each judgment requires boolean and answer evidence: ' + ident)
        critical = review.get('critical_failures')
        if not isinstance(critical, list) or any(not isinstance(v, str) or not v.strip() for v in critical):
            raise ValueError('explicit critical failure list required: ' + ident)
        if not isinstance(review.get('critical_review_evidence'), str) or not review['critical_review_evidence'].strip():
            raise ValueError('critical review evidence required: ' + ident)
        passed = all(v['pass'] for v in checks.values()) and not critical
        results.append({'id': ident, 'status': 'pass' if passed else 'fail', 'critical': bool(critical)})
    passed = sum(r['status'] == 'pass' for r in results)
    complete = all(r['status'] != 'missing' for r in results)
    critical = any(r.get('critical') for r in results)
    rate = passed / len(results)
    return {'suite_id': data['suite_id'], 'run_id': responses['run_id'], 'model': responses['model'],
            'complete': complete, 'passed': passed, 'total': len(results), 'pass_rate': rate,
            'gate_passed': complete and rate >= 0.8 and not critical, 'critical_failure': critical,
            'results': results, 'scope': 'human-reviewed synthetic model replay; not live-cluster validation'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['validate', 'prepare', 'review-template', 'score'])
    parser.add_argument('--responses', type=Path)
    parser.add_argument('--reviews', type=Path)
    args = parser.parse_args()
    try:
        data = suite()
        if args.command == 'validate':
            result = {'status': 'valid', 'scenarios': 20, 'model_evaluation': 'not_run'}
        elif args.command == 'prepare':
            result = prepare(data)
        else:
            if not args.responses:
                parser.error('--responses is required')
            responses = read(args.responses)
            if args.command == 'review-template':
                result = review_template(data, responses)
            else:
                if not args.reviews:
                    parser.error('--reviews is required')
                result = score(data, responses, read(args.reviews))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return int(args.command == 'score' and not result['gate_passed'])
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        parser.exit(2, str(exc) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
