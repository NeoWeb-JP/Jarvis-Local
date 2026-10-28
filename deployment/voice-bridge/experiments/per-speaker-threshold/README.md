# Experimental per-speaker thresholds

This is an experimental VoicePipeline source overlay, not a HACS release. It is based on the verified `speaker_id.py` with SHA-256 `09a933fc2fb72a2b97e3681f46121c26065c5becd80f04e7769636e26ba27bfb`. Do not apply it to production without validation against the exact running version and an isolated end-to-end test.

The optional `speaker_match_thresholds` SQLite setting is a JSON object mapping enrolled display names to thresholds. Keys are case-insensitive; missing names retain the global `match_threshold`. The threshold is checked only for the highest-scoring speaker. A rejected best match is unknown; the code does not switch to a second candidate. Invalid configuration or a read error rejects the match rather than accepting it under a lower threshold. Matching is approximate and cannot authorize actions.

The tests use synthetic embeddings and a temporary database. They do not measure real-world recognition or interaction with the running service.
