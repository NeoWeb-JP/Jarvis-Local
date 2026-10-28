import importlib.util
import json
import math
import os
import sqlite3
import sys
import tempfile
import types
import unittest

import numpy as np

sys.modules.setdefault('soundfile', types.ModuleType('soundfile'))
spec = importlib.util.spec_from_file_location('candidate', os.path.join(os.path.dirname(__file__), 'speaker_id.py'))
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)


class ThresholdTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.temp.name, 'test.db')
        with sqlite3.connect(self.db) as conn:
            conn.execute('CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)')
            conn.execute('INSERT INTO settings VALUES (?, ?)', ('match_threshold', '0.47'))
        self.subject = candidate.SpeakerIdentifier.__new__(candidate.SpeakerIdentifier)
        self.subject._db_path = self.db
        self.subject._cache = {'Alex': np.array([1., 0.]), 'Bee': np.array([-1., 0.])}

    def tearDown(self):
        self.temp.cleanup()

    def set_override(self, value):
        with sqlite3.connect(self.db) as conn:
            conn.execute('INSERT OR REPLACE INTO settings VALUES (?, ?)', ('speaker_match_thresholds', value))

    def match(self, score):
        self.subject.extract_embedding = lambda _: np.array([score, math.sqrt(1 - score * score)])
        return self.subject.identify(b'test')[0]

    def test_missing_overrides_preserve_global_threshold(self):
        self.assertEqual(self.match(0.484), 'Alex')
        self.assertIsNone(self.match(0.46))

    def test_individual_thresholds_and_best_candidate_only(self):
        self.set_override(json.dumps({'alex': .50, 'BEE': .47}))
        self.assertIsNone(self.match(0.484))
        self.assertEqual(self.match(0.51), 'Alex')
        self.assertEqual(self.match(-0.474), 'Bee')
        self.assertIsNone(self.match(-0.46))

    def test_missing_person_uses_global_threshold(self):
        self.set_override(json.dumps({'alex': .50}))
        self.assertEqual(self.match(-0.48), 'Bee')

    def test_invalid_configuration_fails_closed(self):
        for value in ('bad json', '[]', '{"Alex": true}', '{"Alex": 1.1}', '{"Bee": 0.4, "bee": 0.5}'):
            with self.subTest(value=value):
                self.set_override(value)
                self.assertIsNone(self.match(0.8))

    def test_unavailable_database_fails_closed(self):
        self.subject._db_path = os.path.join(self.temp.name, 'missing.db')
        self.assertIsNone(self.match(0.8))


if __name__ == '__main__':
    unittest.main()
