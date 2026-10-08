# Project status

## Implemented on feature/auto-edit-studio

- Backend auto-edit → MP4 pipeline with no required image.
- Immutable job snapshot, single heavy worker, real render progress, cancellation and restart recovery.
- Local optional Whisper, reused model, SRT import/export and editable source-time captions.
- Timed easing zoom, fading headline/source text, properly sized/timed image and video overlays.
- Multi-clip video/audio concat including silent sources; preserved source aspect.
- Revision validation, safe asset lookup, unique outputs and stale-result protection.
- Vietnamese responsive studio with local Lucide icons, guided steps and expandable editing.

## Verification

- Real FFmpeg regression suite: see final verification summary below.
- Frontend JavaScript syntax checked with Node.
- Model-dependent recognition is not covered by the deterministic test suite.

## Limits

Rule-based automation, not expert-level semantic editing. No face tracking, stock search, music mixing or automatic filler removal. Recognition cancellation is cooperative between stages. One local server process only. Original footage is played separately from actual rendered preview; it does not simulate effects live. Read README.md and AUDIT.md before deployment.

## Verified in this session

- 12 FFmpeg/API regression tests passed on Linux CPU.
- Video reference (360×640, 62.855 seconds): local Whisper tiny generated 35 source caption segments; auto plan generated 8 titles and 7 zoom windows; rendered a 12-second preview with no pipeline error. Recognition plus preview took about 16.75 seconds on this environment, not a guarantee for other machines.
- Browser automation: create project → upload the reference → auto-edit without recognition → generate full MP4 → download link; no page JavaScript exceptions. No horizontal overflow at 1440px or 390px widths.
- MP4 media decoding verified through FFmpeg. The test Chromium headless binary lacks H.264 support, so in-browser MP4 playback could not be verified there; standard H.264/AAC MP4 is intended for current Chrome/Edge/Safari. The UI reports unsupported playback and provides the downloadable output.

## Follow-up: stale frontend asset fix

The reported screenshot shows new HTML styled with the original dark CSS. Added versioned absolute CSS/JS/icon URLs and frontend revalidation headers. 13 tests now pass, including the frontend asset regression. Browser verification requested the versioned CSS and confirmed the light root background and fixed sidebar even with the legacy unversioned CSS intercepted.
