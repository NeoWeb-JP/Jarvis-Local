import copy
import importlib.util
import os
import unittest

spec = importlib.util.spec_from_file_location('runtime_check', os.path.join(os.path.dirname(__file__), 'check_runtime.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.compose = {'services': {'voicepipeline': {
            'environment': {'TOKEN': 'PRIVATE_VALUE', 'MODE': 'on'},
            'ports': [{'target': 10300, 'published': '10300', 'protocol': 'tcp'},
                      {'target': 8000, 'published': '8000', 'protocol': 'tcp'}],
            'networks': {'default': None},
        }}, 'networks': {'default': {'name': 'voicepipeline_default'}}}
        self.container = {'Image': 'sha256:abc', 'Config': {'Env': ['PATH=/bin', 'TOKEN=PRIVATE_VALUE', 'MODE=on']},
            'HostConfig': {'PortBindings': {'10300/tcp': [{'HostIp': '', 'HostPort': '10300'}],
                                            '8000/tcp': [{'HostIp': '', 'HostPort': '8000'}]}},
            'NetworkSettings': {'Networks': {'voicepipeline_default': {}}}}
        self.image = {'Id': 'sha256:abc', 'Config': {'Env': ['PATH=/bin', 'MODE=old']}}

    def check(self): return module.check(self.compose, self.container, self.image)

    def test_expected_environment_ports_and_networks_pass(self):
        before = copy.deepcopy((self.compose, self.container, self.image))
        self.assertTrue(self.check())
        self.assertEqual(before, (self.compose, self.container, self.image))

    def test_environment_mismatch_does_not_expose_values(self):
        self.container['Config']['Env'][-1] = 'MODE=SECRET_DIFFERENT'
        with self.assertRaises(ValueError) as error: self.check()
        self.assertNotIn('SECRET', str(error.exception))
        self.assertNotIn('PRIVATE_VALUE', str(error.exception))

    def test_unknown_or_duplicate_environment_is_rejected(self):
        self.compose['services']['voicepipeline']['environment']['UNSET'] = None
        with self.assertRaisesRegex(ValueError, 'unresolved'): self.check()
        self.setUp()
        self.container['Config']['Env'].append('MODE=on')
        with self.assertRaisesRegex(ValueError, 'duplicate'): self.check()

    def test_port_and_network_mismatch_are_rejected(self):
        self.container['HostConfig']['PortBindings']['8000/tcp'][0]['HostPort'] = '8001'
        with self.assertRaisesRegex(ValueError, 'port'): self.check()
        self.setUp()
        self.container['NetworkSettings']['Networks']['unexpected'] = {}
        with self.assertRaisesRegex(ValueError, 'networks'): self.check()

    def test_network_mode_and_dynamic_port_are_checked(self):
        self.compose['services']['voicepipeline']['network_mode'] = 'host'
        self.container['HostConfig']['NetworkMode'] = 'bridge'
        with self.assertRaisesRegex(ValueError, 'network mode'): self.check()
        self.setUp()
        self.compose['services']['voicepipeline']['ports'][0]['published'] = '0'
        with self.assertRaisesRegex(ValueError, 'dynamic'): self.check()

    def test_image_drift_is_rejected(self):
        self.image['Id'] = 'sha256:different'
        with self.assertRaisesRegex(ValueError, 'image'): self.check()

    def test_command_restart_and_privilege_drift_are_rejected(self):
        self.image['Config']['Cmd'] = ['python', 'server.py']
        self.container['Config']['Cmd'] = ['python', 'other.py']
        with self.assertRaisesRegex(ValueError, 'command'): self.check()
        self.setUp()
        self.compose['services']['voicepipeline']['restart'] = 'unless-stopped'
        with self.assertRaisesRegex(ValueError, 'restart'): self.check()
        self.setUp()
        self.container['HostConfig']['Privileged'] = True
        with self.assertRaisesRegex(ValueError, 'privilege'): self.check()

    def test_custom_resources_require_review(self):
        self.container['HostConfig']['Memory'] = 1024
        with self.assertRaisesRegex(ValueError, 'resource limits'): self.check()


if __name__ == '__main__': unittest.main()
