import copy
import importlib.util
import os
import unittest

spec = importlib.util.spec_from_file_location('post_check', os.path.join(os.path.dirname(__file__), 'check_post_deploy.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PostDeployTests(unittest.TestCase):
    def setUp(self):
        self.before = [
            {'Destination': '/data', 'Source': '/tmp/data', 'Type': 'bind', 'RW': True},
            {'Destination': '/app/pipeline/models/speaker_id.py', 'Source': '/tmp/sid', 'Type': 'bind', 'RW': False},
        ]
        self.after = copy.deepcopy(self.before) + [
            {'Destination': '/app/api/main.py', 'Source': '/tmp/stage/api.py', 'Type': 'bind', 'RW': False},
            {'Destination': '/app/ui/app.js', 'Source': '/tmp/stage/ui.js', 'Type': 'bind', 'RW': False},
        ]

    def test_valid_mounts(self): self.assertTrue(module.check(self.before, self.after, '/tmp/stage'))
    def test_wrong_data_or_access_is_rejected(self):
        self.after[0]['Source'] = '/tmp/other'
        with self.assertRaisesRegex(ValueError, 'existing mount'): module.check(self.before, self.after, '/tmp/stage')
        self.setUp(); self.after[-1]['RW'] = True
        with self.assertRaisesRegex(ValueError, 'new application'): module.check(self.before, self.after, '/tmp/stage')
    def test_duplicate_or_missing_is_rejected(self):
        self.after.append(copy.deepcopy(self.after[0]))
        with self.assertRaisesRegex(ValueError, 'duplicate'): module.check(self.before, self.after, '/tmp/stage')
        self.setUp(); self.after.pop()
        with self.assertRaisesRegex(ValueError, 'targets'): module.check(self.before, self.after, '/tmp/stage')


if __name__ == '__main__': unittest.main()
