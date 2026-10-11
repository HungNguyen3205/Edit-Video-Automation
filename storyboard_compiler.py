"""Storyboard Motion Compiler: Renders and composites storyboard scenes

Combines Motion Graphics Engine (HTML5/React in Chrome) with source video speech audio and FFmpeg assembly.
"""
import copy
import json
import os
import re
import subprocess
from pathlib import Path

from asset_resolver import AssetResolver
from editing import filter_path, length, mapped_subtitles, probe, srt_content, write_ass

BASE_DIR = Path(__file__).resolve().parent
MOTION_DIR = BASE_DIR / 'motion_engine'

def compile_storyboard_scenes(plan, asset_dir, work_dir, output_path, preview=False, visual_style='explainer_ref'):
    """Compile storyboard scenes into an end-to-end MP4 video."""
    settings = plan.get('output_settings', {})
    w = settings.get('width', 720)
    h = settings.get('height', 1280)
    fps = settings.get('fps', 30)

    # Force 9:16 vertical ratio if explainer_ref is chosen
    if visual_style == 'explainer_ref' and w > h:
        w, h = 720, 1280

    if preview and max(w, h) > 640:
        ratio = 640 / max(w, h)
        w = int(w * ratio) // 2 * 2
        h = int(h * ratio) // 2 * 2

    assets = {a['id']: a for a in plan.get('assets', [])}
    main_clip = plan['video_clips'][0] if plan.get('video_clips') else None
    if not main_clip:
        raise ValueError('Không có video chính trong kế hoạch dựng.')

    main_asset = assets.get(main_clip['asset_id'])
    if not main_asset:
        raise ValueError('Không tìm thấy tài nguyên video chính.')

    main_video_path = asset_dir / main_asset['filename']
    resolver = AssetResolver(plan.get('assets', []), asset_dir, work_dir)

    storyboard = plan.get('storyboard', [])
    if not storyboard:
        # Fallback if no storyboard scenes
        raise ValueError('Kế hoạch không có storyboard.')

    scene_files = []
    total_duration = 0.0
    work_dir.mkdir(parents=True, exist_ok=True)

    # Render each storyboard scene
    for i, sc in enumerate(storyboard):
        sc_id = sc.get('scene_id', f'scene_{i}')
        sc_type = sc.get('scene_type', 'talking_head')
        dur = float(sc.get('duration', 3.0))
        if preview and total_duration + dur > 12.0:
            dur = max(0.5, 12.0 - total_duration)

        src_in = float(sc.get('source_in', 0))
        scene_mp4 = work_dir / f'sc_{i}.mp4'
        scene_audio = work_dir / f'audio_{i}.wav'

        # 1. Extract audio for this scene from main video
        audio_cmd = [
            'ffmpeg', '-hide_banner', '-y',
            '-ss', str(src_in), '-t', str(dur),
            '-i', str(main_video_path),
            '-vn', '-ar', '48000', '-ac', '2',
            str(scene_audio)
        ]
        res = subprocess.run(audio_cmd, capture_output=True, text=True)
        if res.returncode != 0:
            # If silence or failure, create silent wav
            silence_cmd = ['ffmpeg', '-hide_banner', '-y', '-f', 'lavfi', '-i', f'anullsrc=r=48000:cl=stereo', '-t', str(dur), str(scene_audio)]
            subprocess.run(silence_cmd, check=True, capture_output=True)

        # 2. Render Video Track for this scene
        if sc_type in ('explainer_card', 'comparison', 'statistic', 'step_list', 'cta'):
            # Resolve visual asset
            asset_info = resolver.resolve_visual(
                query=sc.get('asset_query') or sc.get('headline') or '',
                role='illustration',
                fallback_title=sc.get('headline', ''),
                fallback_badge=sc.get('badge_text', 'ĐIỂM NHẤN'),
                badge_color=sc.get('badge_color', 'teal')
            )

            # Build JSON payload for motion_engine
            scene_cfg = {
                'scene_type': sc_type,
                'duration': dur,
                'headline': sc.get('headline', ''),
                'subheadline': sc.get('subheadline', ''),
                'badge_text': sc.get('badge_text', ''),
                'badge_color': sc.get('badge_color', 'teal'),
                'stat_number': sc.get('stat_number', ''),
                'stat_label': sc.get('stat_label', ''),
                'steps': sc.get('steps', []),
                'badges': sc.get('badges', []),
                'asset_path': asset_info.get('local_path', ''),
                'warning_badge': sc.get('warning_badge', ''),
                'footer': '0786.668.222   tabcomgroup.vn'
            }
            if sc_type == 'comparison':
                left_img = resolver.resolve_visual('shopee', role='comparison_icon')
                right_img = resolver.resolve_visual('facebook', role='comparison_icon')
                scene_cfg['comparison_left'] = {
                    'badge': 'NỘI SÀN',
                    'title': 'TIKTOK / SHOPEE',
                    'image_path': left_img.get('local_path', ''),
                    'points': ['Khách rất gần hành vi mua', 'Tỷ lệ chốt đơn tức thì', 'Traffic sàn sẵn có']
                }
                scene_cfg['comparison_right'] = {
                    'badge': 'NGOẠI SÀN',
                    'title': 'FACEBOOK / WEB',
                    'image_path': right_img.get('local_path', ''),
                    'points': ['Chủ động tệp khách riêng', 'Không sợ sàn đổi thuật toán', 'Giá trị trọn đời cao']
                }

            json_path = work_dir / f'motion_{i}.json'
            motion_raw = work_dir / f'motion_raw_{i}.mp4'
            json_path.write_text(json.dumps(scene_cfg, ensure_ascii=False, indent=2), encoding='utf-8')

            # Run motion_engine CLI
            node_cmd = [
                'node', str((MOTION_DIR / 'render_scene.js').resolve()),
                '--input', str(json_path.resolve()),
                '--output', str(motion_raw.resolve()),
                '--width', str(w),
                '--height', str(h),
                '--fps', str(fps)
            ]
            node_res = subprocess.run(node_cmd, capture_output=True, text=True, cwd=str(MOTION_DIR), timeout=180)
            if node_res.returncode != 0:
                raise RuntimeError(f'Motion Engine lỗi ở cảnh {i}: {node_res.stderr or node_res.stdout}')

            # Combine motion graphic video with speaker speech audio
            mux_cmd = [
                'ffmpeg', '-hide_banner', '-y',
                '-i', str(motion_raw),
                '-i', str(scene_audio),
                '-c:v', 'copy',
                '-c:a', 'aac', '-b:a', '128k',
                '-shortest',
                str(scene_mp4)
            ]
            subprocess.run(mux_cmd, check=True, capture_output=True)

        elif sc_type == 'talking_head_pip':
            # White canvas with speaker video positioned at bottom
            asset_info = resolver.resolve_visual(
                query=sc.get('asset_query') or sc.get('headline') or 'analytics',
                role='pip_illustration',
                fallback_title=sc.get('headline', ''),
                fallback_badge=sc.get('badge_text', 'NGOẠI SÀN'),
                badge_color=sc.get('badge_color', 'navy')
            )
            scene_cfg = {
                'scene_type': 'talking_head_pip',
                'duration': dur,
                'headline': sc.get('headline', ''),
                'subheadline': sc.get('subheadline', ''),
                'badge_text': sc.get('badge_text', 'NGOẠI SÀN'),
                'badge_color': sc.get('badge_color', 'navy'),
                'asset_path': asset_info.get('local_path', ''),
                'footer': '0786.668.222   tabcomgroup.vn'
            }
            json_path = work_dir / f'pip_{i}.json'
            pip_bg = work_dir / f'pip_bg_{i}.mp4'
            json_path.write_text(json.dumps(scene_cfg, ensure_ascii=False, indent=2), encoding='utf-8')

            node_cmd = [
                'node', str(MOTION_DIR / 'render_scene.js'),
                '--input', str(json_path),
                '--output', str(pip_bg),
                '--width', str(w),
                '--height', str(h),
                '--fps', str(fps)
            ]
            subprocess.run(node_cmd, check=True, capture_output=True, cwd=str(MOTION_DIR), timeout=180)

            # Composite speaker into bottom container
            speaker_w = int(w * 0.90) // 2 * 2
            speaker_h = int(h * 0.40) // 2 * 2
            pos_x = (w - speaker_w) // 2
            pos_y = h - speaker_h - 60

            comp_cmd = [
                'ffmpeg', '-hide_banner', '-y',
                '-i', str(pip_bg),
                '-ss', str(src_in), '-t', str(dur), '-i', str(main_video_path),
                '-filter_complex',
                f"[1:v]scale={speaker_w}:{speaker_h}:force_original_aspect_ratio=increase,crop={speaker_w}:{speaker_h}[spk];[0:v][spk]overlay={pos_x}:{pos_y}[outv]",
                '-map', '[outv]', '-map', '1:a',
                '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'aac',
                str(scene_mp4)
            ]
            subprocess.run(comp_cmd, check=True, capture_output=True)

        else:
            # talking_head (raw camera) or broll
            badge_text = sc.get('badge_text', '')
            badge_color = sc.get('badge_color', 'teal')
            
            # If input is a side-by-side comparison video (aspect ratio > 1.4), crop the right half ("Claude Edit")
            main_w = main_asset.get('metadata', {}).get('width', 1280)
            main_h = main_asset.get('metadata', {}).get('height', 720)
            if main_w / max(1, main_h) > 1.4:
                # Crop right half: x = in_w / 2
                filter_str = f"crop=iw/2:ih:iw/2:0,scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps},format=yuv420p"
            else:
                filter_str = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps},format=yuv420p"

            if badge_text:
                bcolor = '0x0D9488' if badge_color == 'teal' else '0x1E293B' if badge_color == 'navy' else '0xDC2626'
                filter_str += f",drawtext=font='Arial':text='{badge_text}':fontsize={round(w*0.045)}:fontcolor=white:box=1:boxcolor={bcolor}@0.9:boxborderw=10:x=(w-tw)/2:y=h*0.09"

            cmd = [
                'ffmpeg', '-hide_banner', '-y',
                '-ss', str(src_in), '-t', str(dur),
                '-i', str(main_video_path),
                '-vf', filter_str,
                '-c:v', 'libx264', '-preset', 'ultrafast',
                '-c:a', 'aac', '-b:a', '128k',
                str(scene_mp4)
            ]
            subprocess.run(cmd, check=True, capture_output=True)

        scene_files.append(scene_mp4)
        total_duration += dur
        if preview and total_duration >= 12.0:
            break

    # 3. Concatenate all rendered scenes together
    concat_list = work_dir / 'concat.txt'
    with concat_list.open('w', encoding='utf-8') as f:
        for sf in scene_files:
            posix_p = sf.resolve().as_posix()
            f.write(f"file '{posix_p}'\n")

    assembled = work_dir / 'assembled.mp4'
    concat_cmd = [
        'ffmpeg', '-hide_banner', '-y',
        '-f', 'concat', '-safe', '0',
        '-i', str(concat_list),
        '-c:v', 'libx264', '-preset', 'ultrafast',
        '-c:a', 'aac',
        str(assembled)
    ]
    res = subprocess.run(concat_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f'Lỗi nối các cảnh FFmpeg ({res.returncode}): {res.stderr}')

    # 4. Burn ASS Subtitles if present
    final_video = assembled
    subs = mapped_subtitles(plan)
    if subs:
        sub_ass = work_dir / 'subtitles.ass'
        write_ass(sub_ass, subs, w, h, visual_style=visual_style)
        subbed = work_dir / 'subbed.mp4'
        sub_cmd = [
            'ffmpeg', '-hide_banner', '-y',
            '-i', str(assembled),
            '-vf', f"subtitles=filename='{filter_path(sub_ass)}'",
            '-c:v', 'libx264', '-preset', 'ultrafast' if preview else 'fast',
            '-c:a', 'copy',
            str(subbed)
        ]
        subprocess.run(sub_cmd, check=True, capture_output=True)
        final_video = subbed

    # 5. Move/copy final video to output_path
    if final_video.exists():
        if output_path.exists():
            output_path.unlink()
        final_video.rename(output_path)
    else:
        raise RuntimeError('Không tạo được file video cuối cùng.')

    return total_duration
