# Experimental VoicePipeline history correction

This candidate derives from `paulglavin/VoicePipeline` and includes its MIT licence. It is based on `/app/api/main.py` SHA-256 `83b8285bc91b451fcf1e1b80db141cf9d3f1620026186d7f511f128066e8c386` and `/app/ui/app.js` SHA-256 `e4156a695b1c6a20e8a1700a565b3070918174fd805d1fd9aeb87cb1066d7be1`. It is an isolated test candidate, not a release or an instruction to overwrite another version.

History provides a correction control for resolved or dismissed recordings. Changing the speaker appends a new resolution, removes the recording from other speakers' reference lists and leaves the selected speaker's reference list unchanged. Undo appends a dismissal event and returns the recording to Pending. Neither option deletes audio or automatically adds a reference. Previous resolutions remain in the audit trail; stale History tabs are rejected. The control asks for confirmation.

The original pipeline match and its confidence remain unchanged; the History summary shows a confidence only when it corresponds to the displayed speaker. Filters use the corrected assignment. These changes do not restore references previously rotated out by earlier incorrect assignments or recalculate historical interaction counts and averages. Audio paths must be available in the database to identify references safely. Cache invalidation is requested after saving; the service's existing scheduled refresh may take several minutes. A failure to request refresh is reported separately from a successful database correction.

`test_correction.py` uses temporary SQLite databases built from the upstream schema and extracts the candidate's real backend functions using Python AST; it does not start FastAPI. `test_ui.js` runs the History controls with a simulated DOM. An isolated live API, browser and voice test remains necessary.

`test_installer.py` exercises successful installation and a copy-failure rollback using fake Docker and temporary files; it never controls a real container. The original upstream files used by that test are included under `test_fixtures`.
