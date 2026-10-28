import copy
import importlib.util
import os
import unittest

spec = importlib.util.spec_from_file_location('compose_check', os.path.join(os.path.dirname(__file__), 'check_compose.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ComposeTests(unittest.TestCase):
    def setUp(self):
        self.stage = '/tmp/stage'
        self.before = {'name': 'voicepipeline', 'services': {'voicepipeline': {
            'image': 'voicepipeline-whisper:local', 'environment': {'TOKEN': 'private'},
            'volumes': [{'type': 'bind', 'source': '/tmp/data', 'target': '/data'},
                        {'type': 'bind', 'source': '/tmp/old.py', 'target': '/app/pipeline/models/speaker_id.py', 'read_only': True}],
        }}}
        self.after = copy.deepcopy(self.before)
        self.after['services']['voicepipeline']['volumes'].extend([
            {'type': 'bind', 'source': '/tmp/stage/api.py', 'target': '/app/api/main.py', 'read_only': True},
            {'type': 'bind', 'source': '/tmp/stage/ui.js', 'target': '/app/ui/app.js', 'read_only': True},
        ])
        self.mounts = [{'Destination': '/data', 'Source': '/tmp/data', 'Type': 'bind', 'RW': True},
                       {'Destination': '/app/pipeline/models/speaker_id.py', 'Source': '/tmp/old.py', 'Type': 'bind', 'RW': False}]

    def check(self): return module.check(self.before, self.after, self.mounts, self.stage)

    def test_expected_override_passes_without_modifying_inputs(self):
        before, after = copy.deepcopy(self.before), copy.deepcopy(self.after)
        self.assertEqual(self.check(), 'voicepipeline-whisper:local')
        self.assertEqual((before, after), (self.before, self.after))

    def test_configuration_drift_is_rejected(self):
        self.after['services']['voicepipeline']['environment']['TOKEN'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'more than'): self.check()

    def test_old_mount_replacement_and_runtime_mismatch_are_rejected(self):
        self.after['services']['voicepipeline']['volumes'][0]['source'] = '/tmp/other'
        with self.assertRaisesRegex(ValueError, 'modified'): self.check()
        self.setUp()
        self.mounts[0]['Source'] = '/tmp/other'
        with self.assertRaisesRegex(ValueError, 'source differs'): self.check()

    def test_duplicate_and_unexpected_mounts_are_rejected(self):
        self.after['services']['voicepipeline']['volumes'].append(copy.deepcopy(self.after['services']['voicepipeline']['volumes'][0]))
        with self.assertRaisesRegex(ValueError, 'Duplicate'): self.check()
        self.setUp()
        self.mounts.append({'Destination': '/other', 'Source': '/tmp', 'Type': 'bind', 'RW': True})
        with self.assertRaisesRegex(ValueError, 'Running mounts differ'): self.check()

    def test_unsafe_new_mount_is_rejected(self):
        self.after['services']['voicepipeline']['volumes'][-1]['read_only'] = False
        with self.assertRaisesRegex(ValueError, 'incorrect'): self.check()

    def test_existing_mount_permissions_must_match_running(self):
        self.mounts[0]['RW'] = False
        with self.assertRaisesRegex(ValueError, 'access mode'): self.check()


if __name__ == '__main__': unittest.main()
