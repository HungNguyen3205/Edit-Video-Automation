"""Explicit, conservative filler-only source cuts. The model never chooses timestamps."""
import copy
import hashlib
import json
import math
import re
import unicodedata
from editing import length, validate

FILLERS={'ờ','ờm','ừm','um','umm','uh','erm','hmm'}


def token(text):
    return ''.join(c for c in unicodedata.normalize('NFC',text).casefold() if c.isalpha())


def explicitly_disabled(prompt):
    return bool(re.search(r'(?:giữ|không\s+(?:xóa|xoá|bỏ|cắt|loại))[^.!?\n]{0,30}(?:tiếng đệm|\bờ\b|\bừm\b|\bờm\b)',prompt,re.I))


def requested(prompt):
    if explicitly_disabled(prompt):return False
    return bool(re.search(r'(?:xóa|xoá|bỏ|cắt|loại)[^.!?\n]{0,40}(?:tiếng đệm|\bờ\b|\bừm\b|\bờm\b)',prompt,re.I))


def source_key(plan):
    value={'assets':[(a['id'],a.get('sha256','')) for a in plan['assets'] if a['type']=='video'],
        'recognition':plan.get('recognition_cache'),
        'words':[(s.get('asset_id'),s['start'],s['end'],s['text'],s.get('words',[])) for s in plan.get('recognition_subtitles',plan.get('subtitles',[]))]}
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def detect(plan,event=None):
    frames=plan['output_settings']['fps'];words=[]
    for sub in plan.get('subtitles',[]):
        aid=sub.get('asset_id') or plan['video_clips'][0]['asset_id']
        words.extend({**w,'asset_id':aid,'token':token(w['word'])} for w in sub.get('words',[]))
    words.sort(key=lambda w:(w['asset_id'],w['start'],w['end']))
    cuts=[];review=[]
    for i,word in enumerate(words):
        if event is not None and event.is_set():raise InterruptedError('Đã hủy xử lý tiếng đệm.')
        if word['token'] not in FILLERS:continue
        prev=words[i-1] if i and words[i-1]['asset_id']==word['asset_id'] else None
        nxt=words[i+1] if i+1<len(words) and words[i+1]['asset_id']==word['asset_id'] else None
        if any(c in word['word'] for c in '\"“”‘’') or prev and prev['token'] in ('từ','chữ','tiếng'):
            continue
        if nxt and nxt['token']=='là':continue
        probability=word.get('probability');duration=word['end']-word['start']
        reason=None
        if not isinstance(probability,(float,int)) or isinstance(probability,bool) or not math.isfinite(probability) or probability<.65:reason='Nhận dạng tiếng đệm chưa chắc.'
        elif not .18<=duration<=1.5:reason='Độ dài tiếng đệm chưa đủ rõ.'
        left=max(0,word['start']-.025,prev['end']+.025 if prev else 0)
        right=min(word['end']+.025,nxt['start']-.025 if nxt else word['end']+.025)
        # Round inward to video frames, never into neighbouring meaningful words.
        left=math.ceil((left-1e-8)*frames)/frames;right=math.floor((right+1e-8)*frames)/frames
        if not reason and (right-left<.14 or left>word['start']+1/frames or right<word['end']-1/frames):reason='Điểm cắt quá sát lời nói; cần nghe lại.'
        row={'asset_id':word['asset_id'],'start':round(left,6),'end':round(right,6),'token':word['token']}
        if reason:review.append({**row,'reason':reason})
        else:cuts.append(row)
    # Overlapping ASR words are not permission to cut across other speech.
    return cuts,review


def split_clips(clips,cuts,protected=()):
    result=[];cursor=0
    for clip in clips:
        start=clip['source_in'];end=start+clip['duration'];position=start
        selected=sorted((c for c in cuts if c['asset_id']==clip['asset_id'] and c['end']>start and c['start']<end),key=lambda c:c['start'])
        spans=[]
        for cut in selected:
            # A run of fillers can leave a tiny silent sliver. Join its cuts
            # only if there is no recognized meaningful word in that gap.
            if spans and cut['start']-spans[-1]['end']<.08 and not any(w['asset_id']==clip['asset_id'] and w['start']<=cut['start'] and w['end']>=spans[-1]['end'] for w in protected):
                spans[-1]['end']=max(spans[-1]['end'],cut['end'])
            else:spans.append(dict(cut))
        for cut in spans:
            lo=max(start,cut['start']);hi=min(end,cut['end'])
            if lo>position+.0001:
                if lo-position<.08:return None
                result.append({**clip,'id':clip['id']+'_speech'+str(len(result)),'source_in':position,'duration':lo-position,'timeline_start':cursor});cursor+=lo-position
            position=max(position,hi)
        if end>position+.0001:
            if end-position<.08:return None
            result.append({**clip,'id':clip['id']+'_speech'+str(len(result)),'source_in':position,'duration':end-position,'timeline_start':cursor});cursor+=end-position
    return result if 0<len(result)<=100 else None


def clean_speech(plan,enabled=False,event=None):
    if event is not None and event.is_set():raise InterruptedError('Đã hủy xử lý tiếng đệm.')
    p=copy.deepcopy(plan);previous=p.pop('speech_cleanup',{})
    if not enabled:return p
    key=source_key(plan);warnings=[];reused=False
    if p.get('user_subtitles'):
        # A manual edit must never be replaced by recognition text. Reuse only
        # previously verified cuts on the exact same source/ASR configuration.
        if previous.get('applied') and previous.get('source_key')==key:
            cuts=copy.deepcopy(previous['cuts']);review=[];reused=True
            for sub in p['user_subtitles']:
                # Restoring an explicit filler in reviewed text revokes that cut.
                cuts=[c for c in cuts if not (sub.get('asset_id',c['asset_id'])==c['asset_id'] and sub['start']<c['end'] and sub['end']>c['start'] and c['token'] in [token(x) for x in sub['text'].split()])]
        else:
            cuts=[];review=[];warnings.append('Phụ đề đã sửa thủ công chưa có điểm cắt tiếng đệm được xác nhận; giữ nguyên tiếng để tránh cắt nhầm.')
    else:
        cuts,review=detect(p,event)
        if not any(s.get('words') for s in p.get('subtitles',[])):
            warnings.append('Chưa có timestamp từ để xác định tiếng đệm; không tự cắt theo chữ hoặc khoảng lặng.')
    # Ignore recognition outside the selected source ranges. Require whole
    # tokens so a partially selected filler never becomes a partial word cut.
    cuts=[c for c in cuts if any(v['asset_id']==c['asset_id'] and v['source_in']<=c['start'] and v['source_in']+v['duration']>=c['end'] for v in p['video_clips'])]
    protected=[{**w,'asset_id':s.get('asset_id') or p['video_clips'][0]['asset_id']} for s in p.get('recognition_subtitles',p.get('subtitles',[])) for w in s.get('words',[]) if token(w['word']) not in FILLERS]
    original=length(p);clips=split_clips(p['video_clips'],cuts,protected) if cuts else None
    removed=original-sum(c['duration'] for c in clips) if clips else 0
    if len(cuts)>40 or removed>original*.25 or clips is not None and sum(c['duration'] for c in clips)<.5:
        clips=None;removed=0;warnings.append('Số điểm cắt/thời lượng vượt giới hạn an toàn; giữ nguyên nguồn để duyệt lại.')
    if cuts and clips is None:warnings.append('Không tạo được các đoạn giữ đủ dài; chưa áp dụng cắt tiếng đệm.')
    if cuts and not any(token(w['word']) not in FILLERS for s in p.get('recognition_subtitles',p.get('subtitles',[])) for w in s.get('words',[])):
        clips=None;removed=0;warnings.append('Chưa xác định được lời nói có nghĩa còn lại; giữ nguyên nguồn.')
    applied=bool(clips and removed>.01)
    if applied:
        p['video_clips']=clips;p['storyboard']=[]
        if reused:
            from automatic_director import aligned_words
            raw=plan.get('recognition_subtitles',[])
            p['subtitles']=copy.deepcopy(p['user_subtitles'])
            for sub in p['subtitles']:
                original_sub=next((s for s in raw if abs(s['start']-sub['start'])<.02 and abs(s['end']-sub['end'])<.02),None)
                if original_sub and original_sub.get('words'):
                    sub['words']=aligned_words(original_sub['words'],sub['text'],sub['start'],sub['end'])
                    sub['alignment']='derived_for_edited_captions'
                elif not sub.get('words'):
                    # No trustworthy within-sentence alignment: decline this retry.
                    return clean_speech({**plan,'speech_cleanup':{}},enabled=True,event=event)
        else:
            kept=[]
            for sub in p.get('subtitles',[]):
                aid=sub.get('asset_id') or plan['video_clips'][0]['asset_id']
                words=[w for w in sub.get('words',[]) if not (token(w['word']) in FILLERS and any(c['asset_id']==aid and c['start']<w['end'] and c['end']>w['start'] for c in cuts))]
                if len(words)!=len(sub.get('words',[])):
                    sub['words']=words;sub['text']=' '.join(w['word'].strip() for w in words)
                if sub['text'].strip():kept.append(sub)
            p['subtitles']=kept
    p['speech_cleanup']={'version':1,'enabled':True,'applied':applied,'source_key':key,'source_timeline_seconds':round(original,6),
        'removed_seconds':round(removed,6),'removed_count':len(cuts) if applied else 0,'cuts':cuts if applied else [],
        'review_candidates':review,'reused_verified_cuts':reused,'warnings':warnings,'audio_edge_fade_seconds':.006,
        'method':'word_timestamp_filler_only','model_weights_trained':False}
    if review:warnings.append(f'Có {len(review)} tiếng đệm chưa chắc điểm cắt; đã giữ để nghe lại.')
    return validate(p,p['assets'])
