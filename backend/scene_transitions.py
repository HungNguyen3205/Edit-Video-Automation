"""Short picture dissolves at visual changes, without overlapping the voice timeline."""
from pathlib import Path


def transition_frames(previous,current,fps):
    if previous.get('motion',{}).get('animate') is not True or current.get('motion',{}).get('animate') is not True:return 0
    if previous['scene_type']==current['scene_type']=='talking_head':
        has_intent = bool(current.get('transition') in ('fade','dissolve') or
                          current.get('transition_in') in ('fade','dissolve') or
                          current.get('allow_camera_transition') is True)
        is_continuous = bool(current.get('is_continuous_speech'))
        if not (has_intent and not is_continuous):
            return 0
    seconds=min(current.get('motion',{}).get('transition_seconds',0),previous['duration']/3,current['duration']/3,.25)
    return max(0,round(seconds*fps))


def concat_file(path,files):
    path.write_text(''.join("file '"+str(f.resolve()).replace("'", "'\\''")+"'\n" for f in files),encoding='utf-8')


def assemble_scenes(files,scenes,fps,output,work,run,event=None):
    """Pad only outgoing pictures by the dissolve length, then overlap that pad.

    Incoming frame zero still starts at its original boundary. Each picture
    timeline and the final duration stay unchanged; audio is assembled elsewhere.
    Adjacent camera cuts are remuxed as groups, avoiding hundreds of decoders.
    """
    marks=[0]+[transition_frames(a,b,fps) for a,b in zip(scenes,scenes[1:])]
    if not any(marks):
        listing=work/'concat.txt';concat_file(listing,files)
        run(['ffmpeg','-v','error','-y','-xerror','-f','concat','-safe','0','-i',str(listing),'-an',
             '-vf',f'setpts=N/({fps}*TB),fps={fps}','-c:v','libx264','-preset','fast','-crf','20',
             '-threads','2','-movflags','+faststart',str(output)],event)
        return {'count':0,'method':'hard_cuts'}
    groups=[]
    for i,(file,scene) in enumerate(zip(files,scenes)):
        if i==0 or marks[i]:groups.append({'files':[],'frames':0,'fade_frames':marks[i]})
        groups[-1]['files'].append(file);groups[-1]['frames']+=round(scene['duration']*fps)
    inputs=[];filters=[]
    for i,group in enumerate(groups):
        path=group['files'][0]
        if len(group['files'])>1:
            listing=work/f'group_{i}.txt';concat_file(listing,group['files']);path=work/f'group_{i}.mp4'
            run(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',str(listing),'-map','0:v:0','-an','-c:v','copy',str(path)],event)
        inputs+=['-threads','1','-i',str(path)]
        filters.append(f'[{i}:v]fps={fps},settb=AVTB,setpts=PTS-STARTPTS,format=yuv420p[v{i}]')
    current='v0';cursor=groups[0]['frames']
    for i,group in enumerate(groups[1:],1):
        fade=group['fade_frames']/fps
        filters.append(f'[{current}]tpad=stop_mode=clone:stop_duration={fade}[pad{i}]')
        filters.append(f'[pad{i}][v{i}]xfade=transition=fade:duration={fade}:offset={cursor/fps}[mix{i}]')
        current=f'mix{i}';cursor+=group['frames']
    run(['ffmpeg','-v','error','-y','-xerror',*inputs,'-filter_complex_threads','1','-filter_complex',';'.join(filters),
         '-map',f'[{current}]','-an','-frames:v',str(cursor),'-r',str(fps),'-c:v','libx264','-preset','fast',
         '-crf','20','-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',str(output)],event)
    return {'count':len(groups)-1,'method':'padded_picture_dissolve','maximum_seconds':max(marks)/fps,'voice_overlap':False}
