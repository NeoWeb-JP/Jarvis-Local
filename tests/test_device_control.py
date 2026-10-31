"""Regression checks for per-device lighting failures and safe retry."""
import asyncio
import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

root = Path(__file__).resolve().parents[1] / "custom_components" / "jarvis_local"
pkg = types.ModuleType("jarvis_device_test")
pkg.__path__ = [str(root)]
sys.modules[pkg.__name__] = pkg
ha = types.ModuleType("homeassistant")
ha.__path__ = []
errors = types.ModuleType("homeassistant.exceptions")
class HomeAssistantError(Exception):
    pass
errors.HomeAssistantError = HomeAssistantError
sys.modules["homeassistant"] = ha
sys.modules["homeassistant.exceptions"] = errors
control = importlib.import_module("jarvis_device_test.device_control")

class State:
    def __init__(self, value):
        self.state = value
        self.attributes = {}
        self.name = "Bedroom Lamp"

class States:
    def __init__(self):
        self.data = {"light.good": State("on"), "light.bad": State("on")}
    def get(self, entity):
        return self.data.get(entity)

class Services:
    def __init__(self, states):
        self.states = states
        self.calls = []
    async def async_call(self, domain, service, data, **kwargs):
        name = data["entity_id"][0]
        self.calls.append(name)
        if name == "light.bad":
            raise HomeAssistantError("The Tuya cloud rejected the command")
        self.states.data[name].state = "off" if service == "turn_off" else "on"

class Hass:
    def __init__(self):
        self.states = States()
        self.services = Services(self.states)

class TestDeviceControl(unittest.IsolatedAsyncioTestCase):
    async def test_rejected_light_does_not_abort_other_light(self):
        hass = Hass()
        with patch.object(control.asyncio, "sleep", return_value=None):
            ok, bad, unknown = await control.apply_lighting(
                hass, "light", "turn_off",
                {"entity_id": ["light.bad", "light.good"]}, None)
        self.assertEqual(ok, ["light.good"])
        self.assertEqual(bad, ["light.bad"])
        self.assertEqual(unknown, [])
        self.assertEqual(hass.services.calls, ["light.bad", "light.bad", "light.good"])
        self.assertIn("Bedroom Lamp", control.lighting_report(hass, bad, unknown))
        self.assertNotIn("light.bad", control.lighting_report(hass, bad, unknown))
    async def test_no_retry_when_state_changed_despite_error(self):
        hass = Hass()
        async def rejected_but_applied(domain, service, data, **kwargs):
            hass.services.calls.append(data["entity_id"][0])
            hass.states.data["light.bad"].state = "off"
            raise HomeAssistantError("Cloud response lost")
        hass.services.async_call = rejected_but_applied
        with patch.object(control.asyncio, "sleep", return_value=None):
            ok, bad, unknown = await control.apply_lighting(
                hass, "light", "turn_off", {"entity_id": ["light.bad"]}, None)
        self.assertEqual((ok, bad, unknown), (["light.bad"], [], []))
        self.assertEqual(len(hass.services.calls), 1)

if __name__ == "__main__":
    unittest.main()
