"""Anonymous per-process voice-source counters (never log speech or audio)."""
from collections import Counter

class VoiceUsage:
    def __init__(self):
        self.counts = Counter()
        self.last_source = None
        self.generated_clips = 0

    def record_clips(self, count):
        self.generated_clips += count

    def record(self, source):
        if source not in {"elevenlabs_cached", "elevenlabs_generated",
                          "elevenlabs_category_cached", "xtts_cached", "xtts_generated",
                          "elevenlabs_phrase_cached", "elevenlabs_phrase_generated"}:
            raise ValueError("Unknown voice source")
        self.counts[source] += 1
        self.last_source = source

    def snapshot(self):
        counts = dict(self.counts)
        total = sum(counts.values())
        preferred = sum(v for k, v in counts.items() if k.startswith("elevenlabs_"))
        return {"counts": counts, "total": total, 'last_source':self.last_source,
                'generated_clips':self.generated_clips,
                "preferred_voice_pct": round(100 * preferred / total, 1) if total else None}


