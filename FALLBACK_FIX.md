# One-click AI timeout recovery

Base: published commit 0fc525124e5a326b5552adf89169c78afc2373ad. Published changes preserve the existing project structure.

## Behavior

The one-click automatic path tries local AI with a shared 180-second planning budget (`VIDEO_AUTO_AI_TIMEOUT`). The existing `VIDEO_AI_PLANNING_TIMEOUT` still provides an upper cap. Repairs and validation share that budget. Advanced AI editing retains its existing strict failure behavior.

Recoverable AI errors and exhausted plan repairs switch to a labelled source-based fallback. Cancellation, recognition errors, invalid media, configuration errors, missing render dependencies and renderer/storage failures do not become fake successes. The fallback keeps source speech/timestamps, uses short exact source excerpts for headings and gentle camera zoom, and keeps validated AI scene choices when available. It does not fabricate new graphics. No paid AI service was added.

AI requests use compact scene keys, expanded internally into the existing storyboard schema. Hidden camera graphic labels, badges and rewritten captions are no longer requested. Camera and graphic wire schemas are separate: graphic scenes require a nonempty title and at least two source-constrained labels, while camera scenes do not generate these fields. Source label candidates exclude common filler fragments. The layout engine retains the opening/closing camera and limits repeated graphics, choosing an interior chat and explanatory scene by speech relevance when available; it supplies subtle graphic SFX unless disabled. Timing, layout, motion renderer and saved project schema remain owned by the existing engine. Neutral introduction labels are allowed by the existing vocabulary guard; unsupported claims remain rejected. The frontend reports fallback in progress and in the completed badge/warnings. Its script URL is versioned to avoid an old cached script.

Raw recognition is retained for re-renders. A changed brief always runs planning again; successful recognition for the same immutable project source is reused. Selecting a new source in the simple UI creates a new project, so recognition is not carried between source videos.

Job metadata adds recognition/planning/render/verification seconds. Storyboard rendering additionally measures graphics, scene rendering and assembly; graphics time is INCLUDED in scene rendering, and those stages are INCLUDED in render_seconds. These are overlapping measurements, not numbers to add together. For a single continuous source with camera-only scenes, the compiler reuses the source picture instead of encoding individual scenes and their concatenation; the existing zoom/caption/audio passes still apply. Graphics, multi-clip edits, crop-reference and previews retain their previous renderer path. Every final MP4 is decoded with FFmpeg before success is published, with cancellation supported during verification.

## Run on Windows

Close the old backend first. Apply the patch only after checking existing local changes; never reset or overwrite them. In the repository root:

```powershell
git status --short
git apply --check path\to\ai-fallback-fix.patch
git apply path\to\ai-fallback-fix.patch
python main.py
```

Refresh the browser with Ctrl+F5. Ollama still needs to run for full AI illustrations; if unavailable, one-click rendering can use fallback. Whisper/FFmpeg/Node/Chrome remain required as before. No runtime dependency change is needed for this fix. If dependencies were not installed previously, use the repository's existing setup instructions.

Optional PowerShell configuration, set before starting the backend:

```powershell
$env:VIDEO_AI_MODEL = 'qwen3:4b'
$env:VIDEO_AI_THINK = '0'
$env:VIDEO_AUTO_AI_TIMEOUT = '180'
python main.py
```

The 180 seconds cover AI planning, not upload/recognition/render. Faster fallback does not guarantee demo-level graphics. Full AI and caption accuracy must still be reviewed before publishing.

## Validation

See the measured verification appended below. All measurements are from the test environment, not the user's Windows PC. A screenshot or empty `ollama ps` result cannot prove the Windows slowdown's exact cause.

### Measured final verification

- 78 tests passed; JavaScript syntax and git diff whitespace checks passed.
- Ollama 0.40.3, Qwen3-4B Q4_K_M, CPU-only, 8192 context. Test machine: 9 visible CPUs (8 CPU quota), 9.7 GiB RAM, no swap.
- Same-source genuine Whisper small/int8 recognition: 13.52s initially, cached for subsequent identical-source renders.
- Published baseline: 271.45s, three AI requests, failed graphic validation.
- Final AI: 90.56s, one request, no validation repair; render 99.77s; end-to-end after cached recognition 191.27s.
- Forced real-model timeout at 0.1s: fallback exported successfully in 57.84s. This short timeout is only the fault-injection test; production default remains 180s.
- Both MP4s: 37.3s, 720x1280, audio, complete FFmpeg decode succeeded. Six sampled AI frames were visually inspected. Voice waveform correlation against source: 0.998277; this supports alignment, but does not replace listening or subtitle review.
- Another genuine 12s excerpt from an unrelated source also exported successfully without injecting DANAVA.
- Browser fallback, completed badge, download, refresh and mobile 390px passed on a short silent clip; no page errors or overflow. A separate full-source browser run also finished successfully but exceeded the test's 240s browser wait under concurrent recognition/render load, so it is not reported as a browser automation pass.
- These timings are observations, not a controlled benchmark: CPU load differed across runs. An earlier successful full-AI run planned in 54.2s; the final run took 90.6s under concurrent tests.
- Remaining limitation: source ASR has ambiguous spellings (including Veroi and chết); they were not guessed away. The automated version uses the approved visual style but is not identical to the manually curated demo.

Full stage evidence is in FALLBACK_VERIFICATION.json. Publication was requested after validation.
