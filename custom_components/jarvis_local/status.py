"""Read-only answers from explicit household entities."""
import re
from .settings import get

def answer(hass, text):
    text = re.sub(r"[?.!,]", "", text.lower()).strip()
    text = re.sub(r"^(?:hey )?jarvis\s+", "", text)
    text = re.sub(r"\s+jarvis$", "", text)
    text = re.sub(r"\s+", " ", text)
    def state(entity):
        value = hass.states.get(entity)
        return value if value and value.state not in {"unknown", "unavailable"} else None
    if text in {"help", "what can you do", "what commands do you support"}:
        return ("After a lighting command, you can say set them to 30 percent, a bit brighter, or turn them off for two minutes in the same conversation. I can control individual lights by name or alias, set kitchen lights to 30 percent, dim or brighten room lights, answer are the kitchen lights on, and list what lights are in the kitchen. I can discover lights and rooms: say discover lights, list rooms, or list zones. Say turn off the kitchen to control its lights, or replace kitchen with a configured area name. I can run good morning, good night, and start, end or toggle movie time. "
                "You can also ask: are the lights on, what's the heating set to, "
                "is the heating on, is the car plugged in, or what's the car battery level. "
                "You can combine up to four requests, including one household routine. Say preview followed by a command to check it without running anything.")
    if text in {"are the lights on", "which lights are on", "what lights are on"}:
        from homeassistant.components.homeassistant.exposed_entities import async_should_expose
        lights=[s for s in hass.states.async_all('light') if async_should_expose(hass, 'conversation', s.entity_id)]
        on=[s.name for s in lights if s.state == 'on']
        if not lights:return 'I could not find any lights exposed to Assist.'
        return 'These lights are on: ' + ', '.join(on) + '.' if on else 'No exposed lights report that they are on.'
    if text in {"what's the heating set to", "what is the heating set to", "is the heating on", "what is the temperature", "what's the temperature"}:
        s=state(get(hass, "thermostat")) if get(hass, "thermostat") else None
        if s is None:return "The thermostat is unavailable."
        unit=s.attributes.get("temperature_unit", "degrees")
        return (f"The heating mode is {s.state}. Its current action is {s.attributes.get('hvac_action', 'not reported')}. "
                f"The target is {s.attributes.get('temperature', 'not reported')} {unit}; "
                f"the measured temperature is {s.attributes.get('current_temperature', 'not reported')} {unit}.")
    if text in {"is the car plugged in", "is the car connected"}:
        s=state(get(hass, "car_cable_sensor")) if get(hass, "car_cable_sensor") else None
        if s is None or s.state not in {"on","off"}:return "I can't currently check the charging cable."
        return "The car is plugged in." if s.state=="on" else "The car is not plugged in."
    if text in {"what's the car battery level", "what is the car battery level", "how much battery does the car have"}:
        s=state(get(hass, "car_battery_sensor")) if get(hass, "car_battery_sensor") else None
        try:
            value=float(s.state)
            if not 0<=value<=100:raise ValueError
        except (AttributeError,ValueError,TypeError):return "The car battery reading is unavailable."
        return f"The car battery is at {value:g} percent."
    return None
