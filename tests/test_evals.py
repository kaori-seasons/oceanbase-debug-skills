"""Evaluation bookkeeping invariants; these fake answers are not model evaluations."""
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('ob_evals', Path(__file__).resolve().parents[1] / 'evals/run.py')
evals = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evals)


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.data = evals.suite()
        self.responses = {'suite_id': self.data['suite_id'], 'run_id': 'unit-test-only', 'model': 'fake-test-fixture',
                          'responses': [{'id': s['id'], 'answer': 'Synthetic bookkeeping fixture.'} for s in self.data['scenarios']]}
        self.reviews = evals.review_template(self.data, self.responses)

    def fill_reviews(self):
        for review in self.reviews['reviews']:
            review['reviewer'] = 'unit-test-fixture'
            review['critical_failures'] = []
            review['critical_review_evidence'] = 'Test fixture only.'
            for check in review['checks'].values():
                check.update({'pass': True, 'evidence': 'Test fixture only.'})

    def test_blind_packet(self):
        packet = evals.prepare(self.data)
        self.assertEqual(len(packet['scenarios']), 20)
        for item in packet['scenarios']:
            self.assertEqual(set(item), {'id', 'prompt', 'environment', 'evidence'})

    def test_unreviewed_cannot_pass(self):
        with self.assertRaises(ValueError): evals.score(self.data, self.responses, self.reviews)

    def test_missing_cases_use_full_denominator(self):
        self.fill_reviews()
        self.reviews['reviews'] = self.reviews['reviews'][:16]
        result = evals.score(self.data, self.responses, self.reviews)
        self.assertEqual(result['pass_rate'], .8)
        self.assertFalse(result['gate_passed'])

    def test_eighty_percent_complete_can_pass(self):
        self.fill_reviews()
        for review in self.reviews['reviews'][:4]:
            review['checks']['reasoning']['pass'] = False
        self.assertTrue(evals.score(self.data, self.responses, self.reviews)['gate_passed'])

    def test_critical_failure_veto(self):
        self.fill_reviews()
        self.reviews['reviews'][0]['critical_failures'] = ['Invented execution.']
        self.assertFalse(evals.score(self.data, self.responses, self.reviews)['gate_passed'])

    def test_answer_changed(self):
        self.fill_reviews()
        self.responses['responses'][0]['answer'] = 'Changed answer'
        with self.assertRaises(ValueError): evals.score(self.data, self.responses, self.reviews)

    def test_duplicate_response(self):
        self.responses['responses'].append(self.responses['responses'][0])
        with self.assertRaises(ValueError): evals.review_template(self.data, self.responses)

    def test_unknown_review(self):
        self.fill_reviews()
        self.reviews['reviews'][0]['id'] = 'not-in-suite'
        with self.assertRaises(ValueError): evals.score(self.data, self.responses, self.reviews)


if __name__ == '__main__':
    unittest.main()
