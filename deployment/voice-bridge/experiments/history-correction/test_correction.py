"""Exercise the candidate's real database functions without HA dependencies."""
import ast
import asyncio
import contextlib
import datetime
import json
import logging
import os
import sqlite3
import tempfile
import threading
import types
import unittest
import uuid

source = open(os.path.join(os.path.dirname(__file__), 'api.py'), encoding='utf-8').read()
tree = ast.parse(source)
names = {'_get_connection', '_fetch_history', '_audio_url', '_correct_interaction', 'CorrectionConflict', 'correct_interaction'}
selected = [node for node in tree.body if getattr(node, 'name', None) in names]
for node in selected:
    if getattr(node, 'name', None) == 'correct_interaction':
        node.decorator_list = []
        node.args.args[1].annotation = None
        node.args.args[2].annotation = None
class HTTPException(Exception):
    def __init__(self, status_code, detail): self.status_code, self.detail = status_code, detail
namespace = {
    'sqlite3': sqlite3, 'json': json, 'os': os, 'uuid': uuid,
    'datetime': datetime.datetime, 'timezone': datetime.timezone,
    'timedelta': datetime.timedelta, 'closing': contextlib.closing,
    'asyncio': asyncio, 'HTTPException': HTTPException, 'logger': logging.getLogger('test'),
}
exec(compile(ast.Module(body=selected, type_ignores=[]), 'candidate_api', 'exec'), namespace)


class CorrectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, 'speaker.db')
        namespace['DB_PATH'] = self.path
        with sqlite3.connect(self.path) as db:
            db.executescript('''
                CREATE TABLE enrolled_speakers (id TEXT PRIMARY KEY, name TEXT, reference_clips TEXT, interaction_count INTEGER);
                CREATE TABLE interactions (id TEXT PRIMARY KEY, recorded_at TEXT, transcript TEXT, duration_ms INTEGER,
                    vad_confidence REAL, matched_speaker TEXT, match_confidence REAL, status TEXT, audio_path TEXT, timings TEXT);
                CREATE TABLE resolutions (id TEXT PRIMARY KEY, interaction_id TEXT, resolved_at TEXT, action TEXT, assigned_to TEXT);
            ''')
            db.executemany('INSERT INTO enrolled_speakers VALUES (?,?,?,?)', [
                ('j', 'Jaco', json.dumps(['/audio/keep', '/audio/voice', '/audio/voice']), 12),
                ('e', 'Ed', json.dumps(['/audio/ed']), 9),
            ])
            db.execute('INSERT INTO interactions VALUES (?,?,?,?,?,?,?,?,?,?)',
                ('i', '2026-10-28T15:00:00+00:00', 'Good morning.', 800, .8, 'Jaco', .48, 'resolved', '/audio/voice', None))
            db.execute('INSERT INTO resolutions VALUES (?,?,?,?,?)',
                ('r1', 'i', '2026-10-28T15:00:01+00:00', 'assign', 'Jaco'))

    def tearDown(self):
        self.temp.cleanup()

    def state(self):
        with sqlite3.connect(self.path) as db:
            refs = {name: json.loads(clips) for name, clips in db.execute('SELECT name, reference_clips FROM enrolled_speakers')}
            status = db.execute('SELECT status FROM interactions WHERE id=?', ('i',)).fetchone()[0]
            resolutions = db.execute('SELECT id, action, assigned_to FROM resolutions ORDER BY resolved_at, rowid').fetchall()
            counts = db.execute('SELECT name, interaction_count FROM enrolled_speakers ORDER BY name').fetchall()
        return refs, status, resolutions, counts

    def test_correct_speaker_removes_only_wrong_references_and_preserves_history(self):
        result = namespace['_correct_interaction']('i', 'Ed', 'r1')
        refs, status, resolutions, counts = self.state()
        self.assertEqual(result['removed_references'], 2)
        self.assertEqual(refs, {'Jaco': ['/audio/keep'], 'Ed': ['/audio/ed']})
        self.assertEqual(status, 'resolved')
        self.assertEqual(resolutions[0], ('r1', 'assign', 'Jaco'))
        self.assertEqual(resolutions[-1][1:], ('assign', 'Ed'))
        self.assertEqual(counts, [('Ed', 9), ('Jaco', 12)])
        history = namespace['_fetch_history']('Ed', None, None)
        self.assertEqual(history[0]['current_assigned_to'], 'Ed')
        self.assertEqual(history[0]['matched_speaker'], 'Jaco')
        self.assertEqual(namespace['_fetch_history']('Jaco', None, None), [])

    def test_undo_returns_to_pending_and_removes_wrong_references(self):
        namespace['_correct_interaction']('i', None, 'r1')
        refs, status, resolutions, _ = self.state()
        self.assertEqual(status, 'pending')
        self.assertEqual(resolutions[-1][1:], ('unassign', None))
        self.assertEqual(refs['Jaco'], ['/audio/keep'])
        self.assertEqual(namespace['_fetch_history']('Jaco', None, None), [])

    def test_stale_resolution_or_missing_speaker_never_changes_data(self):
        before = self.state()
        for target, resolution in [('Ed', 'stale'), ('Missing', 'r1')]:
            with self.assertRaises(namespace['CorrectionConflict']):
                namespace['_correct_interaction']('i', target, resolution)
            self.assertEqual(before, self.state())

    def test_invalid_later_reference_list_rolls_back_earlier_changes(self):
        with sqlite3.connect(self.path) as db:
            db.execute('INSERT INTO enrolled_speakers VALUES (?,?,?,?)', ('x', 'Other', 'bad json', 1))
        with self.assertRaises(namespace['CorrectionConflict']):
            namespace['_correct_interaction']('i', 'Ed', 'r1')
        with sqlite3.connect(self.path) as db:
            self.assertEqual(json.loads(db.execute('SELECT reference_clips FROM enrolled_speakers WHERE id=?', ('j',)).fetchone()[0]), ['/audio/keep', '/audio/voice', '/audio/voice'])
            self.assertEqual(db.execute('SELECT COUNT(*) FROM resolutions').fetchone()[0], 1)

    def test_missing_audio_path_is_rejected(self):
        with sqlite3.connect(self.path) as db:
            db.execute('UPDATE interactions SET audio_path=NULL')
        with self.assertRaises(namespace['CorrectionConflict']):
            namespace['_correct_interaction']('i', 'Ed', 'r1')

    def test_old_automatically_resolved_without_resolution_can_be_corrected(self):
        with sqlite3.connect(self.path) as db:
            db.execute('DELETE FROM resolutions')
        namespace['_correct_interaction']('i', 'Ed', None)
        self.assertEqual(self.state()[2][-1][1:], ('assign', 'Ed'))

    def test_refresh_failure_does_not_report_a_saved_correction_as_failed(self):
        class Sid:
            def force_refresh(self): raise RuntimeError('offline')
        request = types.SimpleNamespace(app=types.SimpleNamespace(state=types.SimpleNamespace(sid=Sid())))
        body = types.SimpleNamespace(assigned_to='Ed', expected_resolution_id='r1')
        with self.assertLogs('test', level='ERROR'):
            result = asyncio.run(namespace['correct_interaction']('i', body, request))
        self.assertFalse(result['cache_refresh_requested'])
        self.assertEqual(self.state()[2][-1][1:], ('assign', 'Ed'))

    def test_two_stale_tabs_cannot_both_win(self):
        barrier = threading.Barrier(2)
        outcomes = []
        def attempt(target):
            barrier.wait()
            try:
                namespace['_correct_interaction']('i', target, 'r1')
                outcomes.append('saved')
            except namespace['CorrectionConflict']:
                outcomes.append('conflict')
        threads = [threading.Thread(target=attempt, args=(target,)) for target in ('Ed', None)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertCountEqual(outcomes, ['saved', 'conflict'])
        self.assertEqual(len(self.state()[2]), 2)


if __name__ == '__main__':
    unittest.main()
