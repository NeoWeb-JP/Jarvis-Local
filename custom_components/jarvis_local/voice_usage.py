"""Anonymous per-process voice-source counters (never log speech or audio)."""
from collections import Counter

class VoiceUsage:
    def __init__(self):
        self.counts = Counter()

    def record(self, source):
        if source not in {"elevenlabs_cached", "elevenlabs_generated",
                          "elevenlabs_category_cached", "xtts_cached", "xtts_generated"}:
            raise ValueError("Unknown voice source")
        self.counts[source] += 1

    def snapshot(self):
        counts = dict(self.counts)
        total = sum(counts.values())
        preferred = sum(v for k, v in counts.items() if k.startswith("elevenlabs_"))
        return {"counts": counts, "total": total,
                "preferred_voice_pct": round(100 * preferred / total, 1) if total else None}
