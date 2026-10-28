import json
import tempfile
import unittest
from pathlib import Path
import test_commands
from jarvis_test.voice_profiles import public_profiles, save_profiles_file, validate_profiles

class VoiceProfilesTests(unittest.TestCase):
    def test_round_trip_keeps_private_and_unknown_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'voice.json'
            path.write_text(json.dumps({'secret':'private','profiles':{'jaco':{'name':'Jaco','private_extra':'kept'}}}))
            profiles=validate_profiles({'jaco':{'name':'Jaco','min_confidence':0.5,'morning_responses':['Hello {name}']}})
            saved=save_profiles_file(path,profiles)
            self.assertEqual(saved['secret'],'private')
            self.assertEqual(saved['profiles']['jaco']['private_extra'],'kept')
            self.assertNotIn('secret',public_profiles(saved))
            self.assertNotIn('private_extra',public_profiles(saved)['jaco'])
            self.assertEqual(json.loads(path.read_text()),saved)
    def test_invalid_file_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'voice.json';path.write_text('{invalid')
            with self.assertRaises(ValueError):save_profiles_file(path,{})
            self.assertEqual(path.read_text(),'{invalid')
    def test_invalid_thresholds_and_duplicate_names(self):
        for value in [-1, 2, float('nan'), True]:
            with self.assertRaises(ValueError):validate_profiles({'jaco':{'name':'Jaco','min_confidence':value}})
        with self.assertRaises(ValueError):validate_profiles({'a':{'name':'Ed'},'b':{'name':'ed'}})
