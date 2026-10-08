# DANAVA Video Studio

Local-first video editor: FastAPI + FFmpeg + JavaScript, with a light Vietnamese UI and locally bundled Lucide icons. No AI API keys or external render service.

## Why the original project did not auto-edit

The original Auto Edit button inserted one image at second 0 and required an image. It did not create a transcript, zoom, titles, or a finished MP4. The renderer ignored `effect_keyframes` and `text_overlays`, rendered only the first clip, required audio, and did not normalize overlay size/time. The browser's image preview was always visible regardless of its timeline interval. The old “Sprints 1–7 complete” status overstated the implementation.

This branch replaces that button with a backend pipeline: optional local speech recognition → deterministic edit plan → actual zoom/titles/keyword-linked illustrations → MP4. No extra image is required.

## Install and run

Python 3.10+ and FFmpeg/FFprobe with libx264, libass/subtitles and drawtext support are required. Install a font with Vietnamese coverage such as DejaVu Sans. On Ubuntu:

```bash
sudo apt-get install ffmpeg fonts-dejavu-core
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

On Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

Install FFmpeg and FFprobe separately and add them to PATH on Windows. Set `VIDEO_FONT_FILE` to an existing Vietnamese-capable `.ttf` file if the default font is not available.

Open **http://127.0.0.1:8000/**. No frontend build or CDN connection is required. The server binds to localhost; this is a single-user local tool, not a hardened public upload service.

### Optional automatic Vietnamese captions

```bash
pip install -r requirements-ai.txt
```

Whisper runs on CPU, reuses one loaded model, and caches downloaded model weights. The first run needs Internet to download the model. Default `WHISPER_MODEL=base`; set `WHISPER_MODEL=tiny` for a lighter test, accepting lower accuracy. Installing PyTorch can be large; choose a compatible CPU wheel for your machine if GPU support is unnecessary.

If Whisper is absent, the UI turns automatic recognition off and explains how to install it. You can import a UTF-8 SRT instead, or render zoom/opening text without captions. Turning recognition on without Whisper produces an actionable error, not fake success. Existing captions are reused. Use “Tạo phụ đề” to explicitly regenerate them.

## Use

1. Create a project and upload a main video.
2. Optionally add an opening headline and illustrations. Give illustrations comma-separated keywords to suggest placement against captions.
3. Select a rhythm and click **Tự động dựng & xuất**. It generates the plan and renders a complete MP4.
4. Switch between **Video gốc** and **Bản dựng**. The latter is an actual rendered video, not an inaccurate browser simulation.
5. Expand **Chỉnh bản dựng chi tiết** to trim clips, correct captions, edit titles, or time/place illustrations. Save, then export the edited plan.
6. **Xem thử 12 giây** renders up to the first 12 seconds at a lower resolution. A preview is clearly separate from the full downloadable MP4.

Captions use source timestamps; titles, zoom and illustrations use output timeline timestamps. Clips concatenate in order with source audio or generated silence. Aspect changes use padding by default. Saving a changed plan hides the stale download until a new MP4 is exported.

Auto-generated effects are replaced on regeneration; manual edits are kept. Trimming clamps/removes auto effects outside the new duration. Manual illustrations that no longer fit must be corrected or removed.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `VIDEO_DATA_DIR` | `./data` | Persistent projects, sources, results |
| `MAX_UPLOAD_MB` | `500` | Per-file upload limit |
| `WHISPER_MODEL` | `base` | Local speech recognition model |
| `VIDEO_FONT_FILE` | unset | Absolute path to a Vietnamese-capable TTF for headline rendering |

One heavy job runs at a time. Progress is read from FFmpeg output; recognition uses a truthful phase indicator. Render cancellation terminates FFmpeg. Cancellation during model loading/recognition takes effect at the next pipeline boundary. Interrupted jobs are marked failed after restart. Back up the entire `data` folder, and keep dependencies/models/fonts available when moving machines.

## What this does and does not automate

- Real timed zoom with easing, fading headline text, two-line caption pages, properly timed/scaled image and video illustrations, multi-clip audio/video concatenation, preview and export.
- Planning is **rule-based**, not an LLM that understands the whole story. Highlights extract source words; illustrations match user-provided keywords. It does not invent captions, generate images, search stock footage, track faces, remove filler/silence, select ideal beats, mix music, or guarantee a professional edit for every upload.
- With one video and no transcript, it adds time-based zoom and an optional user headline. To get content-linked titles/illustrations, install recognition or import SRT.
- CPU speed and recognition accuracy depend on the video and machine; no universal speed claim.
- Local single-process use only. Public hosting/multiple worker processes require authentication, shared task storage/queue, resource limits, and access controls first.

## Verification

```bash
pip install -r requirements-dev.txt
python -m pytest -q
node --check frontend/app.js
```

Tests render real FFmpeg output and verify aspect/duration/audio, video-only automation, timed image/video overlays, multi-clip concat with silent sources, caption remapping after trim, SRT, preview, validation, revision conflicts and manual-edit preservation. Speech recognition/model downloads are separate integration checks, not mocked as successful by these tests.

See `AUDIT.md` and `PROJECT_STATUS.md` for verified results and remaining limitations.

### Existing MVP projects

Existing schema-v1 projects are migrated when opened: source metadata is probed, legacy pixel overlay coordinates are converted, and sources/captions remain in place. Back up `data` before switching branches. Generated timing is clamped when trimming; incompatible manual timing is reported for correction.

### UI appears unstyled or still dark after updating

New HTML must load the matching CSS/JS. Frontend assets now use versioned absolute URLs and `Cache-Control: no-cache, must-revalidate` so the browser revalidates them. Update the complete branch, restart `python main.py`, then hard-reload the page (Ctrl+Shift+R on Windows). If the issue remains, check that `/frontend/styles.css?v=studio-20261008-2` responds with the new light stylesheet and that the running server points to this checkout.
