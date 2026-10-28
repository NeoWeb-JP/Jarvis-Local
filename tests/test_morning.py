import unittest
import test_commands
from jarvis_test.morning import morning_reply

class MorningTests(unittest.TestCase):
    def test_per_profile_pool_and_unknown(self):
        profiles = {'jaco': {'name': 'Jaco', 'morning_responses':['Jaco custom']}, 'ed': {'name':'Ed','morning_responses':['Ed custom']}}
        self.assertEqual(morning_reply('Jaco',profiles),'Jaco custom')
        self.assertEqual(morning_reply('Ed',profiles),'Ed custom')
        self.assertNotIn('Ed', morning_reply(None,profiles))
    def test_generic_fallback_and_format_safety(self):
        self.assertIn('Jaco',morning_reply('Jaco',{}))
        self.assertEqual(morning_reply('Jaco',{'jaco':{'name':'Jaco','morning_responses':['Hi {name} {other}']}}),'Hi Jaco {other}')
