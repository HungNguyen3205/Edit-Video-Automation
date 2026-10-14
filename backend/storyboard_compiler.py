"""Validated semantic storyboard -> approved motion style -> real MP4."""
import copy
import json
import os
import signal
import subprocess
import time
from pathlib import Path
from asset_resolver import AssetResolver
from editing import compile_render, filter_path, length, probe, validate
from storyboard_style import write_storyboard_ass

from project_paths import PROJECT_ROOT
BASE_DIR = PROJECT_ROOT
MOTION_DIR = BASE_DIR / 'motion_engine'


def run(command, event=None, timeout=600, cwd=None):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, cwd=cwd, start_new_session=os.name != 'nt')
    start = time.monotonic()
    try:
        while True:
            if event is not None and event.is_set():
                raise InterruptedError('Đã hủy dựng storyboard.')
            if time.monotonic()-start > timeout:
                raise RuntimeError('Quá thời gian dựng cảnh. Hãy thử bản xem trước hoặc giảm số cảnh.')
            try:
                stdout, stderr = process.communicate(timeout=.2)
                break
            except subprocess.TimeoutExpired:
                pass
        if process.returncode:
            raise RuntimeError('Không dựng được video: ' + (stderr or stdout)[-5000:])
    finally:
        if process.poll() is None:
            if os.name == 'nt':
                subprocess.run(['taskkill','/F','/T','/PID',str(process.pid)],capture_output=True)
            else:
                os.killpg(process.pid, signal.SIGKILL)
            process.communicate()


def compile_storyboard_scenes(plan, asset_dir, work_dir, output_path, preview=False,
                              visual_style='explainer_ref', event=None, progress=None, metrics=None, phase=None):
    started=time.monotonic()
    metrics=metrics if metrics is not None else {}
    metrics['graphics_seconds']=0.0
    plan = validate(plan, plan['assets'])
    asset_dir, work_dir, output_path = Path(asset_dir), Path(work_dir), Path(output_path)
    work_dir.mkdir(parents=True, exist_ok=True)
    storyboard = plan.get('storyboard', [])
    if not storyboard:
        raise ValueError('Chưa có storyboard. Chạy AI dựng video trước khi xuất.')
    fps = plan['output_settings']['fps']
    w, h = (360, 640) if preview else (720, 1280)
    total = min(12.0, length(plan)) if preview else length(plan)
    assets = {a['id']: a for a in plan['assets']}
    selected_images=set(plan.get('branding',{}).get('image_asset_ids',[]))
    selected_images.update(s.get('visual_asset_id') for s in storyboard if s.get('visual_asset_id'))
    resolver_assets=[a for a in plan['assets'] if a['id']!=plan.get('branding',{}).get('logo_asset_id')
        and (not plan.get('branding') or a['type']!='image' or a['id'] in selected_images)]
    resolver = AssetResolver(resolver_assets, asset_dir, work_dir)
    scene_files, cursor = [], 0.0
    clip=plan['video_clips'][0] if len(plan['video_clips'])==1 else None
    camera_source=(asset_dir/assets[clip['asset_id']]['filename']
        if clip and not preview and not plan.get('crop_reference_right_half')
        and clip.get('source_in',0)==0 and abs(clip['duration']-total)<.001
        and all(sc['scene_type']=='talking_head' for sc in storyboard) else None)
    if camera_source is not None:
        # Identical continuous source: avoid encoding every camera scene and
        # re-encoding their concat before the final effects/caption pass.
        assembled=camera_source
        metrics['scene_render_seconds']=0.0
        metrics['camera_source_reused']=True
        assembly_started=time.monotonic()
        if phase:
            phase('Đang dựng zoom, giọng nói và phụ đề từ video nguồn')
        if progress:
            progress(75)
    else:
        # Cumulative frame boundaries avoid drift across many short scenes.
        for i, sc in enumerate(storyboard):
            if cursor >= total - .0001:
                break
            end = min(total, sc['timeline_start'] + sc['duration'])
            frames = round(end * fps)-round(cursor * fps)
            if frames < 1:
                raise ValueError('Cảnh quá ngắn cho FPS hiện tại. Hãy gộp cảnh.')
            dur, typ = frames/fps, sc['scene_type']
            source = asset_dir / assets[sc['asset_id']]['filename']
            scene_file, src_in = work_dir / f'scene_{i}.mp4', sc['source_in']
            fit = f'scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps={fps},format=yuv420p'
            if typ in ('talking_head', 'broll'):
                input_opts = ['-ss',str(src_in),'-i',str(source)]
                if typ == 'broll':
                    visual = assets.get(sc.get('visual_asset_id'))
                    if not visual:
                        raise ValueError('B-roll cần ảnh/video minh họa thuộc dự án.')
                    path = asset_dir / visual['filename']
                    input_opts = ['-loop','1','-i',str(path)] if visual['type'] == 'image' else ['-ss',str(sc.get('visual_source_in',0)),'-i',str(path)]
                crop = 'crop=iw/2:ih:iw/2:0,' if typ == 'talking_head' and plan.get('crop_reference_right_half') else ''
                run(['ffmpeg','-v','error','-y',*input_opts,'-an','-vf',crop+fit,
                     '-frames:v',str(frames),'-c:v','libx264','-crf','20','-preset','fast',
                     '-threads','2',str(scene_file)], event)
            else:
                graphics_started=time.monotonic()
                if phase:
                    phase('Đang dựng minh họa và cảnh '+str(i+1))
                visual = assets.get(sc.get('visual_asset_id'))
                if visual and visual['type'] == 'video':
                    asset_path = work_dir / f'visual_frame_{i}.png'
                    run(['ffmpeg','-v','error','-y','-ss',str(sc.get('visual_source_in',0)),
                         '-i',str(asset_dir/visual['filename']),'-frames:v','1',str(asset_path)], event)
                else:
                    info = resolver.resolve_visual(query=sc.get('asset_query') or sc.get('headline',''),
                        fallback_title=sc.get('headline',''),fallback_badge=sc.get('badge_text',''),
                        badge_color=sc.get('badge_color','teal'),graphic_kind=sc.get('graphic_kind','auto'),
                        graphic_title=sc.get('graphic_title',''),graphic_items=sc.get('graphic_items',[]),
                        visual_asset_id=sc.get('visual_asset_id',''))
                    asset_path = info['local_path']
                from text_review import headline_layout
                from typography import profile_for, font_path
                profile = profile_for(plan)
                title,title_size=headline_layout(sc.get('headline',''),min(60,profile['heading_size']) if profile else 60,590,plan.get('proper_names',''),font_path(profile,'heading') if profile else None)
                cfg = {**sc,'headline':title,'headline_font_size':title_size,'duration':dur,'asset_path':str(asset_path),'footer':'' if plan.get('branding') else plan.get('brand_footer','')}
                if profile:
                    cfg.update(heading_font_file=profile['heading_file'],caption_font_file=profile['caption_file'],heading_weight=profile['heading_weight'],caption_weight=profile['caption_weight'])
                if plan.get('motion_style',{}).get('preset')=='dynamic_explainer':
                    cfg['motion_style']='dynamic_explainer'
                cfg_file = work_dir/f'motion_{i}.json'
                cfg_file.write_text(json.dumps(cfg,ensure_ascii=False),encoding='utf-8')
                raw = work_dir/f'motion_{i}.mp4'
                run(['node',str(MOTION_DIR/'render_scene.js'),'--input',str(cfg_file.resolve()),
                     '--output',str(raw.resolve()),'--width',str(w),'--height',str(h),'--fps',str(fps)],event,cwd=MOTION_DIR)
                if typ == 'talking_head_pip':
                    sw, sh = round(w*.9)//2*2, round(h*.43)//2*2
                    x, y = (w-sw)//2, round(h*.49)
                    run(['ffmpeg','-v','error','-y','-i',str(raw),'-ss',str(src_in),'-i',str(source),
                         '-filter_complex',f'[1:v]scale={sw}:{sh}:force_original_aspect_ratio=increase,crop={sw}:{sh},setsar=1[spk];[0:v][spk]overlay={x}:{y}[out]',
                         '-map','[out]','-an','-frames:v',str(frames),'-c:v','libx264','-crf','20','-preset','fast','-threads','2',str(scene_file)],event)
                else:
                    raw.replace(scene_file)
                metrics['graphics_seconds']+=time.monotonic()-graphics_started
            meta = probe(scene_file)
            if abs(meta['duration']-dur) > 1/fps+.01:
                raise RuntimeError(f'Cảnh {i+1} bị thiếu hình; không xuất video bị cụt.')
            scene_files.append(scene_file)
            cursor = end
            if progress:
                progress(20+int(55*cursor/total))
        metrics['scene_render_seconds']=round(time.monotonic()-started,3)
        metrics['graphics_seconds']=round(metrics['graphics_seconds'],3)
        assembly_started=time.monotonic()
        if phase:
            phase('Đang ghép cảnh, giọng nói và phụ đề')
        concat = work_dir/'concat.txt'
        concat.write_text(''.join("file '"+str(f.resolve()).replace("'", "'\\''")+"'\n" for f in scene_files),encoding='utf-8')
        assembled = work_dir/'assembled.mp4'
        run(['ffmpeg','-v','error','-y','-xerror','-f','concat','-safe','0','-i',str(concat),
             '-an','-vf',f'setpts=N/({fps}*TB),fps={fps}', '-c:v','libx264','-preset','fast','-crf','20',
             '-threads','2','-movflags','+faststart',str(assembled)],event)
        if abs(probe(assembled)['duration']-total) > 1/fps+.02:
            raise RuntimeError('Video nối cảnh sai thời lượng; hãy gộp hoặc sửa các cảnh quá ngắn.')
    # Original cuts remain authoritative for voice, music ducking and SFX.
    audio_plan = copy.deepcopy(plan)
    for key in ('subtitles','text_overlays','visual_overlays','effect_keyframes','storyboard'):
        audio_plan[key] = []
    audio_plan['output_settings'].update(width=120,height=120)
    for sc in storyboard:
        kind, start = sc.get('sound_effect','none'), sc['timeline_start']+.15
        if kind != 'none' and start < total-.1:
            if not any(t['kind'] != 'music' and abs(t['timeline_start']-start)<.3 for t in audio_plan['audio_tracks']):
                audio_plan['audio_tracks'].append({'id':f"sfx_{sc['scene_id']}",'kind':kind,'timeline_start':start,
                    'duration':min(.35,total-start),'volume':sc.get('sound_volume',.10)})
    carrier = work_dir/'audio_carrier.mp4'
    cmd,_ = compile_render(audio_plan,asset_dir,work_dir,carrier,preview)
    run(cmd,event)
    # Editable overlays/zooms now operate on the actual motion storyboard.
    picture = assembled
    if plan['visual_overlays'] or plan['effect_keyframes']:
        picture_plan = copy.deepcopy(plan)
        picture_plan['assets'].append({'id':'rendered_story','type':'video','filename':str(assembled.resolve()),'metadata':probe(assembled)})
        picture_plan['video_clips'] = [{'id':'rendered','asset_id':'rendered_story','source_in':0,'duration':total,'timeline_start':0}]
        for key in ('subtitles','text_overlays','audio_tracks','storyboard'):
            picture_plan[key] = []
        for key in ('visual_overlays','effect_keyframes'):
            picture_plan[key] = [{**e,'duration':min(e['duration'],total-e['timeline_start'])} for e in picture_plan[key] if e['timeline_start'] < total-.04]
        picture_plan['output_settings'].update(width=w,height=h,fit='cover')
        picture = work_dir/'picture_effects.mp4'
        cmd,_ = compile_render(picture_plan,asset_dir,work_dir,picture,False)
        run(cmd,event)
    ass = work_dir/'storyboard.ass'
    write_storyboard_ass(ass,plan,w,h)
    output_fit=f'scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps={fps},format=yuv420p,' if camera_source is not None else ''
    vf = output_fit+f"subtitles=filename='{filter_path(ass)}':fontsdir='{filter_path(MOTION_DIR/'fonts')}'"
    run(['ffmpeg','-v','error','-y','-i',str(picture),'-i',str(carrier),'-map','0:v:0','-map','1:a:0',
         '-vf',vf,'-t',str(total),'-c:v','libx264','-preset','fast','-crf','19','-threads','2',
         '-pix_fmt','yuv420p','-c:a','copy','-movflags','+faststart',str(output_path)],event)
    if abs(probe(output_path)['duration']-total) > 1/fps+.02:
        output_path.unlink(missing_ok=True)
        raise RuntimeError('MP4 cuối sai thời lượng; không lưu kết quả bị cụt.')
    metrics['assembly_seconds']=round(time.monotonic()-assembly_started,3)
    return total
