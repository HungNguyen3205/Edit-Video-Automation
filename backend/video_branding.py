"""Apply optional project photos, safe source graphics and persistent branding."""
import copy
import re
from editing import length, validate
from automatic_director import correct_recognition_copy
from asset_resolver import normalize_text
from text_review import normalize_names


def words(text):
    return set(re.findall(r'\w+', normalize_text(text)))


STOPWORDS = {
    'và', 'của', 'là', 'các', 'những', 'trong', 'với', 'cho', 'một', 'được', 'có', 'đến', 'về',
    'này', 'đó', 'thì', 'ở', 'tại', 'ra', 'vào', 'khi', 'đã', 'sẽ', 'đang', 'ảnh', 'hình', 'video',
    'trên', 'dưới', 'bởi', 'do', 'để', 'the', 'a', 'an', 'and', 'or', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from'
}


def parse_keywords(raw_keywords):
    """Extract list of clean keyword strings from raw keywords (comma-separated or words)."""
    if not raw_keywords or not isinstance(raw_keywords, str):
        return []
    if ',' in raw_keywords:
        return [k.strip() for k in raw_keywords.split(',') if k.strip()]
    return list(words(raw_keywords))


def extract_asset_search_metadata(asset):
    """Collect meaningful phrases (multi-word) and keywords from asset metadata, alt, and name."""
    phrases = []
    single_words = []
    seen_norm = set()

    def add_candidate(text):
        if not text or not isinstance(text, str):
            return
        parts = [p.strip() for p in re.split(r'[,;|\-–/]', text) if p.strip()]
        for p in parts:
            p_words = p.split()
            norm_p = normalize_text(p)
            if 2 <= len(p_words) <= 5 and norm_p not in seen_norm:
                seen_norm.add(norm_p)
                phrases.append((p, norm_p))
            for w in p_words:
                norm_w = normalize_text(w)
                if len(norm_w) >= 3 and norm_w not in STOPWORDS and norm_w not in seen_norm:
                    seen_norm.add(norm_w)
                    single_words.append((w, norm_w))

    # Keywords from explicit field
    if asset.get('keywords'):
        for k in parse_keywords(asset['keywords']):
            add_candidate(k)

    # Search terms from web metadata
    meta = asset.get('metadata', {})
    for term in meta.get('search_terms', []):
        add_candidate(term)

    # Reference alt or original name
    add_candidate(meta.get('reference_alt', ''))
    add_candidate(asset.get('original_name', ''))

    return phrases, single_words


def calculate_visual_relevance(speech_text, asset):
    """Calculate semantic relevance score and matched terms between speech and asset.
    Prioritizes full phrase matches over isolated single words.
    """
    if not speech_text:
        return 0.0, []

    phrases, single_words = extract_asset_search_metadata(asset)
    if not phrases and not single_words:
        return 0.0, []

    speech = normalize_text(speech_text)
    score = 0.0
    matched_terms = []

    # 1. Multi-word phrase matching (high confidence)
    for orig_phrase, norm_phrase in phrases:
        if norm_phrase in speech:
            phrase_score = 3.0 + len(norm_phrase.split()) * 1.5
            score += phrase_score
            matched_terms.append(orig_phrase)

    # 2. Distinctive single-word matching
    for orig_w, norm_w in single_words:
        if norm_w in STOPWORDS:
            continue
        if re.search(r'\b' + re.escape(norm_w) + r'\b', speech):
            # Only add if not already part of a matched phrase
            if not any(norm_w in normalize_text(mp) for mp in matched_terms):
                score += 1.0
                matched_terms.append(orig_w)

    return score, matched_terms


def calculate_transcript_match_score(speech_text, keywords):
    """Legacy backward-compatible keyword matching score."""
    if not speech_text or not keywords:
        return 0
    speech = normalize_text(speech_text)
    score = 0
    for k in keywords:
        k_clean = normalize_text(k)
        if not k_clean:
            continue
        if len(k_clean) <= 2:
            if re.search(r'\b' + re.escape(k_clean) + r'\b', speech):
                score += 2
        elif k_clean in speech:
            score += 1
    return score


def apply_visual_assets(plan, prompt, brand_name='', logo_asset_id='', image_asset_ids=None, illustrations=True, broll_asset_ids=None):
    p=copy.deepcopy(plan)
    assets={a['id']:a for a in p['assets']}
    images=list(dict.fromkeys(image_asset_ids or []))
    brolls=list(dict.fromkeys(broll_asset_ids or []))
    for aid in ([logo_asset_id] if logo_asset_id else [])+images:
        if aid not in assets or assets[aid]['type']!='image':
            raise ValueError('Logo và ảnh minh họa phải là ảnh thuộc dự án này.')
    for bid in brolls:
        if bid not in assets or assets[bid]['type'] not in ('video', 'image'):
            raise ValueError('B-roll phải là video hoặc ảnh thuộc dự án này.')
    if logo_asset_id and logo_asset_id in images:
        raise ValueError('Logo không được dùng làm ảnh minh họa.')
    if logo_asset_id and logo_asset_id in brolls:
        raise ValueError('Logo không được dùng làm B-roll.')
    p['brand_footer']=brand_name
    p['branding']={'brand_name':brand_name,'logo_asset_id':logo_asset_id,
                   'image_asset_ids':images,'broll_asset_ids':brolls,'illustrations':illustrations}
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
    diagnostics = p.setdefault('director', {}).setdefault('visual_diagnostics', [])

    for aid in images:
        interior = [i for i in range(len(scenes)) if (len(scenes) <= 2 or 0 < i < len(scenes) - 1)]
        candidates = [i for i in interior if i not in used]
        if not candidates:
            warnings.append('Video chưa đủ đoạn để chèn tất cả ảnh đã chọn.')
            break

        cur_asset = assets[aid]
        is_web = (cur_asset.get('source') == 'web_reference' or 'web_img' in str(aid))
        phrases, single_words = extract_asset_search_metadata(cur_asset)
        has_search_metadata = bool(phrases or single_words)

        scored = []
        for i in candidates:
            speech = scenes[i].get('transcript_meaning', '')
            score, matched = calculate_visual_relevance(speech, cur_asset)
            if score > 0:
                scored.append((score, matched, i))

        if is_web:
            # Web reference images MUST have meaningful relevance score (>= 2.0)
            # Never fallback to arbitrary scenes like pool image into facial recognition
            valid_scores = [item for item in scored if item[0] >= 2.0]
            if not valid_scores:
                warnings.append('Chưa tìm thấy lời nói phù hợp với chủ đề ảnh ' + cur_asset.get('original_name', '') + '.')
                diagnostics.append({'scene_index': -1, 'selected_id': aid, 'source': 'web_reference',
                                    'relevance_score': 0.0, 'matched_terms': [], 'tier': 'none',
                                    'fallback_reason': 'unrelated_content'})
                continue
            best = max(valid_scores, key=lambda x: (x[0], -x[2]))
            index = best[2]
            best_score = best[0]
            matched_terms = best[1]
            tier = 'semantic_match'
        else:
            # User uploaded image: prioritize matching transcript, else fallback to user intent
            if scored:
                best = max(scored, key=lambda x: (x[0], -x[2]))
                index = best[2]
                best_score = best[0]
                matched_terms = best[1]
                tier = 'user_specified'
            elif has_search_metadata and cur_asset.get('keywords'):
                # Explicit keywords provided but transcript did not match
                warnings.append('Chưa tìm thấy lời nói phù hợp với chủ đề ảnh ' + cur_asset.get('original_name', '') + '.')
                diagnostics.append({'scene_index': -1, 'selected_id': aid, 'source': 'user_uploaded',
                                    'relevance_score': 0.0, 'matched_terms': list(single_words or phrases),
                                    'tier': 'none', 'fallback_reason': 'no_matching_transcript'})
                continue
            else:
                index = candidates[0]
                best_score = 1.0
                matched_terms = []
                tier = 'user_specified'

        sc = scenes[index]
        sc.update(scene_type='talking_head_pip', visual_asset_id=aid,
                  sound_effect='none' if no_sound else 'pop')
        used.add(index)
        source.append({'scene_index': index, 'source': cur_asset.get('source', 'user_uploaded'), 'asset_id': aid})
        diagnostics.append({'scene_index': index, 'scene_id': sc.get('scene_id'), 'selected_id': aid,
                            'source': cur_asset.get('source', 'user_uploaded'), 'relevance_score': float(best_score),
                            'matched_terms': matched_terms, 'tier': tier, 'fallback_reason': ''})


    for bid in brolls:
        interior = [i for i in range(len(scenes)) if (len(scenes) <= 2 or 0 < i < len(scenes) - 1)]
        candidates = [i for i in interior if i not in used]
        if not candidates:
            warnings.append('Video chưa đủ đoạn để chèn tất cả B-roll đã chọn.')
            break
        b_asset = assets[bid]
        kw_list = parse_keywords(b_asset.get('keywords', ''))
        if kw_list:
            scored = []
            for i in candidates:
                s = calculate_transcript_match_score(scenes[i].get('transcript_meaning', ''), kw_list)
                if s > 0:
                    scored.append((s, i))
            if not scored:
                warnings.append('Chưa tìm thấy lời nói phù hợp với chủ đề B-roll ' + b_asset.get('original_name', '') + '.')
                diagnostics.append({'scene_index': -1, 'selected_id': bid, 'source': 'user_uploaded', 'relevance_score': 0.0, 'matched_terms': kw_list, 'tier': 'none', 'fallback_reason': 'no_matching_transcript'})
                continue
            index = max(scored, key=lambda x: (x[0], -x[1]))[1]
        else:
            index = candidates[0]

        sc = scenes[index]
        media_type = b_asset.get('type', 'video')
        if media_type != 'video':
            sc.update(scene_type='talking_head_pip', visual_asset_id=bid, visual_source_in=0,
                      sound_effect='none' if no_sound else 'pop')
            used.add(index)
            source.append({'scene_index': index, 'source': 'user_uploaded', 'asset_id': bid})
            diagnostics.append({'scene_index': index, 'scene_id': sc.get('scene_id'), 'selected_id': bid, 'source': 'user_uploaded', 'relevance_score': 1.0, 'matched_terms': kw_list, 'tier': 'user_specified', 'source_range': [0, sc['duration']], 'used_duration': sc['duration'], 'fallback_reason': ''})
            continue

        b_meta = b_asset.get('metadata', {})
        b_dur = float(b_meta.get('duration', 0.0))
        b_src_in = max(0.0, float(b_asset.get('source_in', 0.0)))
        if b_dur <= 0:
            warnings.append('B-roll ' + b_asset.get('original_name', '') + ' không có dữ liệu thời lượng.')
            diagnostics.append({'scene_index': -1, 'selected_id': bid, 'source': 'user_uploaded', 'relevance_score': 0.0, 'matched_terms': kw_list, 'tier': 'none', 'fallback_reason': 'missing_duration'})
            continue
        if b_src_in >= b_dur - 0.001:
            warnings.append('B-roll ' + b_asset.get('original_name', '') + ' có điểm đầu vượt thời lượng file.')
            diagnostics.append({'scene_index': -1, 'selected_id': bid, 'source': 'user_uploaded', 'relevance_score': 0.0, 'matched_terms': kw_list, 'tier': 'none', 'fallback_reason': 'invalid_source_in'})
            continue

        available_dur = b_dur - b_src_in
        fps = p.get('output_settings', {}).get('fps', 30)
        min_scene_dur = max(0.1, 2.0 / fps)

        if available_dur < min_scene_dur:
            warnings.append(f"B-roll {b_asset.get('original_name', '')} thời lượng khả dụng ({round(available_dur, 2)}s) quá ngắn.")
            diagnostics.append({'scene_index': -1, 'selected_id': bid, 'source': 'user_uploaded', 'relevance_score': 0.0, 'matched_terms': kw_list, 'tier': 'none', 'fallback_reason': 'duration_too_short'})
            continue

        sc_dur = sc['duration']
        if available_dur >= sc_dur - 0.02:
            sc.update(scene_type='broll', visual_asset_id=bid, visual_source_in=b_src_in,
                      sound_effect='none' if no_sound else 'pop')
            used.add(index)
            source.append({'scene_index': index, 'source': 'user_uploaded', 'asset_id': bid})
            diagnostics.append({'scene_index': index, 'scene_id': sc.get('scene_id'), 'selected_id': bid, 'source': 'user_uploaded', 'relevance_score': 1.0, 'matched_terms': kw_list, 'tier': 'user_specified', 'source_range': [b_src_in, b_src_in + sc_dur], 'used_duration': sc_dur, 'fallback_reason': ''})
        else:
            used_broll_dur = available_dur
            remainder_dur = sc_dur - used_broll_dur
            if remainder_dur < min_scene_dur:
                if used_broll_dur - (min_scene_dur - remainder_dur) >= min_scene_dur:
                    remainder_dur = min_scene_dur
                    used_broll_dur = round(sc_dur - remainder_dur, 4)
                else:
                    warnings.append(f"Không thể chia cảnh cho B-roll {b_asset.get('original_name', '')} do thời lượng cảnh quá ngắn.")
                    diagnostics.append({'scene_index': -1, 'selected_id': bid, 'source': 'user_uploaded', 'relevance_score': 0.0, 'matched_terms': kw_list, 'tier': 'none', 'fallback_reason': 'cannot_split_safely'})
                    continue

            orig_source_in = sc.get('source_in', sc['timeline_start'])
            orig_timeline_start = sc['timeline_start']

            sc_broll = copy.deepcopy(sc)
            sc_broll.update(
                scene_id=f"{sc.get('scene_id', 'sc')}_broll",
                timeline_start=orig_timeline_start,
                duration=used_broll_dur,
                source_in=orig_source_in,
                scene_type='broll',
                visual_asset_id=bid,
                visual_source_in=b_src_in,
                sound_effect='none' if no_sound else 'pop'
            )

            sc_tail = copy.deepcopy(sc)
            sc_tail.update(
                scene_id=f"{sc.get('scene_id', 'sc')}_tail",
                timeline_start=orig_timeline_start + used_broll_dur,
                duration=remainder_dur,
                source_in=orig_source_in + used_broll_dur,
                scene_type='talking_head',
                sound_effect='none',
                headline='',
                badge_text='',
                graphic_title='',
                graphic_items=[]
            )
            sc_tail.pop('visual_asset_id', None)
            sc_tail.pop('visual_source_in', None)

            scenes[index:index+1] = [sc_broll, sc_tail]

            used = {u if u < index else u + 1 for u in used}
            used.add(index)
            used.add(index + 1)
            for item in source:
                if item['scene_index'] > index:
                    item['scene_index'] += 1

            source.append({'scene_index': index, 'source': 'user_uploaded', 'asset_id': bid})
            diagnostics.append({
                'scene_index': index,
                'scene_id': sc_broll.get('scene_id'),
                'selected_id': bid,
                'source': 'user_uploaded',
                'relevance_score': 1.0,
                'matched_terms': kw_list,
                'tier': 'user_specified',
                'source_range': [b_src_in, b_src_in + used_broll_dur],
                'used_duration': used_broll_dur,
                'split_scene': True,
                'remainder_duration': remainder_dur,
                'fallback_reason': ''
            })

    interior = list(range(1, len(scenes) - 1)) if len(scenes) > 2 else list(range(len(scenes)))
    if not excluded:

        # Check real estate authenticity: do not add generic conceptual diagrams for real estate listings
        combined_text = ' '.join(scenes[i].get('transcript_meaning','') for i in range(len(scenes)))
        is_real_estate = bool(re.search(r'bất động sản|nhà đất|căn hộ|chung cư|biệt thự|villa|đất nền|nhà phố', f'{combined_text} {prompt}', re.I))

        # When AI supplied no graphics, use only clearly recognised concepts.
        # These are labelled rule-based diagrams, never claimed to be photos.
        has_chat=any(s['scene_type']!='talking_head' and s.get('graphic_kind')=='chat' for s in scenes)
        has_diagram=any(s['scene_type']!='talking_head' and s.get('graphic_kind') in ('process','network') for s in scenes)
        candidates=[i for i in interior if i not in used and scenes[i]['scene_type']=='talking_head']
        def text(i):return correct_recognition_copy(scenes[i].get('transcript_meaning',''),prompt)
        assistant=any(re.search(r'trợ lý|hội thoại|trò chuyện',text(i),re.I) for i in range(len(scenes)))
        if not has_chat and assistant and candidates and not is_real_estate:
            ranked=[i for i in candidates if re.search(r'\bAI\b|trợ lý|hội thoại|trò chuyện',text(i),re.I)]
            if ranked:
                index=max(ranked,key=lambda i:len(re.findall(r'\bAI\b|trợ lý|hội thoại|trò chuyện',text(i),re.I)))
                sc=scenes[index]
                sc.update(scene_type='talking_head_pip',headline='TRỢ LÝ AI' if re.search(r'\bAI\b',text(index),re.I) else 'TRỢ LÝ',graphic_kind='chat',graphic_title='Trợ lý',
                    graphic_items=['Chào bạn','Bạn cần hỗ trợ gì?'],sound_effect='none' if no_sound else 'pop')
                source.append({'scene_index':index,'source':'source_rules'});used.add(index)
                diagnostics.append({'scene_index': index, 'scene_id': sc.get('scene_id'), 'selected_id': 'chat_graphic', 'source': 'conceptual_graphic', 'relevance_score': 0.8, 'matched_terms': ['trợ lý'], 'tier': 'exact_concept', 'fallback_reason': ''})
        if not has_diagram and length(p)>15 and not is_real_estate:
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
                diagnostics.append({'scene_index': index, 'scene_id': sc.get('scene_id'), 'selected_id': 'network_diagram', 'source': 'conceptual_graphic', 'relevance_score': 0.75, 'matched_terms': items, 'tier': 'exact_concept', 'fallback_reason': ''})
    p['director']['visual_sources']=source
    p['director']['visual_diagnostics']=diagnostics

    names=p.get('proper_names','')
    for sc in scenes:
        for key in ('headline','badge_text','graphic_title','subheadline'):
            if sc.get(key):
                sc[key]=normalize_names(sc[key],brand_name,names)
        sc['graphic_items']=[normalize_names(x,brand_name,names) for x in sc.get('graphic_items',[])]
    if 'user_subtitles' not in p:
        from automatic_director import aligned_words
        for sub in p.get('subtitles',[]):
            text=normalize_names(sub['text'],brand_name,names)
            if text!=sub['text']:
                sub['words']=aligned_words(sub.get('words',[]),text,sub['start'],sub['end'])
                sub['text']=text
    count=sum(s['scene_type']!='talking_head' for s in scenes)
    p['director']['illustration_count']=count
    if any(s['source']=='source_rules' for s in source):
        warnings.append('Đã thêm đồ họa cơ bản theo các ý rõ trong lời nói; đây là sơ đồ khái niệm, không phải ảnh chụp thật.')
    if not excluded and not count:
        warnings.append('Chưa đủ nội dung rõ để chọn minh họa tự động. Bạn có thể tải ảnh và nhập chủ đề cho ảnh.')
    return validate(p,p['assets'])
