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

## Project-specific spellings and title wrapping

The optional **Tên riêng và cách viết đúng** field uses one entry per line:
`Canonical name | recognised alias | another alias`. It is limited to 600
characters and stored with each job/project. Explicit aliases work with
Vietnamese and Latin names; they do not become global defaults. Brand-token
near-spellings are corrected only when the user supplies that brand; generic
words outside the full brand phrase remain unchanged. Manual subtitle edits
have precedence. Retrying with a different spelling uses the original
recognition cache, rather than accumulating previous automatic corrections.

`text_review.py` owns spelling rules, source-copy preparation, review flags
and title measurements. It preserves source recognition and aligns changed
names within their existing word spans. Both AI and fallback receive that
prepared copy; scene labels are normalized before rendering. Multiword names
up to four words stay on the same caption page.

Camera titles are measured with the local Barlow font and balanced over at
most two lines. Illustrated scenes use the same layout routine and safe font
size instead of allowing CSS to leave a lone trailing word on its own line.

The subtitle editor adds **Nghe câu gốc**, seeking the uploaded source to
that sentence's source timestamp. Low-confidence recognised words (where
metadata exists) and potentially odd wording are review suggestions, not
automatic meaning changes. A result requiring review is labelled accordingly.
The confirmed 'check' correction was applied only to the user's review video,
not hardcoded into production spelling rules.

Verification: 95-test full suite passed, then 20 targeted spelling/caption/
style/contract tests passed after adding multiword-name pagination. Actual
browser checks covered spelling restoration, source playback, corrected
subtitle rerendering and 390px mobile layout. Actual 37.3-second source was
rendered using the existing recognition cache and genuine Ollama-unavailable
fallback, then fully decoded during the production verification stage.

## Durable editing and confirmed correction import

The subtitle editor has an explicit **Lưu phụ đề** action. Editing text creates
an immediate browser draft keyed by project ID and revision. Refresh restores
only a matching draft; a stale draft is left unapplied and visibly reported.
Submitting a new render saves text through the revision-checked edit API and
clears the browser draft only once the new job has been accepted. Saving text
hides the old MP4 download button until rerendering, while retaining previous
successful output files on disk.

**Nhập chỉnh sửa đã xác nhận** accepts a small JSON file containing version=1,
source_duration, brand_name, proper_names and corrections[{find,replace}].
It requires the current project's duration and exactly one literal match per
correction. All validation occurs on a copy before changing the form/project.
Files with no match, duplicate matches, excessive size or invalid structure
are rejected. Import explicitly saves the corrected sentences; the existing
create button then renders them. The user's specific correction file is a
separate deliverable, not a global production substitution rule.

The edit API discards obsolete word timings if they no longer spell the
edited sentence. This prevents clipped source intervals from reconstructing
old recognition words and silently reversing a manual text correction.
A regression test covers a changed word followed by a source trim.

Verification: 96-test full suite passed; 10 subtitle/spelling tests passed
including the added old-word regression. Actual browser checks cover refresh,
explicit save, stale draft rejection, valid/invalid imports, actual rerender,
full MP4 decoding and mobile layout. This feature does not train model weights.
