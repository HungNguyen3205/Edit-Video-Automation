# Audit: auto-edit pipeline and usability

## Current update — prompt-driven local director

The previous fixed-interval planner and discarded audio tracks were the remaining causes of rigid edits. `ai_director.py` now calls local Ollama with a constrained decision schema using the creative brief, timestamped transcript, scene/silence cues and optional sampled vision frames. Validated cut decisions compile to source clips; source captions and manual timed objects are remapped. Uploaded music is mixed with source audio and ducked; original procedural accents are synthesized locally. The UI distinguishes AI and rules modes and reports unavailable models/errors honestly.

21 tests passed with real FFmpeg renders and controlled HTTP/model responses. Real Ollama inference and vision-model quality are not verified in this environment. The historical observations below refer to the earlier implementation, not the current AI director.


## Root causes in commit 167df5a

| Finding | User-visible consequence | Change |
| --- | --- | --- |
| Auto Edit only appends the first image at 0–5 seconds | Uploading only a video cannot start automation | Backend `/auto-edit` pipeline; image optional |
| `text_overlays` and `effect_keyframes` never reach FFmpeg | No zoom or emphasis typography | Compile easing zoom and fading real source/user text |
| Recognition separate and optional, errors hidden | No captions, unclear prerequisites | Optional CPU Whisper stage, actionable error, SRT import/edit |
| Renderer uses `clips[0]` | Extra clips disappear | Normalize and concatenate all video/audio segments |
| Maps `0:a` unconditionally | Silent source fails | Generate silence for clips without audio |
| Raw overlay size, unshifted video PTS | Huge images, wrong start, frozen frames | Scale/fit and shift timestamps, pass-through at EOF |
| Captions retain source time after trim | Caption desynchronization | Source-to-timeline remapping per clip |
| Fake image preview is permanently visible | Preview and export disagree | Actual rendered preview/result player |
| Export reloads mutable project; filenames reused | Changing plan during a job changes output or stale video is offered | Frozen snapshot, unique output, revision-bound result |
| Polling reloads video repeatedly; English technical UI | Lost playback and confusing steps | Vietnamese 3-step flow, bounded polling, advanced edits separate |
| Unvalidated asset paths/edit plan | Wrong input, invalid time/unsafe paths | Project-owned asset IDs and validation |
| “Sprints 1–7 complete” lacks render evidence | Inaccurate delivery status | Replace status with verified checks and limits |

## Interface choices

Light, responsive workspace with project cards, source/result switch, optional illustrations, preset rhythm, optional headline, model notice, worker status, preview/export actions and expandable edits. Lucide 0.468.0 is bundled locally with its license. Custom components use native buttons, inputs, details, focus states and live status messages. Existing FastAPI/vanilla JS stack is retained; adding many overlapping UI frameworks would increase dependencies without improving this flow.

## Historical remaining gap before the AI director

The planner is intentionally deterministic. It extracts caption words and places user-tagged illustrations; it does not understand visual meaning or narrative emphasis. A higher-quality local semantic planner, face-safe crop, beat-aware pacing, audio cleanup and evaluated style templates are future work. The branch addresses the broken pipeline and usability, without claiming those advanced capabilities are already done.

## Verification evidence

12 FFmpeg/API tests passed. A separate real local Whisper tiny run on the user's reference produced 35 caption segments and a successful 12-second rendered preview (8 titles, 7 zoom windows in the full plan). Tiny recognition is not guaranteed accurate; the UI offers corrections and imported SRT. Browser automation completed the upload-to-download flow without JS errors at desktop/mobile sizes. H.264 playback was verified with FFmpeg; the headless test browser does not include that codec, so browser playback is an explicitly unverified check in this environment.
