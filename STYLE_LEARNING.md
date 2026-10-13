# Style learning: first working stage

The app now starts with a visual reference derived from the user's approved
video, stored in `style_reference.json`. It contains layout descriptors only,
not transcript, brand names or exact timestamps. The heading layout also
keeps explicit multiword names together.

After a successful render, open **Giúp AI dựng hợp ý bạn hơn**. Enter concrete
feedback, then use **Duyệt phong cách** or **Cần cải thiện**. Subtitle verification
is separate: an unchecked caption box still allows style approval, and an
unresolved subtitle-review warning blocks claiming captions are checked.
Only the current successful output/revision may receive feedback. Updating
feedback for the same result replaces its record rather than counting twice.

`learning_store.py` stores abstract layout summaries and user-entered notes
under the configured data directory's `learning/` folder. It does not copy
source transcripts, titles, brand names, asset paths or scene timestamps.
The next automatic job snapshots the baseline rules, at most three approved
examples and two recent requested changes. These go into Ollama's user context;
the current source, request and schema retain priority. Notes are bounded.
If guidance would exceed the input limit, it is omitted before sacrificing
source content. Reviews from failed/stale outputs are not accepted.

The result records whether guidance was actually sent to a successful AI
planner. Genuine model-unavailable fallback remains usable and reports
`applied_to_ai=false`. Saved feedback is not claimed to have changed fallback
render decisions. No paid service, new model, fine-tuning dependency or GPU
requirement is introduced.

**Xuất dữ liệu phong cách đã duyệt** downloads JSONL style feedback. This is
an initial supervision record, not a complete transcript-edit training corpus.
Model weights have NOT been trained. Quality improvement from real Ollama
inference needs comparison on fresh videos on the machine running the model.

Relevant verification covers positive/negative reviews, duplicate updates,
revision guards, caption-review guards, privacy of automatic summaries,
bounded example selection, current-source precedence, oversized context,
name-safe headings, and browser approval/refresh/export/rerender flows.
