"""Small offline image catalog and source-grounded photo beats; no network calls."""
import copy
import json
import re
from pathlib import Path
from project_paths import PROJECT_ROOT, SKILLS_DIR

IMAGE_DIR=PROJECT_ROOT/'motion_engine/images'


def catalog():
    try:
        data=json.loads((SKILLS_DIR/'visual_library.json').read_text(encoding='utf-8'))
        if data.get('schema_version')!=1:return []
        entries=[]
        for entry in data['images']:
            if not re.fullmatch(r'[a-z][a-z0-9_]{1,39}',entry['id']):return []
            name=entry['file']
            if Path(name).name!=name or Path(name).suffix not in ('.webp','.png','.jpg'):return []
            if not isinstance(entry['keywords'],list) or not 1<=len(entry['keywords'])<=20:return []
            if any(not isinstance(k,str) or not 1<=len(k)<=60 for k in entry['keywords']):return []
            if (IMAGE_DIR/name).is_file():entries.append(entry)
        return entries[:20]
    except (OSError,ValueError,KeyError,TypeError):return []


def library_image(identifier):
    entry=next((x for x in catalog() if x['id']==identifier),None)
    if entry is None:raise ValueError('Ảnh thư viện không tồn tại; khôi phục tài nguyên của dự án.')
    return IMAGE_DIR/entry['file']


def tokens(text):return re.findall(r'[^\W_]+',text.casefold())


def phrase_in(phrase,text):
    a=tokens(phrase);b=tokens(text)
    return bool(a) and any(b[i:i+len(a)]==a for i in range(len(b)-len(a)+1))


def apply_library_visuals(plan,prompt='',enabled=True):
    p=copy.deepcopy(plan)
    if not enabled or not p.get('branding',{}).get('illustrations',True) or re.search(r'không (?:thêm |chèn |dùng |cần )?(?:minh họa|đồ họa|hình|ảnh)',prompt,re.I):return p
    scenes=p.get('storyboard',[])
    if len(scenes)<3:return p
    used={s.get('library_visual_id') for s in scenes};selected={};taken=set()
    for entry in catalog():
        if entry['id'] in used:continue
        candidates=[]
        for i,sc in enumerate(scenes[1:-1],1):
            if i in taken or sc.get('visual_asset_id') or sc.get('library_visual_id') or sc['duration']<2.4:continue
            speech=sc.get('transcript_meaning','')
            matches=[k for k in entry['keywords'] if phrase_in(k,speech)]
            if not matches:continue
            # Prefer exact local concepts; never match 'AI' inside 'hai' or a name.
            score=max(len(tokens(k)) for k in matches)
            if any(abs(sc['timeline_start']-scenes[j]['timeline_start'])<4 for j in taken):continue
            candidates.append((score,-i,i,matches))
        if not candidates:continue
        _,_,index,matches=max(candidates)
        selected[index]=(entry,matches);taken.add(index)
        if len(used-{None})+len(selected)>=2:break
    if not selected:return p
    result=[]
    for i,sc in enumerate(scenes):
        if i not in selected:result.append(sc);continue
        entry,matches=selected[i];duration=sc['duration'];start=sc['timeline_start']
        # Keep the speaker between visual beats; no speech or time is removed.
        lead=.4 if duration>5.4 else 0
        beat=min(4.2,duration-lead)
        if duration-lead-beat<.6:beat=duration-lead
        chunks=[]
        if lead:chunks.append((0,lead,False))
        chunks.append((lead,beat,True))
        if duration-lead-beat>.02:chunks.append((lead+beat,duration-lead-beat,False))
        layout='full' if len([s for s in result if s.get('library_visual_id')])%2==0 else 'pip'
        for n,(offset,length,is_photo) in enumerate(chunks):
            part=copy.deepcopy(sc);part.update(scene_id=f"{sc['scene_id']}_photo{n}",timeline_start=start+offset,duration=length)
            part.pop('motion',None)
            if is_photo:
                part.update(scene_type='explainer_card' if layout=='full' else 'talking_head_pip',
                    library_visual_id=entry['id'],photo_layout=layout,library_match=matches,
                    animation_in='fade',animation_out='none',sound_effect='none')
                # A generic illustration is not a product image or customer case study.
                part['graphic_items']=[];part['graphic_title']='';part['badge_text']=''
                if part.get('headline') and not phrase_in(part['headline'],sc.get('transcript_meaning','')):part['headline']=''
            else:
                part.update(scene_type='talking_head',sound_effect='none',headline='',badge_text='')
                part.pop('library_visual_id',None);part.pop('photo_layout',None)
            result.append(part)
    p['storyboard']=result
    p.setdefault('director',{})['library_visuals']=[{'scene_index':i,'id':s['library_visual_id'],
        'source':'local_generated_illustration','matched_phrases':s.get('library_match',[])} for i,s in enumerate(result) if s.get('library_visual_id')]
    p['director']['warnings']=list(dict.fromkeys([*[w for w in p['director'].get('warnings',[]) if not w.startswith('Chưa đủ nội dung rõ để chọn minh họa tự động.')],
        'Ảnh thư viện là minh họa tổng hợp, không phải ảnh khách hàng hoặc giao diện sản phẩm thật.']))
    from editing import validate
    return validate(p,p['assets'])
