"""Unit tests for the Jarvis voice cache (no Home Assistant required)."""
import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "jarvis_local"))
from voice_cache import VoiceCache


def test_cache_hit_survives_new_instance(tmp_path):
    async def run():
        count = 0
        async def generate():
            nonlocal count
            count += 1
            return b"example-audio"
        params = dict(text="Lights on, my bru.", provider="elevenlabs",
                      voice_id="male-voice", model="flash", generate=generate)
        audio1, hit1 = await VoiceCache(tmp_path).get_or_generate(**params)
        audio2, hit2 = await VoiceCache(tmp_path).get_or_generate(**params)
        assert (audio1, hit1) == (b"example-audio", False)
        assert (audio2, hit2) == (b"example-audio", True)
        assert count == 1
    asyncio.run(run())


def test_concurrent_requests_generate_only_once(tmp_path):
    async def run():
        cache = VoiceCache(tmp_path)
        count = 0
        async def generate():
            nonlocal count
            count += 1
            await asyncio.sleep(.02)
            return b"voice"
        async def call():
            return await cache.get_or_generate(
                text="Good morning.", provider="elevenlabs",
                voice_id="v1", model="flash", generate=generate)
        answers = await asyncio.gather(*(call() for _ in range(6)))
        assert count == 1
        assert sum(hit for _, hit in answers) == 5
    asyncio.run(run())


def test_voice_and_settings_invalidate_key():
    common = dict(text="Hello.", provider="elevenlabs", voice_id="one", model="flash")
    first = VoiceCache.key(**common)
    assert first != VoiceCache.key(**{**common, "voice_id": "two"})
    assert first != VoiceCache.key(**{**common, "settings": {"stability": .5}})


def test_failed_generation_is_not_cached(tmp_path):
    async def run():
        cache = VoiceCache(tmp_path)
        async def fail():
            raise RuntimeError("provider unavailable")
        params = dict(text="Test.", provider="elevenlabs", voice_id="one",
                      model="flash", generate=fail)
        try:
            await cache.get_or_generate(**params)
        except RuntimeError:
            pass
        else:
            raise AssertionError("provider error was not propagated")
        assert not list(tmp_path.rglob("*.wav"))
    asyncio.run(run())


def test_dynamic_format_and_persistence(tmp_path):
    async def run():
        generated = 0
        async def generate():
            nonlocal generated
            generated += 1
            return "mp3", b"mp3-audio"
        params = dict(text="Hello.", provider="tts.elevenlabs_text_to_speech",
                      voice_id="v1", model="flash", generate=generate)
        first = await VoiceCache(tmp_path).get_or_generate_audio(**params)
        second = await VoiceCache(tmp_path).get_or_generate_audio(**params)
        assert first == ("mp3", b"mp3-audio", False)
        assert second == ("mp3", b"mp3-audio", True)
        assert generated == 1
    asyncio.run(run())


def test_dynamic_format_concurrency_and_provider_isolation(tmp_path):
    async def run():
        cache = VoiceCache(tmp_path)
        count = 0
        async def generate():
            nonlocal count
            count += 1
            await asyncio.sleep(0.02)
            return "wav", b"wave-audio"
        def args(provider):
            return dict(text="Lights on", provider=provider,
                        voice_id="v1", model="model", generate=generate)
        results = await asyncio.gather(*[
            cache.get_or_generate_audio(**args("elevenlabs")) for _ in range(5)
        ])
        assert count == 1
        assert sum(hit for _, _, hit in results) == 4
        other = await cache.get_or_generate_audio(**args("xtts"))
        assert other[2] is False
        assert count == 2
    asyncio.run(run())


def test_dynamic_format_does_not_cache_failure(tmp_path):
    async def run():
        async def generate():
            return "wav", b""
        try:
            await VoiceCache(tmp_path).get_or_generate_audio(
                text="Empty", provider="elevenlabs", voice_id="v1",
                model="m", generate=generate)
        except ValueError:
            pass
        else:
            raise AssertionError("Empty audio should be rejected")
        assert not list(tmp_path.rglob("*.wav"))
    asyncio.run(run())
