"""Exact music-response templates and reusable, voice-isolated PCM clips."""
from __future__ import annotations

import asyncio
import io
import re
import wave
from array import array
import sys

RATE = 24000
MAX_SECONDS = 30
ASSEMBLY_VERSION = "phrases-pcm-v1"


def phrase_parts(message: str) -> list[str] | None:
    """Preserve wording exactly; never rewrite arbitrary responses or errors."""
    slot = r"([\w][\w '&’+/-]{0,79})"
    patterns = [
        r"(Playing )" + slot + r"( music from Spotify in the )" + slot + r"(\.)",
        r"(I requested )" + slot + r"( in )" + slot + r"(\.)",
        r"(I’ve requested )" + slot + r"( music from Spotify in the )" + slot + r"(\.)",
    ]
    for pattern in patterns:
        match = re.fullmatch(pattern, message)
        if match:
            # Attach final punctuation to the room for sentence-final intonation.
            return [match[1].strip(), match[2], match[3].strip(), match[4]+match[5]]
    return None


def pcm_wave(pcm: bytes) -> bytes:
    if not pcm or len(pcm) % 2:
        raise ValueError("Invalid PCM audio")
    output = io.BytesIO()
    with wave.open(output, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(RATE)
        stream.writeframes(pcm)
    return output.getvalue()


def read_pcm(audio: bytes) -> bytes:
    with wave.open(io.BytesIO(audio), "rb") as stream:
        if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate(), stream.getcomptype()) != (1, 2, RATE, "NONE"):
            raise ValueError("Clip format does not match phrase library")
        if not 0 < stream.getnframes() <= RATE * MAX_SECONDS:
            raise ValueError("Clip is empty or too long")
        pcm = stream.readframes(stream.getnframes())
        if len(pcm) != stream.getnframes()*2:
            raise ValueError("Truncated audio clip")
        return pcm


async def normalise_audio(extension: str, audio: bytes, binary: str = "ffmpeg") -> bytes:
    """Decode each clip once, so MP3 headers/delays are never concatenated."""
    if extension == "wav":
        try:
            read_pcm(audio)
            return audio
        except (ValueError, wave.Error, EOFError):
            pass
    if extension not in {"wav", "mp3", "ogg", "flac"} or not audio or len(audio) > 8*1024*1024:
        raise ValueError("Invalid speech audio")
    process = await asyncio.create_subprocess_exec(
        binary, "-hide_banner", "-loglevel", "error", "-nostdin",
        "-protocol_whitelist", "pipe", "-i", "pipe:0", "-vn",
        "-t", str(MAX_SECONDS+1), "-ac", "1", "-ar", str(RATE),
        "-f", "s16le", "pipe:1",
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        pcm, _ = await asyncio.wait_for(process.communicate(audio), timeout=20)
    except BaseException:
        if process.returncode is None:
            process.kill()
        await process.wait()
        raise
    if process.returncode or not pcm or len(pcm) > RATE*MAX_SECONDS*2:
        raise ValueError("Speech clip could not be decoded or is too long")
    return pcm_wave(pcm)


def join_clips(clips: list[bytes]) -> bytes:
    """Build one WAV with a short word boundary, never separate play calls."""
    if not 1 <= len(clips) <= 8:
        raise ValueError("Invalid clip count")
    parts = []
    for audio in clips:
        samples=array('h',read_pcm(audio))
        if sys.byteorder != 'little':samples.byteswap()
        start=0;end=len(samples)
        while start < end and abs(samples[start]) <= 64:start+=1
        while end > start and abs(samples[end-1]) <= 64:end-=1
        if start == end:raise ValueError('Speech clip contains only silence')
        # Keep a small edge margin, removing only leading/trailing near-silence.
        trimmed=samples[max(0,start-RATE//100):min(len(samples),end+RATE//100)]
        if sys.byteorder != 'little':trimmed.byteswap()
        parts.append(trimmed.tobytes())
    silence = b"\0\0" * (RATE * 20 // 1000)
    pcm = silence.join(parts)
    if len(pcm) > RATE*MAX_SECONDS*2:
        raise ValueError("Combined response is too long")
    return pcm_wave(pcm)


class PhraseLibrary:
    def __init__(self, cache, normalise=normalise_audio):
        self.cache = cache
        self.normalise = normalise

    async def clip(self, text, identity, generate):
        text=text.strip().casefold()
        clip_identity = {**identity, "model": identity["model"]+":"+ASSEMBLY_VERSION+":clip"}
        async def create():
            extension, audio = await generate(text)
            return "wav", await self.normalise(extension, audio)
        return await self.cache.get_or_generate_audio(
            text=text, **clip_identity, generate=create, kind="clip",
        )

    async def compose(self, message, identity, generate):
        parts = phrase_parts(message)
        if parts is None:
            return None
        composed_identity = {**identity, "model": identity["model"]+":"+ASSEMBLY_VERSION+":sentence"}
        generated = 0
        async def create():
            nonlocal generated
            clips = []
            for part in parts:
                _, audio, hit = await self.clip(part, identity, generate)
                generated += not hit
                clips.append(audio)
            return "wav", join_clips(clips)
        extension, audio, hit = await self.cache.get_or_generate_audio(
            text=message, **composed_identity, generate=create, kind="assembled",
        )
        return extension, audio, hit, generated

