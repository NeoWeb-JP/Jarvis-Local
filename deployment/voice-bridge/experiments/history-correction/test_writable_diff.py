import importlib.util
import os
import unittest

spec = importlib.util.spec_from_file_location('diff_check', os.path.join(os.path.dirname(__file__), 'check_writable_diff.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class WritableDiffTests(unittest.TestCase):
    def test_reviewed_cache_paths_are_allowed(self):
        entries = ['C /usr', 'C /usr/local/lib/python3.12',
                   'C /usr/local/lib/python3.12/asyncio/__pycache__',
                   'A /usr/local/lib/python3.12/asyncio/__pycache__/tasks.cpython-312.pyc',
                   'C /app/pipeline', 'A /app/pipeline/__pycache__',
                   'A /app/pipeline/__pycache__/writer.cpython-312.pyc',
                   'C /root', 'A /root/.cache', 'A /root/.cache/huggingface',
                   'A /root/.cache/huggingface/.agent_harnesses.json']
        self.assertTrue(module.check(entries))

    def test_persistent_or_unreviewed_changes_are_rejected(self):
        for entry in ('C /app/api/main.py', 'A /root/.cache/huggingface/token',
                      'A /app/pipeline/config.json', 'D /app/api/main.py',
                      'C /app/pipeline/__pycache__/writer.cpython-312.pyc',
                      'A /app/other/__pycache__/x.cpython-312.pyc', 'malformed'):
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                module.check([entry])


if __name__ == '__main__': unittest.main()
