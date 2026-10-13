# Branding and illustrations in one-click editing

Below the prompt, the simple interface now provides **Thương hiệu & hình ảnh**:

- **Tên thương hiệu**: persistent text at the bottom of every frame.
- **Thêm logo**: PNG/JPG/WEBP, top-right placement. Transparent PNG is preserved, not padded with a black rectangle.
- **Thêm ảnh minh họa**: up to six project-owned images. A topic matches the image with source speech; no topic uses the selected order. Missing matches or insufficient scenes produce a visible warning.
- **Tự thêm đồ họa minh họa theo lời nói**: enabled by default. Disabling it retains explicitly selected images and branding.

When AI completes, its scene choices are kept. If it fails or only supplies camera scenes, the visual helper can add neutral assistant artwork and association diagrams only for clearly recognised source concepts. It does not fabricate product screenshots, prices, features, claims, or stock photos. Uncertain recognition is not promoted into large fallback headings. Without a clear concept or chosen image, the tool explains how to add an image instead of inventing one.

The helper `video_branding.py` composes project photos, safe source graphics and logo/footer settings into the existing storyboard and overlay schema. Existing framework, renderer, API routes and advanced editor remain. New make-video fields are optional: brand_name, logo_asset_id, image_asset_ids, illustrations. Upload optionally accepts keywords; a logo upload is marked with usage=logo. Logo assets are excluded from automatic illustration searches. Removing a chosen image also excludes it from simple-mode searches on rerender. No paid AI service or new production dependency was added.

Brand settings and selected assets restore on refresh/history. Assets must belong to the current project. Brand text uses escaped ASS, image markup remains escaped, and the existing cancel/duration/full-decode validation stays active. The input prompt still accepts 4000 characters; the internal Options brief allows 4500 to accommodate appended brand/layout instructions.

## Validation

87 tests passed, with real MP4 pixel checks for uploaded pictures, transparent logo corners, brand text and repeated exports without duplicate logos. Browser checks passed for upload, refresh, removal/rerender, mobile 390px, and no page errors. A genuine 37.3-second original video was recognised with Whisper small/int8 and exported with two source-based illustrations despite an unavailable Ollama endpoint. The final rerender reused only that same-source recognition. Full FFmpeg decode passed; six frames were inspected. The demonstration logo visibly says LOGO MẪU and is not the official DANAVA logo. Detailed evidence is in BRANDING_VERIFICATION.json.

## Update on Windows

Stop the previous backend, pull main, then restart:

```powershell
git pull origin main
python main.py
```

Refresh with Ctrl+F5. Preserve any local changes if Git reports a conflict. Enter your brand name and upload your official logo in the new panel; the demo placeholder is not bundled as a default logo. Review captions before posting because some ASR words remain ambiguous.
