"""Apply optional project photos, safe source graphics and persistent branding."""
import copy
import re
from editing import length, validate
from automatic_director import correct_recognition_copy
from asset_resolver import normalize_text


def words(text):
    return set(re.findall(r'\w+', normalize_text(text)))


def apply_visual_assets(plan, prompt, brand_name='', logo_asset_id='', image_asset_ids=None, illustrations=True):
    p=copy.deepcopy(plan)
    assets={a['id']:a for a in p['assets']}
    images=list(dict.fromkeys(image_asset_ids or []))
    for aid in ([logo_asset_id] if logo_asset_id else [])+images:
        if aid not in assets or assets[aid]['type']!='image':
            raise ValueError('Logo và ảnh minh họa phải là ảnh thuộc dự án này.')
    if logo_asset_id and logo_asset_id in images:
        raise ValueError('Logo không được dùng làm ảnh minh họa.')
    p['brand_footer']=brand_name
    p['branding']={'brand_name':brand_name,'logo_asset_id':logo_asset_id,
                   'image_asset_ids':images,'illustrations':illustrations}
    p['visual_overlays']=[o for o in p.get('visual_overlays',[]) if o.get('origin')!='branding']
    if logo_asset_id:
        p['visual_overlays'].append({'id':'brand_logo','origin':'branding','role':'logo',
            'asset_id':logo_asset_id,'mode':'pip','timeline_start':0,'duration':length(p),
            'x':.77,'y':.025,'width':.20})
    scenes=p.get('storyboard',[])
    if p.get('director',{}).get('engine')=='rules':
        retained=set(p['director'].get('retained_ai_scene_indices',[]))
        topics=['trợ lý AI','trợ lý','thương hiệu','thông điệp','doanh nghiệp','chiến lược',
                'báo cáo','doanh thu','khách hàng','nhân viên','lịch lớp','gói tập']
        for i,sc in enumerate(scenes):
            if i in retained:
                continue
            speech=correct_recognition_copy(sc.get('transcript_meaning',''),prompt)
            topic=next((t for t in topics if re.search(r'\b'+t+r'\b',speech,re.I)),None)
            # Uncertain recognition is never promoted into a large heading.
            sc['headline']=topic.upper() if topic else (brand_name.upper()[:80] if brand_name and i in (0,len(scenes)-1)
                else 'GIỚI THIỆU' if i==0 and speech.strip() else '')
    interior=list(range(1,len(scenes)-1)) if len(scenes)>2 else list(range(len(scenes)))
    source=[]
    warnings=p.setdefault('director',{}).setdefault('warnings',[])
    # User instructions can disable automatic graphics without hiding their
    # explicitly selected photos or brand assets.
    excluded=not illustrations or bool(re.search(r'không (?:thêm |chèn |dùng |cần )?(?:minh họa|đồ họa|hình)',prompt,re.I))
    if excluded:
        for sc in scenes:
            if sc['scene_type'] in ('explainer_card','talking_head_pip'):
                sc['scene_type']='talking_head';sc['sound_effect']='none';sc.pop('visual_asset_id',None)
    no_sound=bool(re.search(r'(?:không|tắt|bỏ|no)\s+(?:thêm |chèn |dùng )?(?:âm thanh|tiếng|sfx|sound)',prompt,re.I))
    used=set()
    for aid in images:
        candidates=[i for i in interior if i not in used]
        if not candidates:
            warnings.append('Video chưa đủ đoạn để chèn tất cả ảnh đã chọn.');break
        keywords=words(assets[aid].get('keywords',''))
        def relevance(i):return len(keywords & words(scenes[i].get('transcript_meaning','')))
        if keywords:
            candidates=[i for i in candidates if relevance(i)>0]
            if not candidates:
                warnings.append('Chưa tìm thấy lời nói phù hợp với chủ đề ảnh '+assets[aid].get('original_name','')+'.');continue
            index=max(candidates,key=relevance)
        else:
            index=candidates[0]
        sc=scenes[index]
        sc.update(scene_type='talking_head_pip',visual_asset_id=aid,
                  sound_effect='none' if no_sound else 'pop')
        used.add(index);source.append({'scene_index':index,'source':'user_uploaded','asset_id':aid})
    if not excluded:
        # When AI supplied no graphics, use only clearly recognised concepts.
        # These are labelled rule-based diagrams, never claimed to be photos.
        has_chat=any(s['scene_type']!='talking_head' and s.get('graphic_kind')=='chat' for s in scenes)
        has_diagram=any(s['scene_type']!='talking_head' and s.get('graphic_kind') in ('process','network') for s in scenes)
        candidates=[i for i in interior if i not in used and scenes[i]['scene_type']=='talking_head']
        def text(i):return correct_recognition_copy(scenes[i].get('transcript_meaning',''),prompt)
        assistant=any(re.search(r'trợ lý|hội thoại|trò chuyện',text(i),re.I) for i in range(len(scenes)))
        if not has_chat and assistant and candidates:
            ranked=[i for i in candidates if re.search(r'\bAI\b|trợ lý|hội thoại|trò chuyện',text(i),re.I)]
            if ranked:
                index=max(ranked,key=lambda i:len(re.findall(r'\bAI\b|trợ lý|hội thoại|trò chuyện',text(i),re.I)))
                sc=scenes[index]
                sc.update(scene_type='talking_head_pip',headline='TRỢ LÝ AI' if re.search(r'\bAI\b',text(index),re.I) else 'TRỢ LÝ',graphic_kind='chat',graphic_title='Trợ lý',
                    graphic_items=['Chào bạn','Bạn cần hỗ trợ gì?'],sound_effect='none' if no_sound else 'pop')
                source.append({'scene_index':index,'source':'source_rules'});used.add(index)
        if not has_diagram and length(p)>15:
            concepts=['thương hiệu','thông điệp','doanh nghiệp','chiến lược','truyền tải','kết nối',
                      'báo cáo','doanh thu','khách hàng','nhân viên','lịch lớp','gói tập']
            matches={i:[c for c in concepts if re.search(r'\b'+c+r'\b',text(i),re.I)]
                for i in candidates if i not in used}
            matches={i:items for i,items in matches.items() if len(items)>=2}
            if matches:
                index=max(matches,key=lambda i:len(matches[i]));items=matches[index][:3]
                sc=scenes[index]
                sc.update(scene_type='explainer_card',headline=items[0].upper(),graphic_kind='network',graphic_title='Ý chính',
                    graphic_items=[c.capitalize() for c in items],sound_effect='none' if no_sound else 'whoosh')
                source.append({'scene_index':index,'source':'source_rules'})
    p['director']['visual_sources']=source
    count=sum(s['scene_type']!='talking_head' for s in scenes)
    p['director']['illustration_count']=count
    if any(s['source']=='source_rules' for s in source):
        warnings.append('Đã thêm đồ họa cơ bản theo các ý rõ trong lời nói; đây là sơ đồ khái niệm, không phải ảnh chụp thật.')
    if not excluded and not count:
        warnings.append('Chưa đủ nội dung rõ để chọn minh họa tự động. Bạn có thể tải ảnh và nhập chủ đề cho ảnh.')
    return validate(p,p['assets'])
