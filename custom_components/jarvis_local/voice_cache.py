"""Provider-independent, persistent cache for synthesized Jarvis speech.

No Home Assistant or ElevenLabs dependency. The TTS platform will call
get_or_generate with bytes returned by its configured speech provider.
Do not include secrets or personal speaker profiles in the cache metadata.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from typing import Awaitable, Callable


class VoiceCache:
    """Cache by exact spoken text and voice generation parameters."""

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self.hits = 0
        self.misses = 0

    @staticmethod
    def key(*, text: str, provider: str, voice_id: str, model: str,
            language: str = "en", settings: dict | None = None,
            extension: str = "wav") -> str:
        """Content-addressed key; exclude credentials and volatile metadata."""
        if extension not in {"wav", "mp3", "ogg", "flac"}:
            raise ValueError("Unsupported audio format")
        payload = {
            "text": text, "provider": provider, "voice_id": voice_id,
            "model": model, "language": language, "settings": settings or {},
            "extension": extension, "cache_version": 1,
        }
        serialised = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                ensure_ascii=False, allow_nan=False)
        return sha256(serialised.encode("utf-8")).hexdigest()

    def path_for(self, key: str, extension: str = "wav") -> Path:
        if len(key) != 64 or any(c not in "0123456789abcdef" for c in key):
            raise ValueError("Invalid cache key")
        if extension not in {"wav", "mp3", "ogg", "flac"}:
            raise ValueError("Unsupported audio format")
        return self.directory / key[:2] / f"{key}.{extension}"

    async def get_or_generate(
        self,
        *,
        text: str,
        provider: str,
        voice_id: str,
        model: str,
        generate: Callable[[], Awaitable[bytes]],
        language: str = "en",
        settings: dict | None = None,
        extension: str = "wav",
    ) -> tuple[bytes, bool]:
        """Return (audio, cache_hit); coalesce concurrent identical requests.

        Provider failure is propagated to the caller, which may use XTTS.
        A fallback voice must use its OWN provider/voice key.
        """
        key = self.key(text=text, provider=provider, voice_id=voice_id,
                       model=model, language=language, settings=settings,
                       extension=extension)
        path = self.path_for(key, extension)
        async with self._locks[key]:
            try:
                audio = await asyncio.to_thread(path.read_bytes)
                if audio:
                    self.hits += 1
                    return audio, True
            except FileNotFoundError:
                pass

            # Never cache failed or empty generations.
            audio = await generate()
            if not isinstance(audio, bytes) or not audio:
                raise ValueError("TTS provider returned empty or invalid audio")

            def write_atomic() -> None:
                path.parent.mkdir(parents=True, exist_ok=True)
                fd, tmp = tempfile.mkstemp(prefix=".jarvis-", dir=path.parent)
                try:
                    with os.fdopen(fd, "wb") as stream:
                        stream.write(audio)
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.replace(tmp, path)
                finally:
                    if os.path.exists(tmp):
                        os.unlink(tmp)

            await asyncio.to_thread(write_atomic)
            self.misses += 1
            return audio, False

    async def get_or_generate_audio(
        self, *, text: str, provider: str, voice_id: str, model: str,
        generate: Callable[[], Awaitable[tuple[str, bytes]]],
        language: str = "en", settings: dict | None = None,
    ) -> tuple[str, bytes, bool]:
        """Cache audio when the provider chooses its output format.

        An identity-wide lock prevents simultaneous misses from generating
        multiple paid requests. Never return a different provider's audio.
        """
        identity = self.key(
            text=text, provider=provider, voice_id=voice_id, model=model,
            language=language, settings=settings, extension="wav"
        )
        async with self._locks[identity]:
            for ext in ("mp3", "wav", "ogg", "flac"):
                key = self.key(
                    text=text, provider=provider, voice_id=voice_id,
                    model=model, language=language, settings=settings,
                    extension=ext
                )
                path = self.path_for(key, ext)
                try:
                    audio = await asyncio.to_thread(path.read_bytes)
                    if audio:
                        self.hits += 1
                        return ext, audio, True
                except FileNotFoundError:
                    pass

            ext, audio = await generate()
            if ext not in {"mp3", "wav", "ogg", "flac"}:
                raise ValueError("Unsupported TTS audio format")
            if not isinstance(audio, bytes) or not audio:
                raise ValueError("TTS provider returned empty or invalid audio")
            key = self.key(
                text=text, provider=provider, voice_id=voice_id, model=model,
                language=language, settings=settings, extension=ext
            )
            path = self.path_for(key, ext)

            def store():
                path.parent.mkdir(parents=True, exist_ok=True)
                fd, tmp = tempfile.mkstemp(prefix=".jarvis-", dir=path.parent)
                try:
                    with os.fdopen(fd, "wb") as stream:
                        stream.write(audio)
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.replace(tmp, path)
                finally:
                    if os.path.exists(tmp):
                        os.unlink(tmp)

            await asyncio.to_thread(store)
            self.misses += 1
            return ext, audio, False
