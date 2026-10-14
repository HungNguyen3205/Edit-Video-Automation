"""Small source/config key and canonical-name hints for local speech recognition."""
import hashlib
import json
import os


def name_hint(brand='', proper_names=''):
    names=[brand.strip(),*[line.split('|')[0].strip() for line in proper_names.splitlines()]]
    selected=[]
    for name in dict.fromkeys(n for n in names if n):
        if len(', '.join([*selected,name]))<=300:selected.append(name)
    return ', '.join(selected)


def recognition_config(plan,engine,brand='',proper_names=''):
    asset_id=plan['video_clips'][0]['asset_id']
    asset=next(a for a in plan['assets'] if a['id']==asset_id)
    hint=name_hint(brand,proper_names)
    return {'version':1,'asset_id':asset_id,'source_sha256':asset.get('sha256',''),
            'engine':engine,'model':os.getenv('WHISPER_MODEL','small' if engine=='faster_whisper' else 'base'),
            'language':'vi','compute_type':'int8' if engine=='faster_whisper' else 'float32',
            'hint_sha256':hashlib.sha256(hint.encode()).hexdigest()}


def cache_changed(plan,config):
    # Existing reviewed edits and legacy imported/SRT projects stay authoritative.
    previous=plan.get('recognition_cache')
    return bool(previous and previous!=config and 'user_subtitles' not in plan)
