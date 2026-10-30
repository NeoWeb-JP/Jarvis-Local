"""Same-category preference must never invent facts or cross guest privacy."""
import importlib.util
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "custom_components" / "jarvis_local" / "voice_catalog_fallback.py"
spec = importlib.util.spec_from_file_location("voice_catalog_fallback", MODULE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

CATALOG = {
    "Sassy": {"on": ["Lights on, my bru.", "Bright as your future."],
              "off": ["Lights off."], "general": ["Sorted."]},
    "Savage": {"on": ["Lights on. Miraculous."], "off": ["Off they go."]},
    "Guest": {"on": ["Lights on, welcome.", "Consider it done."],
              "off": ["Lights off, thanks."]},
}


def test_home_matches_only_same_action():
    values = module.category_alternatives("Lights on, my bru.", CATALOG, guest=False)
    assert set(values) == {"Bright as your future.", "Lights on. Miraculous."}
    assert "Lights off." not in values


def test_guest_never_sees_home_replies():
    values = module.category_alternatives("Lights on, welcome.", CATALOG, guest=True)
    assert values == ("Consider it done.",)
    assert module.category_alternatives("Lights on, my bru.", CATALOG, guest=True) == ()


def test_dynamic_or_unapproved_text_not_substituted():
    assert module.category_alternatives("It's 21 degrees indoors.", CATALOG, guest=False) == ()
    assert module.category_alternatives("Smoke detected!", CATALOG, guest=False) == ()


def test_different_action_is_not_equivalent():
    assert module.category_alternatives("Lights off.", CATALOG, guest=False) == ("Off they go.",)
