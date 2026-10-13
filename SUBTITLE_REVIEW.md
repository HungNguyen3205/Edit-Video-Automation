# Subtitle review and layout improvements

The one-button workflow and existing `/edit_plan` revision API are retained.
After a first transcription/render, open **Sửa phụ đề trước khi dựng lại**,
correct each sentence, then press the existing create button. Sentence times
stay unchanged. Changed sentences discard old word alignments, so caption
pages use sentence timing instead of assigning old words to corrected text.

Explicit edits and SRT imports are stored in `user_subtitles`; automatic
retries use that copy, while `recognition_subtitles` retains recognition
output for comparison. The AI/fallback adapter cannot rewrite the explicit
corrections. Existing automatic retries without manual corrections continue
to use the recognition cache. Stale revisions are rejected.

The persistent logo is 20% of frame width with a 9% height cap, preserves
transparency and aspect ratio, and occupies the top-right safe area. The
brand footer uses a larger font. Picture-in-picture scenes move the speaker
up and increase speaker height; explainer cards allow a larger graphic.
Rule diagrams use a neutral centre label rather than repeating a source
concept as both the centre and a node. Uploaded photos remain selected
by explicit asset IDs and topic matching.

No model training, paid service or new production dependency is added.
Uncertain recognition words still require user review. Existing zoom pulses
remain active; this change does not replace the camera motion engine.

Run: `CHROME_PATH=/path/to/chrome python -m pytest -q`.
On Windows activate the existing virtual environment and run `python main.py`.
